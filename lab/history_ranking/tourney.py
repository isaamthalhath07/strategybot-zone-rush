"""Staged tournament over every distinct bot in the repository's history.
R1: all bots x 16 games -> R2: top 200 + whole own-bot lineage x 32 -> R3: top 64 x 96 -> R4 finals: top 16 x 576 fresh games.
Then a round-robin league among the 16 finalists. All games: current confirmed rules (STAY-only Shield),
process-isolated seats, 200 ms/turn enforced. Finals ranking uses only fresh R4 + league games."""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner
SP = os.path.dirname(os.path.abspath(__file__))
CANDS = json.load(open(SP + "/cands.json"))["cands"]
P = lambda cid: CANDS[cid]["path"]
FIELDS = {
    "house":       ["e8b3682d8b39", "1bb70109a75e", "641c909b7ef1"],   # current root bot, Blocker, Apex
    "alt_arch":    ["a8f7a74e7ed3", "720e5a3daf7b", "5f1bb9f70aac"],   # Ultimate, Fusion, Zenith
    "independent": ["a6c0c5abcded", "2a9fa5c1127f", "0db330d2bb63"],   # opp_raider_03, opp_adaptive_02, opp_farmer_04
    "llm_pasted":  ["0b826e99381a", "d14526f372e3", "dc6cf21af88d"],   # opp_planner_gpt1, opp_opportunist_gemini1, opp_greedy_gpt1
    # two extra fields used only in the finals
    "shield_bait": ["42e759b51db9", "8fb32ee24081", "f95dc9fc2266"],   # opp_shield_03, opp_bait_01, Feint
    "racers":      ["a35c2c481164", "d44e9ce2fa35", "3ad8ac8c48a2"],   # Racer, opp_planner_gemini1, opp_raider_gpt1
}
def maps(first, n):
    out, seen, s = [], set(), first
    while len(out) < n:
        b = runner.random_map(s); k = tuple(b)
        if k not in seen: seen.add(k); out.append((s, b))
        s += 1
    return out
def fixtures(stage, map_first, n_maps, fields, combos_fn):
    fx = []
    for mi, (seed, base) in enumerate(maps(map_first, n_maps)):
        for fi, f in enumerate(fields):
            for seat, token in combos_fn(mi, fi):
                fx.append(dict(stage=stage, map=seed, base=base, field=f, seat=seat, token=token))
    return fx
def jobs_for(cids, fx):
    jobs = []
    for cid in cids:
        for x in fx:
            paths = [P(o) for o in FIELDS[x["field"]]]; paths.insert(x["seat"], P(cid))
            jobs.append(dict(id="%s|%s|%d|%s|%d|%d" % (x["stage"], cid, x["map"], x["field"], x["seat"], x["token"]), paths=paths, base=x["base"], token=x["token"],
                             meta=dict(cand=cid, stage=x["stage"], map=x["map"], field=x["field"], seat=x["seat"])))
    random.Random(7).shuffle(jobs)
    return jobs
def standings(results):
    agg = {}
    for r in results:
        m = r["meta"]; x = r["rec"][m["seat"]]
        a = agg.setdefault(m["cand"], dict(games=0, pw=0.0, score=0.0, faults=0, late=0, crash=0, illegal=0, max_ms=0.0, ms=0.0, calls=0))
        a["games"] += 1; a["pw"] += r["pw"][m["seat"]]; a["score"] += r["scores"][m["seat"]]
        for k in ("faults", "late", "crash", "illegal", "calls"): a[k] += x[k]
        a["ms"] += x["total_ms"]; a["max_ms"] = max(a["max_ms"], x["max_ms"])
    for a in agg.values():
        a["mean_pw"] = a["pw"] / a["games"]; a["mean_score"] = a["score"] / a["games"]
    return agg
def top(agg, n, pool=None):
    ks = [k for k in agg if pool is None or k in pool]
    return sorted(ks, key=lambda k: (-agg[k]["mean_pw"], -agg[k]["mean_score"]))[:n]
def merge(*aggs):
    out = {}
    for agg in aggs:
        for k, a in agg.items():
            o = out.setdefault(k, dict(games=0, pw=0.0, score=0.0, faults=0))
            o["games"] += a["games"]; o["pw"] += a["pw"]; o["score"] += a["score"]; o["faults"] += a["faults"]
    for o in out.values(): o["mean_pw"] = o["pw"] / o["games"]; o["mean_score"] = o["score"] / o["games"]
    return out
BASE4 = ["house", "alt_arch", "independent", "llm_pasted"]
ALL6 = BASE4 + ["shield_bait", "racers"]
if __name__ == "__main__":
    procs = 4
    allc = sorted(CANDS)
    # R1: 4 maps x 4 fields x 1 seat/token crossing = 16 games
    fx1 = fixtures("R1", 910001, 4, BASE4, lambda m, f: [((m + f) % 4, ((m + f) % 4 + (m - f)) % 4 + 1)])
    r1 = runner.run_jobs(jobs_for(allc, fx1), procs, "R1", SP + "/R1.jsonl", 1000)
    s1 = standings(r1); json.dump(s1, open(SP + "/S1.json", "w"))
    lineage = [k for k, c in CANDS.items() if c["git_paths"] and not all(p.startswith(("opponents/", "harness/bots/")) for p in c["git_paths"])]
    keep2 = sorted(set(top(s1, 200)) | set(lineage))
    print("R2 pool:", len(keep2), "(lineage %d)" % len(lineage), flush=True)
    # R2: 8 new maps x 4 fields x 1 crossing = 32 games
    fx2 = fixtures("R2", 920001, 8, BASE4, lambda m, f: [((m + 2 * f + 1) % 4, ((m + 2 * f + 1) % 4 + (m + f + 2)) % 4 + 1)])
    r2 = runner.run_jobs(jobs_for(keep2, fx2), procs, "R2", SP + "/R2.jsonl", 1000)
    s2 = standings(r2); json.dump(s2, open(SP + "/S2.json", "w"))
    c12 = merge({k: v for k, v in s1.items() if k in s2}, s2)
    keep3 = top(c12, 64)
    # R3: 6 new maps x 4 fields x 4 crossings = 96 games
    fx3 = fixtures("R3", 930001, 6, BASE4, lambda m, f: [(s, (s + m + f + s // 2) % 4 + 1) for s in range(4)])
    r3 = runner.run_jobs(jobs_for(keep3, fx3), procs, "R3", SP + "/R3.jsonl", 1000)
    s3 = standings(r3); json.dump(s3, open(SP + "/S3.json", "w"))
    c123 = merge({k: v for k, v in c12.items() if k in s3}, s3)
    finalists = top(c123, 16)
    # always carry the shipped root bot and the repo's own named leaders into the finals, then fill to 20 by rank
    for ref in ["e8b3682d8b39", "1bb70109a75e", "f95dc9fc2266", "a8f7a74e7ed3"] + top(c123, 64):
        if len(finalists) >= 20: break
        if ref not in finalists: finalists.append(ref)
    json.dump(dict(keep2=keep2, keep3=keep3, finalists=finalists), open(SP + "/pools.json", "w"))
    print("finalists:", finalists, flush=True)
    # R4 finals: 12 fresh maps x 6 fields x 8 crossings = 576 games each
    fx4 = fixtures("R4", 940001, 12, ALL6, lambda m, f: [(s, t) for s in range(4) for t in range(1, 5) if (s + t) % 2 == (m + f) % 2])
    r4 = runner.run_jobs(jobs_for(finalists, fx4), procs, "R4", SP + "/R4.jsonl", 1000)
    s4 = standings(r4); json.dump(s4, open(SP + "/S4.json", "w"))
    # League: finalists against each other, 4 distinct finalists per game, 16 fresh maps
    rng = random.Random(20261110); lmaps = maps(950001, 16); lj = []
    for rnd in range(400):
        order = list(finalists); rng.shuffle(order)
        for pod in range(len(order) // 4):
            four = order[pod * 4: pod * 4 + 4]
            seed, base = lmaps[(rnd * 4 + pod) % len(lmaps)]
            lj.append(dict(id="L|%d|%d" % (rnd, pod), paths=[P(c) for c in four], base=base, token=rng.randint(1, 4), meta=dict(stage="L", cands=four, map=seed)))
    rl = runner.run_jobs(lj, procs, "League", SP + "/L.jsonl", 500)
    print("DONE", flush=True)
