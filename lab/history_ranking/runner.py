"""Tournament runner built on the repository's own pinned referee/worker (simulator/vendor_harness).
Every seat is a fresh isolated process per game; each bot only receives the four public fields.
Timing matches the repo benchmark: 2000 ms first call, 200 ms per later call, enforced (late -> STAY)."""
import os, sys, time, json, hashlib
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(REPO, "simulator", "vendor_harness")
sys.path.insert(0, VENDOR)
from match import BotProcess, DEFAULT_TIMING   # noqa: E402
from referee import DEFAULT_RULES, Referee, pairwise, random_map, example_map  # noqa: E402

TIMING = dict(DEFAULT_TIMING, hard_s=1.0, load_s=5.0)
RULES = dict(DEFAULT_RULES)          # catch_requires_stay=True: the confirmed STAY-only Shield rule
assert RULES["catch_requires_stay"] is True

def play(job):
    """job: dict(id, paths[4], base[64], token, rules(optional), keep_actions(optional))"""
    paths = job["paths"]
    rules = dict(RULES, **(job.get("rules") or {}))
    workers = [BotProcess(p) for p in paths]
    rec = [dict(calls=0, total_ms=0.0, max_ms=0.0, faults=0, late=0, crash=0, illegal=0, other=0, first_error=None) for _ in paths]
    t0 = time.perf_counter()
    try:
        for w in workers: w.spawn()
        for s, w in enumerate(workers):
            loaded = w.finish_load(TIMING["load_s"])
            if not loaded["ok"]:
                rec[s]["faults"] += 1; rec[s]["other"] += 1
                rec[s]["first_error"] = "load: " + str(loaded["error"])[-600:]
        game = Referee(job["base"], rules=rules, start_token=job["token"])
        while not game.over():
            chosen = []
            for s, w in enumerate(workers):
                obs = game.observation(s + 1)
                r = w.act(obs, game.turn, TIMING)
                rr = rec[s]
                rr["calls"] += 1
                ms = r.get("ms") or 0.0
                rr["total_ms"] += ms
                if game.turn > 1: rr["max_ms"] = max(rr["max_ms"], ms)
                else: rr["first_ms"] = ms
                if r["status"] != "ok":
                    rr["faults"] += 1
                    k = r["status"] if r["status"] in ("late", "crash", "illegal") else "other"
                    rr[k] += 1
                    if rr["first_error"] is None:
                        rr["first_error"] = "t%d %s: %s" % (game.turn, r["status"], (str(r.get("error") or r.get("returned") or r.get("chosen")))[-500:])
                chosen.append(r["used"])
            game.step(chosen)
        pw = [3 * v for v in pairwise(game.score)]
        return dict(id=job["id"], scores=list(game.score), pw=pw, rec=rec, elapsed=time.perf_counter() - t0,
                    meta=job.get("meta"))
    finally:
        for w in workers:
            try: w.close()
            except Exception: pass

def run_jobs(jobs, procs=4, label="", out_path=None, progress_every=200):
    """Run jobs in a process pool; append results as JSON lines so a run can resume."""
    from multiprocessing import Pool
    done = {}
    if out_path and os.path.exists(out_path):
        for line in open(out_path):
            try:
                r = json.loads(line); done[r["id"]] = r
            except Exception: pass
    todo = [j for j in jobs if j["id"] not in done]
    t0 = time.perf_counter()
    f = open(out_path, "a") if out_path else None
    n = 0
    with Pool(procs) as pool:
        for r in pool.imap_unordered(play, todo, chunksize=1):
            done[r["id"]] = r; n += 1
            if f: f.write(json.dumps(r, separators=(",", ":")) + "\n"); f.flush()
            if n % progress_every == 0 or n == len(todo):
                el = time.perf_counter() - t0
                print("%s %d/%d games  %.0fs  (%.2f games/s, eta %.0fs)" % (label, n, len(todo), el, n / el, (len(todo) - n) * el / n), flush=True)
    if f: f.close()
    return [done[j["id"]] for j in jobs]
