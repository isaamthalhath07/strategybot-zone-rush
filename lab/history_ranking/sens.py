"""Sensitivity: the same policies under the superseded 'presence' Shield reading (catch_requires_stay=False)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner, tourney as T
SP = os.path.dirname(os.path.abspath(__file__))
POL = ["a35c2c481164", "1bb70109a75e", "f95dc9fc2266", "e8b3682d8b39", "fc00af81fdf7", "def6a8585f26", "8e84ff655452", "5f1bb9f70aac", "a8f7a74e7ed3", "d75575389253"]
fx = T.fixtures("SP", 960001, 6, T.BASE4, lambda m, f: [(s, t) for s in range(4) for t in range(1, 5) if (s + t) % 2 == (m + f) % 2])
jobs = T.jobs_for(POL, fx)
for j in jobs: j["rules"] = {"catch_requires_stay": False}
if __name__ == "__main__":
    res = runner.run_jobs(jobs, 4, "presence-rule", SP + "/SP.jsonl", 500)
    print("DONE")
