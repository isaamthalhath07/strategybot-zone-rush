"""Move-for-move equivalence of two candidates on the documented interface.

  python3 lab/equiv.py candA candB [--maps 30] [--seed 41]

Both play the same fixtures (map, seat, token, opponents, opponent seeds). Because the
opponents only see public state, the games stay identical for as long as the two
candidates choose identical actions; the first differing turn is reported.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, arena, fields
import multiprocessing as mp


def job(t):
    out = []
    for c in t["cands"]:
        names = list(t["opponents"]); names.insert(t["seat"], c)
        r = sim.play(names, sim.make_map(t["family"], t["mapseed"]), token=t["token"], seed=t["seed"], record=True)
        out.append([chosen[t["seat"]] for _, chosen, _ in r["log"]])
    a, b = out
    first = next((k for k in range(len(a)) if a[k] != b[k]), None)
    return first, len(a)


if __name__ == "__main__":
    args = sys.argv[1:]
    maps = int(args[args.index("--maps") + 1]) if "--maps" in args else 30
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 41
    cands = [a for a in args if not a.startswith("--") and not a.isdigit()][:2]
    fx = arena.fixtures(fields.DEV_ALL, maps=maps, seed=seed)
    tasks = [dict(f, cands=cands) for f in fx]
    same = turns = 0
    diffs = []
    with mp.Pool(4) as pool:
        for first, n in pool.imap_unordered(job, tasks, chunksize=2):
            turns += n
            if first is None:
                same += 1
            else:
                diffs.append(first + 1)
    print("%s vs %s: %d/%d games identical move for move (%d decisions)%s" % (
        cands[0], cands[1], same, len(tasks), turns, "" if not diffs else "; first differing turns: %s" % sorted(diffs)[:20]))
