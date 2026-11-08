"""Tune the economic planner on graded positions (grader-as-teacher).

The grader stores, for every graded decision, the Q value of *every* candidate
action, the position, and the planner's memory at that moment
(`grade.py batch ... --store`). So a planner genome can be scored without
playing a single game: re-run the planner on each stored position and read off
the grader's Q for the action it would choose,

    J(genome) = mean over positions of  Q(action chosen by genome) - Q(action played)

which is the expected pairwise-win gain per decision of switching to that genome
for one move with everyone continuing as before -- one step of policy
improvement, with the grader as the critic. Positions are split by game into a
tuning half and a validation half, and a candidate must improve both. The result
is then confirmed in real games (genarena.py), because a policy that changes many
moves also changes the positions it reaches.

    python zenith/lab/distill.py score runs/*.jsonl [--genome g.json]
    python zenith/lab/distill.py tune  runs/*.jsonl --gens 40 --out zenith/lab/distilled.json
"""
import argparse
import copy
import gzip
import json
import multiprocessing as mp
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "zenith", "src"))

from evosim import EvoSim, EVO_GENOMES  # noqa: E402

MOVES = {"NORTH": -8, "SOUTH": 8, "WEST": -1, "EAST": 1}
BASE = dict(EVO_GENOMES[0], home_retention=100.0, vexp=1.0)
# gene -> (low, high, step); depth and breadth are structural and stay fixed
SPACE = {
    "upgrade_open": (0.5, 4.0, 0.25), "upgrade_late": (1.0, 6.0, 0.4),
    "raid_open": (0.2, 2.5, 0.15), "raid_late": (0.5, 4.0, 0.25),
    "risk_open": (0.0, 8.0, 0.5), "risk_late": (0.0, 12.0, 0.8),
    "income_lifetime": (15.0, 70.0, 4.0), "safety_slope": (0.0, 8.0, 0.6),
    "fortify_premium": (0.8, 1.6, 0.06), "denial_base": (0.0, 1.2, 0.1),
    "denial_close": (0.0, 0.8, 0.07), "cash_weight": (0.5, 2.0, 0.1),
    "contest_cost": (0.0, 1.5, 0.1), "route_weight": (0.0, 1.2, 0.07),
    "route_delay": (0.0, 0.3, 0.03), "inertia": (0.0, 0.3, 0.03),
    "shield_weight": (0.5, 2.5, 0.12), "backfire_cost": (0.3, 3.0, 0.15),
    "feint_weight": (0.0, 2.5, 0.15),
    "home_retention": (20.0, 100.0, 8.0), "vexp": (0.8, 1.6, 0.06),
}

_DATA = None


def load(paths):
    recs = []
    for p in paths:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt") as f:
            for k, ln in enumerate(f):
                if not ln.strip():
                    continue
                d = json.loads(ln)
                if "state" not in d or not d.get("q") or d["category"] == "Forced":
                    continue
                if d["played"] not in d["q"]:
                    continue
                d["game"] = "%s#%s#%d" % (p, d.get("final"), d["seat"])
                recs.append(d)
    return recs


def effective(a, st, me, q):
    """The candidate an action plays as: a blocked move plays like STAY."""
    if a in q:
        return a
    if a in MOVES:
        t = st["pos"][me] + MOVES[a]
        if t in st["pos"][1:]:
            return "STAY"
    return "STAY" if "STAY" in q else None


def decide(genome, d):
    st = d["state"]
    me = d["seat"]
    sim = EvoSim(genome)
    sim.mem = copy.deepcopy(d["snap"]) if d.get("snap") else None
    base = st["base"]
    ishome = [bool(h) for h in st["home"]]
    owner = st["owner"]
    level = st["up"]
    pos = st["pos"]
    frozen = st["frz"]
    legal = st["legal"]
    income = [0] * 5
    for c in range(64):
        if owner[c]:
            income[owner[c]] += base[c] * (2 if level[c] else 1)
    try:
        if not sim.begin(me, legal, base, ishome, owner, level, pos, frozen):
            return legal[0]
        a, _c, _b = sim.decide(me, legal, st["token"] == me, base, ishome, owner, level,
                               pos, frozen, income)
    except Exception:
        return "STAY"
    return a


def score(genome, recs):
    """(mean gain over the played move, share of decisions changed, n)."""
    gain, changed, n = 0.0, 0, 0
    for d in recs:
        q = d["q"]
        a = effective(decide(genome, d), d["state"], d["seat"], q)
        if a is None:
            continue
        n += 1
        gain += q[a] - q[d["played"]]
        changed += a != d["played"]
    return (gain / n if n else 0.0), (changed / n if n else 0.0), n


def split(recs):
    games = sorted(set(d["game"] for d in recs))
    rnd = random.Random(7)
    rnd.shuffle(games)
    tune = set(games[: len(games) // 2])
    return [d for d in recs if d["game"] in tune], [d for d in recs if d["game"] not in tune]


def mutate(g, rnd, scale):
    c = dict(g)
    keys = rnd.sample(sorted(SPACE), rnd.randint(1, 3))
    for k in keys:
        lo, hi, st = SPACE[k]
        c[k] = round(min(hi, max(lo, c[k] + rnd.gauss(0, st * scale))), 5)
    return c


def cmd_score(a):
    recs = load(a.files)
    g = dict(BASE)
    if a.genome:
        with open(a.genome) as f:
            g.update(json.load(f))
    m, ch, n = score(g, recs)
    print("%d positions: gain %+.4f PW/decision over the played move, %.1f%% of moves changed"
          % (n, m, 100 * ch))
    best = sum(max(d["q"].values()) - d["q"][d["played"]] for d in recs) / max(1, len(recs))
    print("ceiling (always the grader's best move): %+.4f PW/decision" % best)


def cmd_tune(a):
    rnd = random.Random(a.seed)
    recs = load(a.files)
    tune_set, val_set = split(recs)
    tune_games = set(d["game"] for d in tune_set)
    print("%d positions: %d tuning, %d validation" % (len(recs), len(tune_set), len(val_set)))
    global _DATA
    for d in recs:
        d["half"] = 0 if d["game"] in tune_games else 1
    _DATA = recs
    pool = mp.Pool(a.procs)

    def ev(genomes):
        jobs = []
        for g in genomes:
            jobs.append((g, 0))
            jobs.append((g, 1))
        res = pool.map(_score_half, jobs)
        return [(res[2 * i], res[2 * i + 1]) for i in range(len(genomes))]
    inc = dict(BASE)
    if a.start:
        with open(a.start) as f:
            inc.update(json.load(f))
    (it, iv), = ev([inc])
    print("start: tune %+.4f  val %+.4f  changed %.1f%%" % (it[0], iv[0], 100 * it[1]))
    scale = 1.0
    for gen in range(a.gens):
        cands = [mutate(inc, rnd, scale) for _ in range(a.lam)]
        res = ev(cands)
        order = sorted(range(len(cands)), key=lambda i: -res[i][0][0])
        bi = order[0]
        (bt, bv) = res[bi]
        accept = bt[0] > it[0] + 1e-4 and bv[0] > iv[0] - a.slack
        if accept:
            diff = dict((k, cands[bi][k]) for k in SPACE if cands[bi][k] != inc[k])
            inc, it, iv = cands[bi], bt, bv
            print("gen %2d  ACCEPT tune %+.4f val %+.4f changed %.1f%%  %s" % (
                gen, it[0], iv[0], 100 * it[1], diff), flush=True)
            with open(a.out, "w") as f:
                json.dump(dict((k, inc[k]) for k in SPACE), f, indent=1, sort_keys=True)
        else:
            scale = max(0.4, scale * 0.97)
            print("gen %2d  keep   best cand tune %+.4f val %+.4f" % (gen, bt[0], bv[0]), flush=True)
    pool.close()
    print("final: tune %+.4f  val %+.4f  changed %.1f%%" % (it[0], iv[0], 100 * it[1]))
    print("genome changes vs evolved:")
    for k in sorted(SPACE):
        if inc[k] != BASE[k]:
            print("  %-16s %8.4f -> %8.4f" % (k, BASE[k], inc[k]))


def _score_half(arg):
    g, half = arg
    return score(g, [d for d in _DATA if d["half"] == half])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    s.add_argument("--genome")
    t = sub.add_parser("tune")
    t.add_argument("files", nargs="+")
    t.add_argument("--gens", type=int, default=40)
    t.add_argument("--lam", type=int, default=12)
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--slack", type=float, default=0.0005)
    t.add_argument("--start")
    t.add_argument("--procs", type=int, default=mp.cpu_count())
    t.add_argument("--out", default=os.path.join(HERE, "distilled.json"))
    a = p.parse_args(argv)
    {"score": cmd_score, "tune": cmd_tune}[a.cmd](a)


if __name__ == "__main__":
    main()
