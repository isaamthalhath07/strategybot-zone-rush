"""
Pure-Python twin of the trained policy, so the learned weights can be measured in
the real harness and shipped if they earn it.

The feature extraction here must match rl.Features exactly, or the network is fed
different numbers than it was trained on. `python nnbot.py` self-tests that by
comparing against the torch implementation on random states.

Hidden quantities the state object does not expose (turn, scores, progress,
cooldowns, token) come from mybot.Tracker, which reconstructs them from board
diffs.
"""
import json
import math
import os

from mybot import MANH, NC, NEIGH, Tracker

N = 8
N_FEAT = 75
ACTIONS = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
DIR_DELTA = (-8, 1, 8, -1)                     # NORTH, EAST, SOUTH, WEST
HOMES = ((0, 0), (0, 7), (7, 7), (7, 0))

# 3x3 patch indices and validity, matching rl._tables ordering exactly
PATCH = []
PATCH_OK = []
for _p in range(NC):
    _idx = []
    _ok = []
    for _dr in (-1, 0, 1):
        for _dc in (-1, 0, 1):
            _r, _c = divmod(_p, N)
            _nr, _nc = _r + _dr, _c + _dc
            if 0 <= _nr < N and 0 <= _nc < N:
                _idx.append(_nr * N + _nc)
                _ok.append(1.0)
            else:
                _idx.append(_p)
                _ok.append(0.0)
    PATCH.append(tuple(_idx))
    PATCH_OK.append(tuple(_ok))


def features(seat, owner, upg, base, occ, pos, score, income, cd, frozen, prog,
             token, turn):
    """The 75 features, in the same order as rl.Features."""
    s = seat - 1
    me = pos[s]
    mine_cnt = 0
    upg_cnt = 0
    neutral = 0
    for p in range(NC):
        o = owner[p]
        if o == seat:
            mine_cnt += 1
            if upg[p]:
                upg_cnt += 1
        elif o == 0:
            neutral += 1
    best_rival = max(score[j] for j in range(4) if j != s)
    r_me, c_me = divmod(me, N)
    d_home = abs(r_me - HOMES[s][0]) + abs(c_me - HOMES[s][1])
    d_riv = 14.0
    adj_riv = 0.0
    for j in range(4):
        if j == s or pos[j] is None:
            continue
        rj, cj = divmod(pos[j], N)
        d = abs(r_me - rj) + abs(c_me - cj)
        if d < d_riv:
            d_riv = d
        if d <= 1:
            adj_riv += 1.0
    min_riv_cd = min(cd[j] for j in range(4) if j != s)
    o_at = owner[me]
    t = turn / 80.0
    marg = (score[s] - best_rival) / 400.0
    f = [
        t,
        1.0 - t,
        income[s] / 60.0,
        score[s] / 3000.0,
        best_rival / 3000.0,
        math.tanh(marg),
        cd[s] / 4.0,
        frozen[s] / 2.0,
        prog[s] / 3.0,
        1.0 if token == seat else 0.0,
        mine_cnt / 20.0,
        upg_cnt / 15.0,
        neutral / 60.0,
        r_me / 7.0,
        c_me / 7.0,
        d_home / 14.0,
        base[me] / 3.0,
        1.0 if o_at == seat else 0.0,
        1.0 if o_at == 0 else 0.0,
        1.0 if (o_at != 0 and o_at != seat) else 0.0,
        1.0 if upg[me] else 0.0,
        d_riv / 14.0,
        adj_riv / 3.0,
        min_riv_cd / 4.0,
    ]
    for k in range(4):
        d = DIR_DELTA[k]
        tc = me + d
        r, c = divmod(me, N)
        off = ((k == 0 and r == 0) or (k == 2 and r == N - 1) or
               (k == 1 and c == N - 1) or (k == 3 and c == 0))
        if off:
            tc = me
        o = owner[tc]
        f.append(1.0 if off else 0.0)
        f.append(0.0 if off else (1.0 if occ[tc] else 0.0))
        f.append(0.0 if off else (1.0 if o == seat else 0.0))
        f.append(0.0 if off else (1.0 if o == 0 else 0.0))
        f.append(0.0 if off else (1.0 if (o != 0 and o != seat) else 0.0))
        f.append(0.0 if off else base[tc] / 3.0)
    pi = PATCH[me]
    pk = PATCH_OK[me]
    for k in range(9):
        f.append(1.0 if (owner[pi[k]] == seat) else 0.0 * 1.0)
        f[-1] *= pk[k]
    for k in range(9):
        o = owner[pi[k]]
        f.append((1.0 if (o != 0 and o != seat) else 0.0) * pk[k])
    for k in range(9):
        f.append(base[pi[k]] / 3.0 * pk[k])
    return f


class NNAgent(object):
    def __init__(self, weights="nn_policy.json", seed=0, greedy=True):
        if isinstance(weights, str):
            weights = json.load(open(weights))
        self.w1 = weights["b1_w"]
        self.o1 = weights["b1_b"]
        self.w2 = weights["b2_w"]
        self.o2 = weights["b2_b"]
        self.wp = weights["pi_w"]
        self.op = weights["pi_b"]
        self.tr = Tracker()
        self.last_action = None
        self.greedy = greedy
        self.rng = seed * 2654435761 % 4294967291 or 7

    def _rand(self):
        self.rng = (1103515245 * self.rng + 12345) % 2147483648
        return self.rng / 2147483648.0

    def __call__(self, view):
        try:
            a = self.decide(view)
        except Exception:
            a = "STAY"
        if a not in view.legal_actions:
            a = "STAY"
        self.last_action = a
        return a

    def decide(self, view):
        bd = view.board
        cells = ([bd[r][c] for r in range(N) for c in range(N)]
                 if bd and isinstance(bd[0], (list, tuple)) else list(bd))
        base = [0] * NC
        owner = [0] * NC
        upg = [0] * NC
        home_of = [0] * NC
        occ = [0] * NC
        frz = [0] * NC
        for p in range(NC):
            cl = cells[p]
            base[p] = cl.base_points
            owner[p] = cl.owner
            upg[p] = 1 if cl.is_upgraded else 0
            occ[p] = cl.occupant
            frz[p] = 1 if cl.is_frozen else 0
            if cl.is_home:
                home_of[p] = cl.owner or 1
        seat = view.bot_id
        tr = self.tr
        tr.observe(owner, upg, occ, frz, seat, view.is_priority_token, base,
                   home_of, self.last_action)
        if tr.pos[seat - 1] is None:
            return "STAY"
        f = features(seat, owner, upg, base, occ, tr.pos, tr.score, tr.income,
                     tr.cd, tr.frozen, tr.prog, tr.token, tr.turn)
        h1 = []
        for i, row in enumerate(self.w1):
            acc = self.o1[i]
            for j in range(N_FEAT):
                acc += row[j] * f[j]
            h1.append(math.tanh(acc))
        h2 = []
        for i, row in enumerate(self.w2):
            acc = self.o2[i]
            for j, v in enumerate(h1):
                acc += row[j] * v
            h2.append(math.tanh(acc))
        logits = []
        for i, row in enumerate(self.wp):
            acc = self.op[i]
            for j, v in enumerate(h2):
                acc += row[j] * v
            logits.append(acc)
        legal = view.legal_actions
        best, bestv = None, -1e30
        for i, name in enumerate(ACTIONS):
            if name not in legal:
                continue
            if logits[i] > bestv:
                bestv, best = logits[i], name
        return best or "STAY"


def _selftest():
    """Compare these features against the torch implementation on random states."""
    import random
    import torch
    import engine
    import gpuenv
    import rl

    dev = "cpu"
    feats = rl.Features(dev)
    rnd = random.Random(5)
    worst = 0.0
    checked = 0
    for trial in range(6):
        base = engine.make_map(seed=trial + 1)
        cpu = engine.Game(base=base, start_token=rnd.randint(1, 4))
        for _ in range(rnd.randint(5, 55)):
            cpu.step([rnd.choice(cpu.legal(b)) for b in range(4)])
        g = gpuenv.BatchGame(base, n=1, device=dev, start_token=cpu.token)
        g.owner = torch.tensor([cpu.owner], dtype=torch.long)
        g.upg = torch.tensor([cpu.upg], dtype=torch.bool)
        g.pos = torch.tensor([cpu.pos], dtype=torch.long)
        g.frozen = torch.tensor([cpu.frozen], dtype=torch.long)
        g.cd = torch.tensor([cpu.cd], dtype=torch.long)
        g.prog = torch.tensor([cpu.prog], dtype=torch.long)
        g.score = torch.tensor([cpu.score], dtype=torch.long)
        g.income = torch.tensor([cpu.income], dtype=torch.long)
        g.turn = cpu.turn
        ref = feats(g)[0]
        occ = [0] * NC
        for i in range(4):
            occ[cpu.pos[i]] = i + 1
        for seat in range(1, 5):
            mine = features(seat, cpu.owner, cpu.upg, cpu.base, occ, cpu.pos,
                            cpu.score, cpu.income, cpu.cd, cpu.frozen, cpu.prog,
                            cpu.token, cpu.turn)
            r = ref[seat - 1].tolist()
            for k in range(N_FEAT):
                d = abs(mine[k] - r[k])
                if d > worst:
                    worst = d
                checked += 1
    print("feature comparisons: %d   worst absolute difference: %.2e" % (checked, worst))
    print("PYTHON FEATURES MATCH TORCH" if worst < 1e-5 else "FEATURE MISMATCH")
    return worst < 1e-5


if __name__ == "__main__":
    _selftest()
