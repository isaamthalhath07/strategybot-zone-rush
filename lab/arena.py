"""Parallel league and paired-comparison runners built on lab/sim.py."""
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402


def _run(task):
    base = task.get("base") or sim.make_map(task["family"], task["mapseed"])
    try:
        res = sim.play(task["names"], base, token=task["token"], seed=task["seed"],
                       rules=task.get("rules"), timing=task.get("timing", False))
    except Exception as exc:  # a broken opponent must not kill a long run
        return dict(task=task, error=repr(exc))
    res["task"] = task
    return res


def run_tasks(tasks, workers=4, progress=None):
    out = []
    t0 = time.time()
    with mp.Pool(workers) as pool:
        for k, res in enumerate(pool.imap_unordered(_run, tasks, chunksize=4)):
            out.append(res)
            if progress and (k + 1) % progress == 0:
                print("  %d/%d games  %.0fs" % (k + 1, len(tasks), time.time() - t0), flush=True)
    return out


def league(names, games, seed=0, families=sim.FAMILIES, weights=None, workers=4, progress=None):
    """Random four-bot games drawn from `names`. Returns per-bot mean pairwise wins."""
    rnd = random.Random(seed)
    tasks = []
    for g in range(games):
        if weights:
            four = []
            while len(four) < 4:
                pick = rnd.choices(names, weights)[0]
                four.append(pick)
        else:
            four = [rnd.choice(names) for _ in range(4)]
        tasks.append(dict(names=four, family=rnd.choice(families), mapseed=rnd.randrange(10 ** 6),
                          token=rnd.randint(1, 4), seed=rnd.randrange(10 ** 9)))
    results = run_tasks(tasks, workers, progress)
    return results


def table(results):
    agg = {}
    for res in results:
        if "error" in res:
            continue
        for i, name in enumerate(res["task"]["names"]):
            row = agg.setdefault(name, [0, 0.0, 0.0, 0])
            row[0] += 1
            row[1] += res["pw"][i]
            row[2] += res["scores"][i]
            row[3] += res["faults"][i]
    rows = [(name, v[0], v[1] / v[0], v[2] / v[0], v[3]) for name, v in agg.items()]
    rows.sort(key=lambda r: -r[2])
    return rows


def fixtures(field, maps, seed=0, families=sim.FAMILIES, per_map=4):
    """Balanced fixtures: each map is played from every seat with a rotating token.

    `field` is a list of opponent names (triples are sampled) or a list of explicit
    triples. The same fixture list is replayed for every candidate, so comparisons
    are paired on map, seat, token, opponents and opponent RNG seeds.
    """
    rnd = random.Random(seed)
    out = []
    for m in range(maps):
        family = families[m % len(families)]
        mapseed = rnd.randrange(10 ** 6)
        for k in range(per_map):
            if field and isinstance(field[0], (list, tuple)):
                opp = list(rnd.choice(field))
            else:
                opp = [rnd.choice(field) for _ in range(3)]
            rnd.shuffle(opp)
            out.append(dict(family=family, mapseed=mapseed, seat=k % 4, token=1 + (k + m) % 4,
                            opponents=opp, seed=rnd.randrange(10 ** 9), map_id=m))
    return out


def evaluate(cands, fx, workers=4, progress=None, rules=None):
    tasks = []
    for fi, f in enumerate(fx):
        for c in cands:
            names = list(f["opponents"])
            names.insert(f["seat"], c)
            tasks.append(dict(names=names, family=f["family"], mapseed=f["mapseed"], token=f["token"],
                              seed=f["seed"], cand=c, fx=fi, seat=f["seat"], map_id=f["map_id"],
                              rules=rules))
    results = run_tasks(tasks, workers, progress)
    per = {c: {} for c in cands}
    errors = 0
    for res in results:
        if "error" in res:
            errors += 1
            continue
        t = res["task"]
        per[t["cand"]][t["fx"]] = (res["pw"][t["seat"]], res["scores"][t["seat"]], t["map_id"],
                                   res["faults"][t["seat"]])
    return per, errors


def summarize(per, ref=None, boot=2000, seed=1):
    """Mean PW per candidate and, against `ref`, the paired difference with a
    map-clustered bootstrap interval (whole maps are resampled)."""
    rnd = random.Random(seed)
    lines = []
    for c, rows in per.items():
        if not rows:
            continue
        n = len(rows)
        pw = sum(v[0] for v in rows.values()) / n
        sc = sum(v[1] for v in rows.values()) / n
        faults = sum(v[3] for v in rows.values())
        entry = dict(cand=c, n=n, pw=pw, score=sc, faults=faults)
        if ref and ref in per and c != ref:
            common = sorted(set(rows) & set(per[ref]))
            clusters = {}
            for k in common:
                clusters.setdefault(rows[k][2], []).append(rows[k][0] - per[ref][k][0])
            means = [sum(v) / len(v) for v in clusters.values()]
            if means:
                d = sum(means) / len(means)
                bs = sorted(sum(rnd.choice(means) for _ in means) / len(means) for _ in range(boot))
                entry.update(diff=d, lo=bs[int(0.025 * boot)], hi=bs[int(0.975 * boot)],
                             clusters=len(means))
        lines.append(entry)
    lines.sort(key=lambda e: -e["pw"])
    return lines


def show(lines):
    for e in lines:
        extra = ""
        if "diff" in e:
            extra = "  d=%+.3f [%+.3f,%+.3f] (%d maps)" % (e["diff"], e["lo"], e["hi"], e["clusters"])
        print("%-38s n=%-5d PW=%.3f score=%.0f faults=%d%s" % (e["cand"], e["n"], e["pw"], e["score"],
                                                              e["faults"], extra))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", type=int, default=0)
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.league:
        res = league(args.names, args.league, seed=args.seed, progress=200)
        rows = table(res)
        for r in rows:
            print("%-40s n=%-5d PW=%.3f score=%.0f faults=%d" % r)
        if args.out:
            json.dump(rows, open(args.out, "w"))
