"""Apply the shipping rule of lab/PREREGISTRATION2.md to a finished EXT2 run.
  python3 lab/ext2_rule.py lab/results/test_ext2.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_test

if __name__ == "__main__":
    path = sys.argv[1]
    s, _ = final_test.report(path, quiet=True, cand="zr8")
    pooled = s["POOLED unseen"]
    disjoint = ("ai_pasted", "generated", "other_designs", "stress", "unseen_mixed")
    fmt = lambda d: "%+.3f [%+.3f, %+.3f]" % d[:3]
    rows = []
    d = s["fields"]["other_designs"]["diffs"]["zr6"]
    rows.append(("1 other_designs: zr8 - zr6 lower bound > 0", fmt(d), d[1] > 0))
    rows.append(("2 that lead is at least +0.13", "%+.3f" % d[0], d[0] >= 0.13))
    d = pooled["diffs"]["zr6"]
    rows.append(("3 pooled: zr8 not significantly below zr6", fmt(d), d[2] >= 0))
    bad = [(f, s["fields"][f]["diffs"]["zr6"]) for f in disjoint
           if s["fields"][f]["diffs"]["zr6"][0] < -0.08 and s["fields"][f]["diffs"]["zr6"][2] < 0]
    rows.append(("4 no field below zr6 by more than 0.08, significantly",
                 "; ".join("%s %s" % (f, fmt(x)) for f, x in bad) or "none", not bad))
    dr, db = pooled["diffs"]["a_novel_b_racer"], pooled["diffs"]["a_novel_b_blocker"]
    rows.append(("5 pooled: zr8 - Racer, zr8 - Blocker lower bounds > 0", fmt(dr) + " and " + fmt(db),
                 dr[1] > 0 and db[1] > 0))
    worse = [(n, r["diffs"]["zr6"]) for n, r in s["rules"].items() if r["diffs"]["zr6"][2] < 0]
    ok6 = s["faults"]["zr8"] == 0 and s["errors"] == 0 and not worse
    rows.append(("6 zero faults, zero failed games, no rule reading significantly below zr6",
                 "faults %d, failed %d, %s" % (s["faults"]["zr8"], s["errors"],
                                              "; ".join("%s %s" % (n, fmt(x)) for n, x in worse) or "none below"), ok6))
    for label, value, ok in rows:
        print("%-74s %-44s %s" % (label, value, "holds" if ok else "FAILS"))
    print("\nDECISION: %s" % ("ship zr8" if all(r[2] for r in rows) else "zr6 stays"))
