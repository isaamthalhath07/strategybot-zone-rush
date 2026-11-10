"""Write the full ranking (CSV + Markdown) from the tournament stage files."""
import json, os, sys, csv, collections
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import names as N, analyze as A
CANDS = N.CANDS
ARCH = json.load(open(SP + "/arch.json"))
ARCHNAME = {0: "generated 'Player' opponent", 1: "guarded Transfer (current main family)", 2: "simple act()-only bot", 3: "tiny evolved Rival",
            4: "mybot beam planner (v6-v9)", 5: "mybot beam planner (v3-v7)", 6: "novel-b core (Blocker/Racer/Feint)", 7: "Transfer / evolved economic planner",
            11: "presence Transfer", 12: "PR10 v9 forecast planner", 16: "futurelab forward-sim", 17: "Fusion (econ + beam fallback)", 18: "novel-d", 19: "novel-c", 20: "novel-a",
            22: "Apex/Zenith exact-copy predictor", 23: "fusion source", 25: "presence guarded"}
def arch(c): return ARCHNAME.get(ARCH.get(c, -1), "other #%s" % ARCH.get(c, "?"))
stages = {s: A.focal_rows(A.load(s)) for s in ("R1", "R2", "R3", "R4")}
S = {s: A.summarize(r) for s, r in stages.items()}
Lg, h2h = A.league(A.load("L"))
base_rows = stages["R1"] + stages["R2"] + stages["R3"]
CUM = A.summarize(base_rows)                      # all screening games vs the 4 base fields
def tier(c): return 4 if c in S["R4"] else 3 if c in S["R3"] else 2 if c in S["R2"] else 1
finalists = sorted(S["R4"], key=lambda c: -(S["R4"][c]["pw"] + (Lg[c]["pw"] if c in Lg else S["R4"][c]["pw"])) / 2)
def overall(c): return (S["R4"][c]["pw"] + Lg[c]["pw"]) / 2 if c in Lg else S["R4"][c]["pw"]
order = finalists + sorted([c for c in CUM if tier(c) == 3], key=lambda c: -CUM[c]["pw"]) \
                  + sorted([c for c in CUM if tier(c) == 2], key=lambda c: -CUM[c]["pw"]) \
                  + sorted([c for c in CUM if tier(c) == 1], key=lambda c: (-CUM[c]["pw"], -CUM[c]["score"]))
rank = {c: i + 1 for i, c in enumerate(order)}
json.dump(dict(order=order, rank=rank), open(SP + "/rank.json", "w"))
with open(SP + "/full_ranking.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rank", "id_sha256_12", "name", "family", "architecture", "stage_reached", "finals_pw", "finals_ci_lo", "finals_ci_hi", "league_pw", "overall_final",
                "screen_games", "screen_pw", "screen_mean_score", "faults", "max_ms", "bytes", "first_commit", "first_date", "where"])
    for c in order:
        r4 = S["R4"].get(c); cu = CUM[c]; lg = Lg.get(c)
        w.writerow([rank[c], c, N.name(c), N.family(c), arch(c), "finals" if r4 else "R%d" % tier(c),
                    "%.4f" % r4["pw"] if r4 else "", "%.3f" % r4["ci"][0] if r4 else "", "%.3f" % r4["ci"][1] if r4 else "", "%.4f" % lg["pw"] if lg else "",
                    "%.4f" % overall(c) if r4 else "", cu["games"], "%.4f" % cu["pw"], "%.1f" % cu["score"], cu["faults"] + (r4["faults"] if r4 else 0),
                    "%.1f" % max(cu["max_ms"], r4["max_ms"] if r4 else 0), CANDS[c]["size"], CANDS[c]["first_commit"], CANDS[c]["first_date"][:10], N.where(c)])
def line(c):
    r4 = S["R4"][c]; lg = Lg.get(c, dict(pw=float("nan"), ci=(float("nan"),) * 2, win=float("nan"), games=0))
    return "%2d  %-13s %-50s R4 %.3f [%.2f,%.2f] win %2.0f%%  score %6.0f | league %.3f [%.2f,%.2f] | overall %.3f | f=%d maxms=%.0f | %s" % (
        rank[c], c, N.name(c)[:50], r4["pw"], r4["ci"][0], r4["ci"][1], 100 * r4["win"], r4["score"], lg["pw"], lg["ci"][0], lg["ci"][1], overall(c), r4["faults"], r4["max_ms"], arch(c))
if __name__ == "__main__":
    print("games:", {s: len(v) for s, v in stages.items()}, "league", sum(v["games"] for v in Lg.values()) // 4)
    print("\n=== FINALS ===")
    for c in finalists: print(line(c))
    print("\nper-field R4 PW:")
    fields = ["house", "alt_arch", "independent", "llm_pasted", "shield_bait", "racers"]
    print(" " * 30 + "  ".join("%-11s" % f for f in fields))
    for c in finalists: print("%-30s" % N.name(c)[:30] + "  ".join("%-11.3f" % S["R4"][c]["fields"].get(f, float("nan")) for f in fields))
    if finalists:
        top = finalists[0]; print("\npaired R4 difference, #1 (%s) minus other, map-clustered 95%% CI:" % N.name(top))
        for c in finalists[1:]:
            p = A.paired(stages["R4"], top, c); print("   vs %-50s %+.3f [%+.3f, %+.3f]" % (N.name(c)[:50], p["mean"], p["ci"][0], p["ci"][1]))
    print("\n=== POOLED BY POLICY (seed-only clones merged) ===")
    groups = collections.defaultdict(list)
    for c in finalists: groups[N.policy(c) or N.name(c)].append(c)
    pooled = {}
    for g, cs in groups.items():
        rows = [dict(r, cand=g) for r in stages["R4"] if r["cand"] in cs]
        pooled[g] = A.summarize(rows)[g]
        lgs = [Lg[c] for c in cs if c in Lg]
        pooled[g]["league"] = sum(x["pw"] * x["games"] for x in lgs) / max(1, sum(x["games"] for x in lgs)) if lgs else float("nan")
        pooled[g]["league_games"] = sum(x["games"] for x in lgs)
        pooled[g]["n_files"] = len(cs)
    json.dump(pooled, open(SP + "/pooled.json", "w"))
    for g, p in sorted(pooled.items(), key=lambda kv: -(kv[1]["pw"] + kv[1]["league"]) / 2):
        print("%-52s files %d  R4 %.3f [%.2f,%.2f] (%4d g) win %2.0f%% last %2.0f%% score %5.0f | league %.3f (%4d g) | overall %.3f | f=%d" % (
            g[:52], p["n_files"], p["pw"], p["ci"][0], p["ci"][1], p["games"], 100 * p["win"], 100 * p["last"], p["score"], p["league"], p["league_games"], (p["pw"] + p["league"]) / 2, p["faults"]))
    def pooled_pair(ga, gb):
        fa = collections.defaultdict(list); fb = collections.defaultdict(list); mp = {}
        for r in stages["R4"]:
            if r["cand"] in groups[ga]: fa[r["fid"]].append(r["pw"]); mp[r["fid"]] = r["map"]
            if r["cand"] in groups[gb]: fb[r["fid"]].append(r["pw"]); mp[r["fid"]] = r["map"]
        cl = collections.defaultdict(list)
        for k in fa.keys() & fb.keys(): cl[mp[k]].append(sum(fa[k]) / len(fa[k]) - sum(fb[k]) / len(fb[k]))
        means = [sum(v) / len(v) for v in cl.values()]
        return sum(means) / len(means), A.boot_ci(means, seed=9)
    gs = sorted(pooled, key=lambda g: -(pooled[g]["pw"] + pooled[g]["league"]) / 2)
    print("paired R4 differences (map-clustered 95% CI):")
    for ga, gb in [(gs[0], g) for g in gs[1:]] + [("Blocker", "Racer")] + [(g, "CURRENT main bot.py (guarded Transfer, STAY-only)") for g in ("Racer", "Blocker", "Feint")]:
        if ga == gb or ga not in groups or gb not in groups: continue
        m, ci = pooled_pair(ga, gb); print("   %-40s minus %-52s %+.3f [%+.3f, %+.3f]" % (ga[:40], gb[:52], m, ci[0], ci[1]))
    print("\n=== ROOT bot.py HISTORY ===")
    for sha, v in sorted(N.ROOT.items(), key=lambda kv: kv[1][0]["date"]):
        if v[0]["path"] != "bot.py" or sha not in CUM: continue
        cu = CUM[sha]; r4 = S["R4"].get(sha)
        print("%-8s %s  rank %3d  screen %.3f (%d g)%s  f=%d | %s | %s" % (v[0]["commit"], v[0]["date"][:10], rank[sha], cu["pw"], cu["games"], "  finals %.3f" % r4["pw"] if r4 else "", cu["faults"], arch(sha), v[0]["subject"][:60]))
    print("\n=== BRANCH HEADS ===")
    for b, h in sorted(N.HEADS.items(), key=lambda kv: kv[1]["date"]):
        s = h["bot_sha"]; print("%-34s %s %s  bot %s  rank %s  screen %s" % (b, h["commit"], h["date"][:10], s, rank.get(s), "%.3f" % CUM[s]["pw"] if s in CUM else "-"))
    print("\n=== TOP 60 overall ===")
    for c in order[:60]:
        cu = CUM[c]; print("%3d %-13s %-48s %-22s tier%d screen %.3f (%3d g) f=%d" % (rank[c], c, N.name(c)[:48], N.family(c), tier(c), cu["pw"], cu["games"], cu["faults"]))
