"""
Self-play PPO on the batched GPU engine.

The policy is a small MLP over 75 hand-built egocentric features, chosen so the
same forward pass can be re-implemented in pure stdlib Python at ~1 ms per turn
for the submission. Raw 8x8 planes would want a conv net, which cannot run inside
the 200 ms budget without numpy.

All four seats share one policy during training. `export` writes the weights as
plain nested lists for the shipped bot to carry as literals.

    python rl.py train <iterations> <batch>
    python rl.py bench
"""
import json
import math
import sys
import time

import torch
import torch.nn as nn
import torch.nn.functional as F

import engine
import gpuenv

DEV = "cuda" if torch.cuda.is_available() else "cpu"
N_FEAT = 75
N_ACT = 6
DIRS = (gpuenv.NORTH, gpuenv.EAST, gpuenv.SOUTH, gpuenv.WEST)


def _tables(dev):
    """3x3 patch indices around every cell, with an out-of-board mask."""
    idx = torch.zeros((64, 9), dtype=torch.long)
    ok = torch.zeros((64, 9), dtype=torch.bool)
    k = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for p in range(64):
                r, c = divmod(p, 8)
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    idx[p, k] = nr * 8 + nc
                    ok[p, k] = True
                else:
                    idx[p, k] = p
            k += 1
    rows = torch.arange(64) // 8
    cols = torch.arange(64) % 8
    return idx.to(dev), ok.to(dev), rows.to(dev), cols.to(dev)


class Features(object):
    """Builds [n, 4, 75] observations from a BatchGame. Mirrored in nnbot.py."""

    def __init__(self, dev):
        self.pidx, self.pok, self.rows, self.cols = _tables(dev)
        self.dev = dev
        self.tgt = gpuenv._delta_tables(dev)

    def __call__(self, g):
        n = g.n
        dev = self.dev
        seats = torch.arange(1, 5, device=dev).expand(n, 4)
        owner, upg, base = g.owner, g.upg, g.base
        pos = g.pos

        owner_at = owner.gather(1, pos)
        base_at = base.gather(1, pos).float()
        upg_at = upg.gather(1, pos).float()

        mine_cnt = torch.zeros((n, 4), device=dev)
        upg_cnt = torch.zeros((n, 4), device=dev)
        for s in range(4):
            m = owner == s + 1
            mine_cnt[:, s] = m.sum(1).float()
            upg_cnt[:, s] = (m & upg).sum(1).float()
        neutral = (owner == 0).sum(1).float().unsqueeze(1).expand(n, 4)

        sc = g.score.float()
        best_rival = torch.zeros((n, 4), device=dev)
        for s in range(4):
            others = [sc[:, j] for j in range(4) if j != s]
            best_rival[:, s] = torch.stack(others, 1).max(1).values

        # distances to home and to the nearest rival, Manhattan
        r_me = (pos // 8).float()
        c_me = (pos % 8).float()
        homes = torch.tensor([[0, 0], [0, 7], [7, 7], [7, 0]], device=dev).float()
        d_home = (r_me - homes[:, 0]).abs() + (c_me - homes[:, 1]).abs()
        d_riv = torch.full((n, 4), 14.0, device=dev)
        adj_riv = torch.zeros((n, 4), device=dev)
        for s in range(4):
            for j in range(4):
                if j == s:
                    continue
                d = (r_me[:, s] - r_me[:, j]).abs() + (c_me[:, s] - c_me[:, j]).abs()
                d_riv[:, s] = torch.minimum(d_riv[:, s], d)
                adj_riv[:, s] += (d <= 1).float()
        min_riv_cd = torch.full((n, 4), 4.0, device=dev)
        for s in range(4):
            others = [g.cd[:, j].float() for j in range(4) if j != s]
            min_riv_cd[:, s] = torch.stack(others, 1).min(1).values

        tok = (g.token.unsqueeze(1) == seats).float()
        turn = torch.full((n, 4), g.turn / 80.0, device=dev)

        sca = torch.stack([
            turn,
            1.0 - turn,
            g.income.float() / 60.0,
            sc / 3000.0,
            best_rival / 3000.0,
            torch.tanh((sc - best_rival) / 400.0),
            g.cd.float() / 4.0,
            g.frozen.float() / 2.0,
            g.prog.float() / 3.0,
            tok,
            mine_cnt / 20.0,
            upg_cnt / 15.0,
            neutral / 60.0,
            r_me / 7.0,
            c_me / 7.0,
            d_home / 14.0,
            base_at / 3.0,
            (owner_at == seats).float(),
            (owner_at == 0).float(),
            ((owner_at != 0) & (owner_at != seats)).float(),
            upg_at,
            d_riv / 14.0,
            adj_riv / 3.0,
            min_riv_cd / 4.0,
        ], dim=2)                                              # [n,4,24]

        occ = g._occupancy()
        dirf = []
        for a in DIRS:
            t = self.tgt[a, pos.reshape(-1)].reshape(n, 4)
            off = (t < 0)
            tc = t.clamp(min=0)
            o = owner.gather(1, tc)
            dirf.append(torch.stack([
                off.float(),
                ((occ.gather(1, tc) > 0) & (~off)).float(),
                ((o == seats) & (~off)).float(),
                ((o == 0) & (~off)).float(),
                ((o != 0) & (o != seats) & (~off)).float(),
                base.gather(1, tc).float() / 3.0 * (~off).float(),
            ], dim=2))
        dirf = torch.cat(dirf, dim=2)                          # [n,4,24]

        pi = self.pidx[pos.reshape(-1)].reshape(n, 4, 9)
        pk = self.pok[pos.reshape(-1)].reshape(n, 4, 9).float()
        po = torch.gather(owner.unsqueeze(1).expand(n, 4, 64), 2, pi)
        pb = torch.gather(base.unsqueeze(1).expand(n, 4, 64), 2, pi).float()
        s3 = seats.unsqueeze(2)
        patch = torch.cat([
            ((po == s3).float() * pk),
            (((po != 0) & (po != s3)).float() * pk),
            (pb / 3.0 * pk),
        ], dim=2)                                              # [n,4,27]

        return torch.cat([sca, dirf, patch], dim=2)


class Policy(nn.Module):
    def __init__(self, hidden=96):
        super().__init__()
        self.b1 = nn.Linear(N_FEAT, hidden)
        self.b2 = nn.Linear(hidden, hidden)
        self.pi = nn.Linear(hidden, N_ACT)
        self.v = nn.Linear(hidden, 1)

    def forward(self, x):
        h = torch.tanh(self.b1(x))
        h = torch.tanh(self.b2(h))
        return self.pi(h), self.v(h).squeeze(-1)

    def export(self, path):
        d = {"n_feat": N_FEAT, "n_act": N_ACT,
             "hidden": self.b1.out_features,
             "b1_w": self.b1.weight.detach().cpu().tolist(),
             "b1_b": self.b1.bias.detach().cpu().tolist(),
             "b2_w": self.b2.weight.detach().cpu().tolist(),
             "b2_b": self.b2.bias.detach().cpu().tolist(),
             "pi_w": self.pi.weight.detach().cpu().tolist(),
             "pi_b": self.pi.bias.detach().cpu().tolist()}
        json.dump(d, open(path, "w"))
        return path


def rollout(net, feats, n, maps, horizon=80):
    """One batch of self-play games. Returns tensors flattened over (turn, game, seat)."""
    g = gpuenv.BatchGame(maps, n=n, device=DEV,
                         start_token=torch.randint(1, 5, (n,), device=DEV))
    obs_l, act_l, logp_l, val_l, mask_l = [], [], [], [], []
    prev_score = g.score.float().clone()
    rew_l = []
    for _ in range(horizon):
        obs = feats(g)
        mask = g.legal_mask()
        logits, val = net(obs)
        logits = logits.masked_fill(~mask, -1e9)
        dist = torch.distributions.Categorical(logits=logits)
        act = dist.sample()
        obs_l.append(obs)
        act_l.append(act)
        logp_l.append(dist.log_prob(act))
        val_l.append(val)
        mask_l.append(mask)
        g.step(act)
        now = g.score.float()
        rew_l.append((now - prev_score) / 100.0)      # dense: points earned
        prev_score = now.clone()
    # terminal bonus: how many rivals we outscored, centred
    place = g.places()
    beat = (4.0 - place) - 1.5
    rew_l[-1] = rew_l[-1] + beat * 2.0
    return (torch.stack(obs_l), torch.stack(act_l), torch.stack(logp_l),
            torch.stack(val_l), torch.stack(mask_l), torch.stack(rew_l), g)


def train(iters=60, n=2048, lr=3e-4, clip=0.2, epochs=3, gamma=0.995, lam=0.95):
    torch.manual_seed(0)
    feats = Features(DEV)
    net = Policy().to(DEV)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    maps = torch.tensor([engine.make_map(seed=i) for i in range(n)],
                        dtype=torch.long, device=DEV)
    t0 = time.time()
    for it in range(1, iters + 1):
        with torch.no_grad():
            obs, act, logp, val, mask, rew, g = rollout(net, feats, n, maps)
        T = obs.shape[0]
        with torch.no_grad():
            adv = torch.zeros_like(rew)
            last = torch.zeros_like(rew[0])
            for t in reversed(range(T)):
                nxt = val[t + 1] if t + 1 < T else torch.zeros_like(val[0])
                delta = rew[t] + gamma * nxt - val[t]
                last = delta + gamma * lam * last
                adv[t] = last
            ret = adv + val
            adv = (adv - adv.mean()) / (adv.std() + 1e-6)
        ob = obs.reshape(-1, N_FEAT)
        ac = act.reshape(-1)
        lp = logp.reshape(-1)
        ad = adv.reshape(-1)
        rt = ret.reshape(-1)
        mk = mask.reshape(-1, N_ACT)
        idx = torch.randperm(ob.shape[0], device=DEV)
        mb = ob.shape[0] // 4
        for _ in range(epochs):
            for k in range(0, ob.shape[0], mb):
                sel = idx[k:k + mb]
                lo, v = net(ob[sel])
                lo = lo.masked_fill(~mk[sel], -1e9)
                d = torch.distributions.Categorical(logits=lo)
                ratio = (d.log_prob(ac[sel]) - lp[sel]).exp()
                pl = -torch.min(ratio * ad[sel],
                                ratio.clamp(1 - clip, 1 + clip) * ad[sel]).mean()
                vl = F.mse_loss(v, rt[sel])
                loss = pl + 0.5 * vl - 0.01 * d.entropy().mean()
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
        if it % 5 == 0 or it == 1:
            sc = g.score.float()
            print("iter %3d  mean score %6.0f  best seat %6.0f  spread %5.0f  "
                  "%.0fs  (%.1fM steps)"
                  % (it, sc.mean().item(), sc.max(1).values.mean().item(),
                     (sc.max(1).values - sc.min(1).values).mean().item(),
                     time.time() - t0, it * n * 80 / 1e6))
            net.export("nn_policy.json")
    net.export("nn_policy.json")
    print("wrote nn_policy.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "bench":
        feats = Features(DEV)
        net = Policy().to(DEV)
        maps = torch.tensor([engine.make_map(seed=i) for i in range(2048)],
                            dtype=torch.long, device=DEV)
        with torch.no_grad():
            t0 = time.time()
            rollout(net, feats, 2048, maps)
            torch.cuda.synchronize() if DEV == "cuda" else None
            dt = time.time() - t0
        print("rollout 2048 games x 80 turns: %.2fs -> %.2fM policy-steps/s"
              % (dt, 2048 * 80 * 4 / dt / 1e6))
    else:
        train(iters=int(sys.argv[2]) if len(sys.argv) > 2 else 60,
              n=int(sys.argv[3]) if len(sys.argv) > 3 else 2048)
