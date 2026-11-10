"""Turn the stage result files into rankings: finals table (fresh R4 games + league), paired comparisons, full 595-bot ranking."""
import json, os, sys, random, collections, csv
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import names as N
CANDS = N.CANDS
ARCH = json.load(open(SP + "/arch.json")) if os.path.exists(SP + "/arch.json") else {}
def load(stage):
    p = SP + "/%s.jsonl" % stage
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
def focal_rows(res):
    rows = []
    for r in res:
        m = r["meta"]; x = r["rec"][m["seat"]]
        rows.append(dict(cand=m["cand"], stage=m["stage"], map=m["map"], field=m["field"], seat=m["seat"], pw=r["pw"][m["seat"]], score=r["scores"][m["seat"]],
                         place=1 + sum(1 for s in r["scores"] if s > r["scores"][m["seat"]]), faults=x["faults"], late=x["late"], crash=x["crash"], illegal=x["illegal"],
                         max_ms=x["max_ms"], ms=x["total_ms"], calls=x["calls"], fid=r["id"].split("|", 2)[2]))
    return rows
def boot_ci(cluster_means, n=5000, seed=1):
    rng = random.Random(seed); k = len(cluster_means)
    if k < 2: return (float("nan"), float("nan"))
    b = sorted(sum(rng.choice(cluster_means) for _ in range(k)) / k for _ in range(n))
    return (b[int(0.025 * n)], b[int(0.975 * n) - 1])
def summarize(rows):
    by = collections.defaultdict(list)
    for r in rows: by[r["cand"]].append(r)
    out = {}
    for c, rs in by.items():
        n = len(rs)
        maps = collections.defaultdict(list)
        for r in rs: maps[r["map"]].append(r["pw"])
        fields = collections.defaultdict(list)
        for r in rs: fields[r["field"]].append(r["pw"])
        out[c] = dict(games=n, pw=sum(r["pw"] for r in rs) / n, score=sum(r["score"] for r in rs) / n, win=sum(r["place"] == 1 for r in rs) / n,
                      last=sum(r["pw"] == 0 for r in rs) / n, faults=sum(r["faults"] for r in rs), late=sum(r["late"] for r in rs), crash=sum(r["crash"] for r in rs),
                      illegal=sum(r["illegal"] for r in rs), max_ms=max(r["max_ms"] for r in rs), mean_ms=sum(r["ms"] for r in rs) / max(1, sum(r["calls"] for r in rs)),
                      ci=boot_ci([sum(v) / len(v) for v in maps.values()]), fields={f: sum(v) / len(v) for f, v in fields.items()})
    return out
def league(res):
    by = collections.defaultdict(lambda: dict(games=0, pw=0.0, score=0.0, win=0, faults=0, pws=[]))
    h2h = collections.defaultdict(lambda: [0.0, 0])
    for r in res:
        cs = r["meta"]["cands"]
        for i, c in enumerate(cs):
            a = by[c]; a["games"] += 1; a["pw"] += r["pw"][i]; a["score"] += r["scores"][i]; a["pws"].append(r["pw"][i])
            a["win"] += (r["scores"][i] == max(r["scores"])); a["faults"] += r["rec"][i]["faults"]
            for j, d in enumerate(cs):
                if i != j:
                    h = h2h[(c, d)]; h[0] += 1.0 if r["scores"][i] > r["scores"][j] else 0.5 if r["scores"][i] == r["scores"][j] else 0.0; h[1] += 1
    out = {}
    for c, a in by.items():
        n = a["games"]; rng = random.Random(3); p = a["pws"]
        b = sorted(sum(rng.choice(p) for _ in range(n)) / n for _ in range(2000))
        out[c] = dict(games=n, pw=a["pw"] / n, score=a["score"] / n, win=a["win"] / n, faults=a["faults"], ci=(b[50], b[1949]))
    return out, h2h
def paired(rows, a, b):
    A = {r["fid"]: r for r in rows if r["cand"] == a}; B = {r["fid"]: r for r in rows if r["cand"] == b}
    cl = collections.defaultdict(list)
    for k in A.keys() & B.keys(): cl[A[k]["map"]].append(A[k]["pw"] - B[k]["pw"])
    means = [sum(v) / len(v) for v in cl.values()]
    if not means: return None
    return dict(mean=sum(means) / len(means), ci=boot_ci(means, seed=5), n=sum(len(v) for v in cl.values()))
if __name__ == "__main__":
    stages = {s: focal_rows(load(s)) for s in ("R1", "R2", "R3", "R4")}
    S = {s: summarize(r) for s, r in stages.items()}
    for s in S: print(s, "bots", len(S[s]), "games", len(stages[s]))
    Lg, h2h = league(load("L"))
    json.dump(dict(S=S, L=Lg), open(SP + "/summary.json", "w"))
