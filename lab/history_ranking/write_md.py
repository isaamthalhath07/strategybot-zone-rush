"""Write RANKING.md (human-readable full report) next to full_ranking.csv."""
import json, os, sys, csv, collections
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import names as N, analyze as A
rows = list(csv.DictReader(open(SP + "/full_ranking.csv")))
pooled = json.load(open(SP + "/pooled.json"))
stages = {s: A.focal_rows(A.load(s)) for s in ("R4",)}
S4 = A.summarize(stages["R4"])
Lg, _ = A.league(A.load("L"))
sp_rows = A.focal_rows(A.load("SP")); SPS = A.summarize(sp_rows) if sp_rows else {}
FIELDS = ["house", "alt_arch", "independent", "llm_pasted", "shield_bait", "racers"]
FDESC = {"house": "current main bot.py, Blocker, Apex", "alt_arch": "UltimateBot, Fusion, Zenith", "independent": "opp_raider_03, opp_adaptive_02, opp_farmer_04",
         "llm_pasted": "opp_planner_gpt1, opp_opportunist_gemini1, opp_greedy_gpt1", "shield_bait": "opp_shield_03, opp_bait_01, Feint", "racers": "Racer, opp_planner_gemini1, opp_raider_gpt1"}
out = []
w = out.append
w("# Zone Rush: every bot in the repository's history, ranked\n")
w("Generated 2026-11-10. 595 distinct playable `act(state)` sources (by SHA-256) from all 60 commits on all 13 branches, plus bot sources stored inside zip archives committed in history. "
  "35,616 games / 11.4 M timed callbacks on the repo's pinned referee (`simulator/vendor_harness`), current confirmed rules (STAY-only Shield), one isolated process per seat, 200 ms per turn enforced.\n")
w("Metric: **opponents outscored per game (0-3)**, ties count half. 1.5 is break-even in a field of equals.\n")
w("## 1. Finals: distinct policies (seed-only clones merged)\n")
w("Each file played 576 fresh games: 12 new maps x 6 opponent line-ups x 8 seat/priority-token crossings. League = 2,000 games among the 20 finalist files (13 of them are Blocker/Racer/Feint code, so it mostly measures play against that family).\n")
w("| # | Policy | Files | Fixed-field score (95% CI) | 1st place | League | Faults |\n|---|---|---:|---|---:|---:|---:|")
for i, (g, p) in enumerate(sorted(pooled.items(), key=lambda kv: -kv[1]["pw"])):
    w("| %d | %s | %d | **%.3f** [%.2f, %.2f] | %.0f%% | %.3f | %d |" % (i + 1, g, p["n_files"], p["pw"], p["ci"][0], p["ci"][1], 100 * p["win"], p["league"], p["faults"]))
w("\nPer line-up (fixed-field score):\n")
w("| Policy | " + " | ".join(FIELDS) + " |\n|---|" + "---:|" * len(FIELDS))
for g, p in sorted(pooled.items(), key=lambda kv: -kv[1]["pw"]):
    w("| %s | " % g + " | ".join("%.2f" % p["fields"][f] for f in FIELDS) + " |")
w("\nLine-ups: " + "; ".join("**%s** = %s" % (f, FDESC[f]) for f in FIELDS) + ".\n")
w("## 2. Finals: all 20 files\n")
w("| Rank | SHA-256 (12) | Bot | Fixed-field (95% CI) | League (95% CI) | Max ms | Where |\n|---:|---|---|---|---|---:|---|")
for r in rows[:20]:
    c = r["id_sha256_12"]; a = S4[c]; l = Lg[c]
    w("| %s | `%s` | %s | %.3f [%.2f, %.2f] | %.3f [%.2f, %.2f] | %.0f | %s |" % (r["rank"], c, r["name"], a["pw"], a["ci"][0], a["ci"][1], l["pw"], l["ci"][0], l["ci"][1], a["max_ms"], r["where"]))
w("\nFiles 1-12 are one code base (Blocker/Racer/Feint). Eight of them are byte-for-byte Racer or Blocker with a different random seed for one seat; their spread shows the noise level.\n")
if SPS:
    w("## 3. Sensitivity: superseded 'presence' Shield reading (`catch_requires_stay=False`)\n")
    w("192 games each (6 maps x 4 line-ups x 8 crossings). Not the confirmed rule; shown only to see whether the order depends on it.\n")
    w("| Bot | Score (95% CI) | Faults |\n|---|---|---:|")
    for c, a in sorted(SPS.items(), key=lambda kv: -kv[1]["pw"]):
        w("| %s | %.3f [%.2f, %.2f] | %d |" % (N.name(c), a["pw"], a["ci"][0], a["ci"][1], a["faults"]))
    w("")
w("## 4. Every root `bot.py` ever committed\n")
w("| Commit | Date | Rank / 595 | Screening score (games) | Architecture | Commit subject |\n|---|---|---:|---|---|---|")
byid = {r["id_sha256_12"]: r for r in rows}
for sha, v in sorted(N.ROOT.items(), key=lambda kv: kv[1][0]["date"]):
    if v[0]["path"] != "bot.py" or sha not in byid: continue
    r = byid[sha]
    w("| `%s` | %s | %s | %s (%s) | %s | %s |" % (v[0]["commit"], v[0]["date"][:10], r["rank"], r["screen_pw"], r["screen_games"], r["architecture"], v[0]["subject"][:80]))
w("\n## 5. Root `bot.py` at each branch head\n")
w("| Branch | Head | Date | bot.py SHA | Rank / 595 | Screening score |\n|---|---|---|---|---:|---:|")
for b, h in sorted(N.HEADS.items(), key=lambda kv: kv[1]["date"]):
    r = byid.get(h["bot_sha"])
    w("| `%s` | `%s` | %s | `%s` | %s | %s |" % (b, h["commit"], h["date"][:10], h["bot_sha"], r["rank"] if r else "-", r["screen_pw"] if r else "-"))
w("\n## 6. Full ranking (all 595)\n")
w("Finalists are ordered by the mean of fixed-field and league score; everything below by screening score within the stage it reached (R3 = 144 games, R2 = 48, R1 = 16). Lower tiers have wide error bars (about +/-0.15 at 144 games, +/-0.25 at 48, +/-0.4 at 16).\n")
w("| Rank | SHA-256 (12) | Bot | Family | Architecture | Stage | Screening score | Games | Faults | Where |\n|---:|---|---|---|---|---|---:|---:|---:|---|")
for r in rows:
    w("| %s | `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (r["rank"], r["id_sha256_12"], r["name"][:70], r["family"], r["architecture"], r["stage_reached"], r["screen_pw"], r["screen_games"], r["faults"], r["where"][:110]))
open(SP + "/RANKING.md", "w").write("\n".join(out) + "\n")
print("wrote", SP + "/RANKING.md", len(out), "lines")
if SPS:
    for c, a in sorted(SPS.items(), key=lambda kv: -kv[1]["pw"]): print("%-52s %.3f [%.2f,%.2f] g=%d f=%d" % (N.name(c)[:52], a["pw"], a["ci"][0], a["ci"][1], a["games"], a["faults"]))
