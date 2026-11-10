import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner
SP = os.path.dirname(os.path.abspath(__file__))
R = runner.REPO
cands = json.load(open(SP + "/cands.json"))["cands"]
opp = [R + "/bot.py", R + "/tester_bots/blocker.py", R + "/tester_bots/transfer_previous.py"]
jobs = []
for cid, c in sorted(cands.items()):
    for g, (seat, token, base) in enumerate([(0, 1, runner.example_map()), (2, 3, runner.random_map(4242))]):
        paths = list(opp); paths.insert(seat, c["path"])
        jobs.append(dict(id="%s:%d" % (cid, g), paths=paths, base=base, token=token, meta=dict(cand=cid, seat=seat)))
if __name__ == "__main__":
    res = runner.run_jobs(jobs, procs=3, label="smoke", out_path=SP + "/smoke.jsonl", progress_every=300)
    agg = {}
    for r in res:
        cid = r["meta"]["cand"]; x = r["rec"][r["meta"]["seat"]]
        a = agg.setdefault(cid, dict(games=0, faults=0, late=0, crash=0, illegal=0, other=0, max_ms=0, first_ms=0, total_ms=0, calls=0, pw=0, err=None))
        a["games"] += 1
        for k in ("faults", "late", "crash", "illegal", "other", "total_ms", "calls"): a[k] += x[k]
        a["max_ms"] = max(a["max_ms"], x["max_ms"]); a["first_ms"] = max(a["first_ms"], x.get("first_ms", 0))
        a["pw"] += r["pw"][r["meta"]["seat"]]
        if x["first_error"] and not a["err"]: a["err"] = x["first_error"]
    json.dump(agg, open(SP + "/smoke_agg.json", "w"), indent=1)
    bad = {k: v for k, v in agg.items() if v["faults"]}
    print("candidates:", len(agg), "with faults:", len(bad))
    slow = sorted(agg.items(), key=lambda kv: -kv[1]["max_ms"])[:25]
    print("slowest (max ms after first call / first call ms / mean ms):")
    for k, v in slow: print("  ", k, round(v["max_ms"], 1), round(v["first_ms"], 1), round(v["total_ms"] / max(1, v["calls"]), 2), cands[k]["git_paths"][:1] or cands[k]["zip_paths"][:1])
    print("faulty:")
    for k, v in sorted(bad.items(), key=lambda kv: -kv[1]["faults"]):
        print("  ", k, {x: v[x] for x in ("faults", "late", "crash", "illegal", "other")}, (cands[k]["git_paths"][:1] or [z.split("!")[-1] for z in cands[k]["zip_paths"][:1]]), "|", (v["err"] or "")[-160:].replace("\n", " "))
