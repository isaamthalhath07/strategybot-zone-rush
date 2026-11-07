"""Apex agent (development module): rival models, rollout planner, tactics, act()."""
import math
import time

from evosim import EvoSim, EVO_GENOMES
from tracker import Tracker, Obs, CORNER, NEIGHB, DIR_OF, TARGET
from sim import SimState, sim_step, sim_legal

MOVES = ("NORTH", "EAST", "SOUTH", "WEST")
DIST = []
for _a in range(64):
    _ar, _ac = divmod(_a, 8)
    DIST.append(tuple(abs(_ar - _b // 8) + abs(_ac - _b % 8) for _b in range(64)))

FLAGS = {
    "mirror": 1,          # predict rivals with the evolved-planner simulator bank
    "t_defend": 1,        # prediction-aware shield defence
    "t_safe": 1,          # do not stay on rival land the owner is about to shield
    "trust": 14.0,        # evidence before a simulator's predictions drive tactics
    "trust_exact": 30.0,  # evidence on every rival before exact-world rollouts
    "wr": 0.5,            # weight of a rival's gain relative to my own loss
    "hk": 14,             # horizon (turns) for valuing a lost cell
    "kappa": 1.0,         # shield cost multiplier
    "rollout": 1,         # improve the plan by rollouts
    "tau": 120.0,         # score-gap scale of the pairwise value
    "hmin": 6,            # shortest rollout horizon when the clock forces a cut
    "deadline_ms": 100.0, # wall-clock guard for the whole turn
    "wall": 1,            # 1 = obey the wall clock (the shipped setting)
    "rmodel": 1,          # pick each unknown rival's rollout model by predictive accuracy
    "endgame": 20,        # rollouts with modelled rivals when this few turns remain
    "own_def": 0,         # replace the inherited shield rule with my own defence decision
    "expo": 1.0,          # weight of the cooldown window a shield opens
    "expo_d": 3,          # rivals this close to an unupgraded cell can raid it inside the window
}
# my own planner's genome: None keeps the evolved planner's value for that gene
for _g in tuple(EVO_GENOMES[0]) + ("home_retention", "vexp"):
    FLAGS["g_" + _g] = None


def own_genome():
    g = dict(EVO_GENOMES[0])
    for k, v in FLAGS.items():
        if k.startswith("g_") and v is not None:
            g[k[2:]] = v
    return g


def _income(owner, up, base):
    inc = [0] * 5
    for p in range(64):
        o = owner[p]
        if o:
            inc[o] += base[p] * (2 if up[p] else 1)
    return inc


# candidate behaviour models for unknown rivals: (upgrade weight, raid weight, shield reflex)
GREEDY = (("claim", 0.8, 0.25, 0), ("upgrade", 1.7, 0.3, 0), ("raider", 1.0, 1.6, 0),
          ("guard", 1.3, 0.4, 1))


def tail_action(st, s, left, ishome, uw, rw, guard):
    """A fast greedy farmer; with different weights, the family of rival models."""
    if st.fl[s] > 0:
        return "STAY"
    p = st.pos[s]
    owner, up, base = st.owner, st.up, st.base
    if guard and st.cd[s] == 0:
        for j in (1, 2, 3, 4):
            if j != s and st.fl[j] == 0:
                c = st.pos[j]
                if owner[c] == s and not ishome[c]:
                    return "SHIELD"
    dp = DIST[p]
    prog = st.prog[s]
    best, bi = 0.0, -1
    for i in range(64):
        o = owner[i]
        u = up[i]
        if o == s:
            if u:
                continue
            work = 3
        elif ishome[i]:
            continue
        else:
            work = 3 if u else 1
        if i == p:
            work -= prog
            if work < 1:
                work = 1
        cost = dp[i] + work
        if cost > left:
            continue
        life = left - cost + 1
        v = base[i]
        if o == s:
            r = v * life * uw
        elif o == 0:
            r = v * life
        else:
            r = rw * (8 * v * (1 + u) + v * life)
        r /= cost
        if r > best:
            best, bi = r, i
    if bi < 0 or bi == p:
        return "STAY"
    pr, pc = divmod(p, 8)
    tr_, tc = divmod(bi, 8)
    occ = st.pos
    cands = []
    if tr_ < pr:
        cands.append(("NORTH", p - 8))
    elif tr_ > pr:
        cands.append(("SOUTH", p + 8))
    if tc < pc:
        cands.append(("WEST", p - 1))
    elif tc > pc:
        cands.append(("EAST", p + 1))
    for nm, q in cands:
        if q != occ[1] and q != occ[2] and q != occ[3] and q != occ[4]:
            return nm
    return cands[0][0] if cands else "STAY"


class Mirror(object):
    """Exact-simulator hypotheses for one rival seat."""

    def __init__(self, seat):
        self.seat = seat
        self.hyps = [[EvoSim(g), True, 0] for g in EVO_GENOMES]
        self.pred = [None] * len(self.hyps)    # set of possible actions this turn
        self.forced = True

    def alive(self):
        for h in self.hyps:
            if h[1]:
                return True
        return False

    def best(self, need):
        best = None
        for k, h in enumerate(self.hyps):
            if h[1] and h[2] >= need and self.pred[k] is not None:
                if best is None or h[2] > self.hyps[best][2]:
                    best = k
        return best

    def score(self, obs):
        """obs: ('move', d) | ('shield',) | ('ambig', bset) | ('stay', bset) | None (forced)."""
        if obs is None or self.forced:
            return
        for k, h in enumerate(self.hyps):
            if not h[1] or self.pred[k] is None:
                continue
            A = self.pred[k]
            kind = obs[0]
            # evidence = log(1 / chance a generic bot does this): a matched move
            # or shield says far more than a matched stay
            if kind == "move":
                ok = obs[1] in A
                w = 2.3 if len(A) == 1 else 1.6
            elif kind == "shield":
                ok = "SHIELD" in A
                w = 3.5
            elif kind == "ambig":
                ok = ("SHIELD" in A or "STAY" in A or bool(A & obs[1]))
                w = 0.0
            else:
                ok = "STAY" in A or bool(A & obs[1])
                w = 0.5 if "STAY" in A else 0.0
            if not ok:
                h[1] = False
            else:
                h[2] += w

    def predict(self, ctx, legal, flag):
        s = self.seat
        base, ishome, owner, level, pos, frozen, income = ctx
        self.forced = len(legal) == 1
        for k, h in enumerate(self.hyps):
            self.pred[k] = None
            if not h[1]:
                continue
            sim = h[0]
            try:
                if not sim.begin(s, legal, base, ishome, owner, level, pos, frozen):
                    self.pred[k] = set(["STAY"])
                    continue
                if flag is None:
                    a1, c1, b1 = sim.decide(s, legal, False, base, ishome, owner, level, pos, frozen, income)
                    a2, _c2, _b2 = sim.decide(s, legal, True, base, ishome, owner, level, pos, frozen, income)
                    sim.commit(a1, c1, b1)
                    self.pred[k] = set([a1, a2])
                else:
                    a, c, b = sim.decide(s, legal, flag, base, ishome, owner, level, pos, frozen, income)
                    sim.commit(a, c, b)
                    self.pred[k] = set([a])
            except Exception:
                h[1] = False


class RivalModel(object):
    """Online model selection for a rival no exact simulator explains."""

    def __init__(self, seat):
        self.seat = seat
        self.evo = EvoSim(EVO_GENOMES[0])
        self.names = ["evo"] + [g[0] for g in GREEDY]
        self.acc = [0.62] + [0.55] * len(GREEDY)    # decayed accuracy
        self.pred = [None] * len(self.names)

    def score(self, obs):
        if obs is None:
            return
        for k, a in enumerate(self.pred):
            if a is None:
                continue
            kind = obs[0]
            if kind == "move":
                m = 1.0 if a == obs[1] else 0.0
            elif kind == "shield":
                m = 1.0 if a == "SHIELD" else 0.0
            elif kind == "ambig":
                m = 1.0 if a in ("SHIELD", "STAY") or a in obs[1] else 0.0
            else:
                if a in obs[1]:
                    continue
                m = 1.0 if a == "STAY" else 0.0
            self.acc[k] = 0.92 * self.acc[k] + 0.08 * m

    def predict(self, ctx, legal, flag, st, ishome):
        s = self.seat
        base, _ih, owner, level, pos, frozen, income = ctx
        try:
            if self.evo.begin(s, legal, base, ishome, owner, level, pos, frozen):
                a, c, b = self.evo.decide(s, legal, bool(flag), base, ishome, owner, level, pos, frozen, income)
                self.evo.commit(a, c, b)
            else:
                a = "STAY"
        except Exception:
            a = "STAY"
        self.pred[0] = a
        left = 81 - st.turn
        for k, g in enumerate(GREEDY):
            self.pred[k + 1] = tail_action(st, s, left, ishome, g[1], g[2], g[3])

    def best(self):
        k = max(range(len(self.acc)), key=lambda i: (self.acc[i], -i))
        return k


class Beta(object):
    __slots__ = ("a", "b")

    def __init__(self, p, n):
        self.a = p * n
        self.b = (1 - p) * n

    def add(self, x, w=1.0):
        if x:
            self.a += w
        else:
            self.b += w

    def p(self):
        return self.a / (self.a + self.b)


def _rival_legal(pos, frozen, cd, s):
    if frozen[s]:
        return ["STAY"]
    p = pos[s]
    lg = [d for d in MOVES if TARGET.get((p, d)) is not None]
    lg.append("STAY")
    if cd[s] == 0:
        lg.append("SHIELD")
    return lg


def plan_pick(A):
    if len(A) == 1:
        return next(iter(A))
    for x in ("STAY", "SHIELD", "NORTH", "EAST", "SOUTH", "WEST"):
        if x in A:
            return x
    return "STAY"


class Agent(object):
    def __init__(self):
        self.tr = Tracker()
        self.me = None
        self.mirrors = {}
        self.last = None
        self.own = None
        self.prev_pred = {}
        self.rt_cost = 0.0005
        self.ro_cache = None

    # ------------------------------------------------------------------
    def new_game(self, me):
        self.me = me
        self.mirrors = dict((s, Mirror(s)) for s in (1, 2, 3, 4) if s != me)
        self.own = EvoSim(own_genome())
        self.models = dict((s, RivalModel(s)) for s in (1, 2, 3, 4) if s != me)
        self.ro_cache = None
        # woken mid-game: the planner's own clock guess is worse than the tracker's
        self.sync_clock = not self.tr.known_start
        self.commit_imm = dict((s, Beta(0.75, 4.0)) for s in (1, 2, 3, 4))
        self.commit_far = dict((s, Beta(0.6, 3.0)) for s in (1, 2, 3, 4))
        self.shresp = dict((s, Beta(0.25, 4.0)) for s in (1, 2, 3, 4))
        self.agg = dict((s, Beta(0.12, 8.0)) for s in (1, 2, 3, 4))
        self.prev_pred = {}

    def hint(self, s):
        p = self.prev_pred.get(s)
        if p is None:
            return None
        return 1.0 if "SHIELD" in p else 0.0

    def observe_rivals(self, P, B, prev_cdmin):
        tr = self.tr
        me = self.me
        for s in (1, 2, 3, 4):
            if s == me:
                continue
            m = self.mirrors.get(s)
            if P.frz[s]:
                obs = None
            elif B.pos[s] != P.pos[s]:
                obs = ("move", DIR_OF.get((P.pos[s], B.pos[s])))
            else:
                bset = set()
                for d in MOVES:
                    t = TARGET.get((P.pos[s], d))
                    if t is None:
                        continue
                    if P.occ[t] or (B.occ[t] and B.occ[t] != s):
                        bset.add(d)
                if s in tr.amb:
                    obs = ("ambig", bset)
                elif s in tr.shielded:
                    obs = ("shield",)
                else:
                    obs = ("stay", bset)
            if m is not None:
                m.score(obs)
            self.models[s].score(obs)
            if not P.frz[s]:
                c0 = B.pos[s]
                self.agg[s].add(B.owner[c0] not in (0, s) and not B.home[c0], 0.5)
                c = P.pos[s]
                if P.owner[c] == me and not P.home[c]:
                    stayed = (obs is not None and obs[0] in ("stay", "ambig")) or s in tr.caught
                    if not P.up[c]:
                        self.commit_imm[s].add(stayed)
                    else:
                        self.commit_far[s].add(stayed)
        for o in (1, 2, 3, 4):
            if o == me or P.frz[o] or prev_cdmin[o] > 0:
                continue
            exposed = False
            for j in (1, 2, 3, 4):
                if j == o or P.frz[j]:
                    continue
                c = P.pos[j]
                if P.owner[c] == o and not P.home[c]:
                    exposed = True
            if exposed:
                self.shresp[o].add(o in tr.shielded and o not in tr.amb)

    # ------------------------------------------------------------------
    def decide(self, cells, me, token, legal, t0):
        tr = self.tr
        ob = Obs(cells)
        P = tr.prev
        prev_cdmin = list(tr.cdmin)
        fresh = tr.update(ob, me, token, legal, self.last, self.hint)
        if fresh or self.me != me:
            self.new_game(me)
        elif P is not None:
            self.observe_rivals(P, ob, prev_cdmin)
        B = ob
        base = B.base
        ishome = [bool(h) for h in B.home]
        owner, level = B.owner, B.up
        pos = list(B.pos)
        frozen = list(B.frz)
        income = _income(owner, level, base)
        ctx = (base, ishome, owner, level, pos, frozen, income)
        holder = tr.holder()
        st = SimState()
        st.base = base
        st.home = B.home
        st.owner = list(owner)
        st.up = list(level)
        st.pos = list(pos)
        st.fl = list(tr.fl)
        st.cd = list(tr.cd)
        st.prog = list(tr.prog)
        st.score = list(tr.score)
        st.turn = tr.turn
        st.token = holder if holder is not None else me
        st.resets = tr.claim_resets()
        # ---- predictions ------------------------------------------------------
        preds = {}
        for s in (1, 2, 3, 4):
            if s == me or pos[s] < 0:
                continue
            lg = _rival_legal(pos, frozen, tr.cd, s)
            flag = None if holder is None else (holder == s)
            m = self.mirrors[s]
            if FLAGS["mirror"] and m.alive():
                m.predict(ctx, lg, flag)
                k = m.best(FLAGS["trust"])
                if k is not None:
                    preds[s] = m.pred[k]
            self.models[s].predict(ctx, lg, holder == s, st, ishome)
        self.prev_pred = {}
        for s, m in self.mirrors.items():
            k = m.best(0)
            if k is not None:
                self.prev_pred[s] = m.pred[k]
        # ---- base plan: the evolved planner on my own seat ----------------------
        if not self.own.begin(me, legal, base, ishome, owner, level, pos, frozen):
            return legal[0]
        if self.sync_clock:
            self.own.mem["turn"] = tr.turn
            self.sync_clock = False
        plan, cc, baited = self.own.decide(me, legal, bool(token), base, ishome, owner, level, pos, frozen, income)
        a = self.tactics(plan, B, preds, legal)
        if FLAGS["rollout"] and tr.turn < 80:
            try:
                a = self.rollout_choice(st, B, ishome, legal, a, plan, cc, baited, t0)
            except Exception:
                pass
        self.own.commit(a, cc, baited if a == plan else False)
        return a

    # ------------------------------------------------------------------
    def exact_world(self):
        """Every rival explained by a trusted simulator, and the token known."""
        if self.tr.holder() is None:
            return None
        out = {}
        for s, m in self.mirrors.items():
            k = m.best(FLAGS["trust_exact"])
            if k is None or len(m.pred[k]) != 1:
                return None
            out[s] = k
        return out

    def rollout_choice(self, st, B, ishome, legal, plan, eplan, cc, baited, t0):
        ex = self.exact_world()
        tr = self.tr
        me = self.me
        rsims, rpred = {}, {}
        if ex is None:
            self.ro_cache = None
            # only with models trained on this game (not after waking up mid-game)
            if 81 - tr.turn > FLAGS["endgame"] or tr.seen < 10:
                return plan
            for s, m in self.mirrors.items():
                k = m.best(FLAGS["trust"])
                if k is not None:
                    rsims[s] = m.hyps[k][0]
                    rpred[s] = plan_pick(m.pred[k])
                else:
                    md = self.models[s]
                    k = md.best() if FLAGS["rmodel"] else 0
                    rsims[s] = md.evo if k == 0 else GREEDY[k - 1]
                    rpred[s] = md.pred[k] or "STAY"
        else:
            for s, k in ex.items():
                m = self.mirrors[s]
                rsims[s] = m.hyps[k][0]
                rpred[s] = next(iter(m.pred[k]))
        at = B.pos[me]
        threatened = False
        for r in (1, 2, 3, 4):
            if r != me and B.owner[B.pos[r]] == me and not B.home[B.pos[r]]:
                threatened = True
        cands = [plan]
        for a in legal:
            if a in cands:
                continue
            if a in MOVES:
                t = TARGET.get((at, a))
                if t is None or B.occ[t]:
                    continue
            if a == "SHIELD" and not threatened:
                continue
            cands.append(a)
        if len(cands) <= 1:
            self.ro_cache = None
            return plan
        left = 81 - tr.turn
        wall = FLAGS["wall"]
        hard = t0 + FLAGS["deadline_ms"] / 1000.0
        # the plan's value may already be known from last turn's chosen rollout
        known = None
        sig = (tuple(st.owner), tuple(st.up), tuple(st.pos), tuple(st.score),
               tuple(st.fl), tuple(st.cd), st.turn)
        c = self.ro_cache
        if c is not None:
            traj, val, idx = c
            if idx < len(traj) and traj[idx][0] == sig and traj[idx][1] == plan:
                known = (val, (traj, idx + 1))
        horizon = left
        if wall:
            now = time.perf_counter()
            need = sum(1 for a in cands if not (a == plan and known is not None))
            avail = hard - now
            per_turn = self.rt_cost
            if need * left * per_turn > avail:
                horizon = max(FLAGS["hmin"], int(avail / max(1e-6, need * per_turn)))
        best, bv, bnext = plan, None, None
        for a in cands:
            if a == plan and known is not None and horizon >= left:
                v, nxt = known
            else:
                r = self.rollout_value(st, rsims, rpred, a, eplan, cc, baited, horizon, ishome,
                                       hard if wall else None)
                if r is None:
                    break
                v, nxt = r
            if bv is None or v > bv:
                best, bv, bnext = a, v, nxt
        if bnext is not None and horizon >= left:
            self.ro_cache = (bnext[0], bv, bnext[1])
        else:
            self.ro_cache = None
        return best

    def rollout_value(self, st0, rsims, rpred, a, eplan, cc, baited, horizon, ishome, hard):
        me = self.me
        st = st0.copy()
        sims = dict((s, x.clone() if isinstance(x, EvoSim) else x) for s, x in rsims.items())
        mine = self.own.clone()
        mine.commit(a, cc, baited if a == eplan else False)
        sims[me] = mine
        acts = [None] * 5
        for s, x in rpred.items():
            acts[s] = x
        acts[me] = a
        sim_step(st, acts)
        base = st.base
        h = 1
        traj = []
        t_start = time.perf_counter()
        n_turns = 0
        while st.turn <= 80 and h < horizon:
            owner = st.owner[:]
            level = st.up[:]
            pos = st.pos[:]
            fl = st.fl
            frozen = [False, fl[1] > 0, fl[2] > 0, fl[3] > 0, fl[4] > 0]
            income = _income(owner, level, base)
            sig = (tuple(owner), tuple(level), tuple(pos), tuple(st.score),
                   tuple(fl), tuple(st.cd), st.turn)
            for s in (1, 2, 3, 4):
                x = sims[s]
                if type(x) is tuple:
                    acts[s] = tail_action(st, s, 81 - st.turn, ishome, x[1], x[2], x[3])
                else:
                    acts[s] = x.step(s, sim_legal(st, s), st.token == s, base, ishome,
                                     owner, level, pos, frozen, income)
            traj.append((sig, acts[me]))
            sim_step(st, acts)
            h += 1
            n_turns += 1
            if hard is not None and (n_turns & 3) == 0 and time.perf_counter() > hard:
                return None
        if n_turns:
            dt = (time.perf_counter() - t_start) / n_turns
            self.rt_cost = 0.8 * self.rt_cost + 0.2 * dt
        fin = list(st.score)
        if st.turn <= 80:
            rem = 81 - st.turn
            inc = _income(st.owner, st.up, base)
            for s in (1, 2, 3, 4):
                fin[s] += inc[s] * rem
        tau = FLAGS["tau"]
        v = 0.0
        for r in (1, 2, 3, 4):
            if r != me:
                v += 1.0 / (1.0 + math.exp(-(fin[me] - fin[r]) / tau))
        v += fin[me] * 1e-5
        return v, (traj, 0)

    # ------------------------------------------------------------------
    def turn_value(self, left):
        return max(4.0, min(60.0, 2.2 * left))

    def p_stay(self, s, need_left, preds):
        if s in preds:
            A = preds[s]
            return 0.97 if A == set(["STAY"]) else (0.5 if "STAY" in A else 0.03)
        if need_left <= 1:
            return self.commit_imm[s].p()
        return self.commit_far[s].p()

    def p_shield(self, o, preds):
        if o in preds:
            A = preds[o]
            return 0.97 if A == set(["SHIELD"]) else (0.5 if "SHIELD" in A else 0.03)
        return self.shresp[o].p()

    def tactics(self, a, B, preds, legal):
        tr = self.tr
        me = self.me
        at = B.pos[me]
        left = 81 - tr.turn
        tv = self.turn_value(left)
        wr = FLAGS["wr"]
        if FLAGS["own_def"] and a == "SHIELD":
            a = self.own.pre if self.own.pre in legal else "STAY"
        if FLAGS["t_defend"] and "SHIELD" in legal and tr.cd[me] == 0 and not B.frz[me]:
            benefit = 0.0
            miss = 1.0
            hk = FLAGS["hk"]
            catchers = []
            for r in (1, 2, 3, 4):
                if r == me or B.frz[r]:
                    continue
                c = B.pos[r]
                if B.owner[c] != me or B.home[c]:
                    continue
                need = 3 if B.up[c] else 1
                nl = need - tr.prog[r]
                ps = self.p_stay(r, nl, preds)
                miss *= 1.0 - ps
                catchers.append((r, ps))
                if nl == 1:
                    v = B.base[c]
                    lvl = 2 if B.up[c] else 1
                    h = min(left, hk)
                    loss = v * lvl * h + wr * (8 * v * lvl + v * h)
                    benefit += ps * (loss + wr * 2 * tv)
            if benefit > 0:
                lost_prog = tr.prog[me] if a == "STAY" else 0
                if left <= 1:
                    cost = 0.0 if a != "STAY" else self.stay_gain_now(B, left)
                else:
                    cost = FLAGS["kappa"] * (tv * (1 + lost_prog) + miss * 2 * tv + 0.5 * tv)
                    if FLAGS["expo"] and left > 2:
                        cost += FLAGS["expo"] * self.window_exposure(B, catchers, preds, left)
                if benefit > cost:
                    return "SHIELD"
        if FLAGS["t_safe"] and a == "STAY":
            o = B.owner[at]
            if o not in (0, me) and not B.home[at] and not B.frz[o] and tr.cdmin[o] == 0 and left > 1:
                ps = self.p_shield(o, preds)
                k = tr.prog[me]
                b_o = wr * 2.0
                if ps > (3.0 + k) / (3.0 + k + b_o) * 0.9:
                    alt = self.bait_step(B, legal, o)
                    if alt is not None:
                        return alt
        return a

    def window_exposure(self, B, catchers, preds, left):
        """Expected loss to raids during the 4-turn cooldown a shield now would open."""
        me = self.me
        dmax = FLAGS["expo_d"]
        caught = dict(catchers)
        h = min(left, FLAGS["hk"])
        risk = 0.0
        for r in (1, 2, 3, 4):
            if r == me:
                continue
            pr = B.pos[r]
            # a rival I catch is frozen for half the window; one already frozen too
            free = 0.5 if (B.frz[r] or r in caught) else 1.0
            g = self.agg[r].p() * free
            if g <= 0.0:
                continue
            best = 0.0
            for c in range(64):
                if B.owner[c] == me and not B.up[c] and not B.home[c] and DIST[pr][c] <= dmax:
                    v = B.base[c]
                    val = v * h + FLAGS["wr"] * (8 * v + v * h)
                    if val > best:
                        best = val
            risk += g * best
        return risk

    def stay_gain_now(self, B, left):
        tr = self.tr
        me = self.me
        at = B.pos[me]
        need = tr.need(me, at, B)
        if need and tr.prog[me] + 1 >= need:
            v = B.base[at]
            o = B.owner[at]
            if o not in (0, me):
                return 8 * v * (2 if B.up[at] else 1) + v * left
            return v * left
        return 0.0

    def bait_step(self, B, legal, o):
        at = B.pos[self.me]
        best, bv = None, -1e9
        for d in MOVES:
            if d not in legal:
                continue
            t = TARGET.get((at, d))
            if t is None or B.occ[t]:
                continue
            v = 0.0
            if B.owner[t] == o and not B.home[t]:
                v += 2.0 + B.base[t]
            elif B.owner[t] == 0:
                v += 1.0 + B.base[t]
            elif B.owner[t] == self.me:
                v += 0.5
            if v > bv:
                best, bv = d, v
        return best


class _Cell(object):
    __slots__ = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points


# --------------------------------------------------------------------------
# input normalisation: the documented interface first, tolerant of variants
_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
_ALL = ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD")
_MISSING = object()


def _attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _cell_like(x):
    if isinstance(x, dict):
        return "owner" in x
    if hasattr(x, "owner"):
        return True
    return isinstance(x, (list, tuple)) and len(x) == 6


def _field(c, k, idx):
    if isinstance(c, dict):
        return c.get(k)
    v = getattr(c, k, _MISSING)
    if v is not _MISSING:
        return v
    if isinstance(c, (list, tuple)) and len(c) == 6:
        return c[idx]
    return None


def _int(x):
    if x is None:
        return 0
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    return int(float(x))


def _bool(x):
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(x)


def _name(a):
    if isinstance(a, str):
        s = a
    else:
        s = getattr(a, "name", None)
        if not isinstance(s, str):
            s = getattr(a, "value", None)
        if not isinstance(s, str):
            s = str(a)
    s = s.strip().upper()
    if "." in s:
        s = s.rsplit(".", 1)[1]
    return s


def _flatten(board):
    if isinstance(board, dict):
        board = board.get("cells") or board.get("board")
    seq = list(board)
    if len(seq) == 64 and _cell_like(seq[0]):
        return seq
    if len(seq) == 8:
        rows = [list(r) for r in seq]
        if all(len(r) == 8 for r in rows) and _cell_like(rows[0][0]):
            return [c for r in rows for c in r]
    raise ValueError("unrecognised board")


def normalise(state):
    raw = _flatten(_attr(state, "board"))
    cells = []
    for c in raw:
        cells.append(_Cell(_int(_field(c, "occupant", 0)), _int(_field(c, "owner", 1)),
                           _bool(_field(c, "is_upgraded", 2)), _bool(_field(c, "is_home", 3)),
                           _bool(_field(c, "is_frozen", 4)), _int(_field(c, "base_points", 5)) or 1))
    for s in (1, 2, 3, 4):
        p = CORNER[s]
        if cells[p].is_home and not cells[p].owner:
            cells[p].owner = s
    me = _int(_attr(state, "bot_id"))
    found = [c.occupant for c in cells]
    if me not in found:
        if (me + 1) in found and 0 <= me <= 3:
            me += 1
        else:
            raise ValueError("cannot find my bot")
    raw_legal = _attr(state, "legal_actions")
    raw_legal = list(raw_legal) if raw_legal is not None else []
    lookup = {}
    for a in raw_legal:
        nm = _name(a)
        if nm in _ALL and nm not in lookup:
            lookup[nm] = a
    if "STAY" not in lookup:
        lookup["STAY"] = "STAY"
    names = [a for a in _ALL if a in lookup]
    token = _bool(_attr(state, "is_priority_token", False))
    return cells, me, token, names, lookup


def fallback(cells, me, names):
    """A policy that depends on almost nothing: finish work here, else walk to work."""
    at = -1
    occ = set()
    for i, c in enumerate(cells):
        if c.occupant == me:
            at = i
        elif c.occupant:
            occ.add(i)
    if at < 0 or len(names) == 1:
        return "STAY"
    c = cells[at]
    if c.owner == 0 or (c.owner == me and not c.is_upgraded) or \
            (c.owner != me and not c.is_home and not c.is_upgraded):
        return "STAY"
    best, bi = -1.0, -1
    for i, x in enumerate(cells):
        if i == at or i in occ or x.is_home:
            continue
        if x.owner == 0 or (x.owner == me and not x.is_upgraded):
            r = x.base_points / (DIST[at][i] + (1 if x.owner == 0 else 3))
            if r > best:
                best, bi = r, i
    if bi < 0:
        return "STAY"
    for d in MOVES:
        t = TARGET.get((at, d))
        if t is not None and t not in occ and d in names and DIST[t][bi] < DIST[at][bi]:
            return d
    return "STAY"


class _Seat(object):
    """Per-seat state: the agent, an always-warm backup planner, failure counts."""

    def __init__(self):
        self.agent = Agent()
        self.backup = EvoSim(EVO_GENOMES[0])
        self.fails = 0


_SEATS = {}


def _backup_action(seat, cells, me, names, token):
    owner = [c.owner for c in cells]
    level = [1 if c.is_upgraded else 0 for c in cells]
    base = [c.base_points for c in cells]
    ishome = [bool(c.is_home) for c in cells]
    pos, frozen = [-1] * 5, [False] * 5
    for i, c in enumerate(cells):
        if 1 <= c.occupant <= 4:
            pos[c.occupant], frozen[c.occupant] = i, c.is_frozen
    income = _income(owner, level, base)
    if seat.backup.mem is not None and seat.backup.mem.get("turn", 0) >= 80:
        seat.backup = EvoSim(EVO_GENOMES[0])
    return seat.backup.step(me, names, token, base, ishome, owner, level, pos, frozen, income)


def act(state):
    t0 = time.perf_counter()
    try:
        cells, me, token, names, lookup = normalise(state)
    except Exception:
        try:
            for a in list(_attr(state, "legal_actions") or []):
                if _name(a) == "STAY":
                    return a
        except Exception:
            pass
        return "STAY"
    seat = _SEATS.get(me)
    if seat is None:
        seat = _SEATS[me] = _Seat()
    b = None
    try:
        b = _backup_action(seat, cells, me, names, token)
    except Exception:
        b = None
    a = None
    if seat.fails < 3:
        try:
            a = seat.agent.decide(cells, me, token, names, t0)
            seat.agent.last = a
        except Exception:
            seat.fails += 1
            a = None
            seat.agent = Agent()
    if a not in lookup:
        a = b
    if a not in lookup:
        try:
            a = fallback(cells, me, names)
        except Exception:
            a = "STAY"
    if a not in lookup:
        a = "STAY"
    if a == "SHIELD" and len(names) > 1 and "SHIELD" not in names:
        a = "STAY"
    return lookup.get(a, lookup["STAY"])
