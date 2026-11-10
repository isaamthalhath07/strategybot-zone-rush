"""The out-of-sample test. Every focal bot plays the identical fixtures against opponents
the candidate was never developed on, on fresh maps (half from map families that did not
exist during development), from every seat and token start.

  python3 lab/final_test.py --set EXT1 --out lab/results/test_ext1.json [--maps 48]
  python3 lab/final_test.py --report lab/results/test_ext1.json

The plan, the fields, the seeds and the shipping rule are fixed in
lab/PREREGISTRATION.md, committed before the first test game was played.
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arena  # noqa: E402
import fields  # noqa: E402
import sim  # noqa: E402

CANDIDATE = "zr5"
FOCALS = [CANDIDATE, "cur_e8", "a_novel_b_racer", "a_novel_b_blocker"]
SEED = {"EXT1": 5101, "EXT2": 6203}
FAMILIES = sim.FAMILIES + sim.NEW_FAMILIES            # 7 known, 7 new: alternated per map
RULE_VARIANTS = [("presence_catch", {"catch_requires_stay": False}),
                 ("home_not_upgradable", {"home_upgradable": False}),
                 ("claim_keeps_progress", {"claim_resets_progress": False}),
                 ("lost_contest_not_stay", {"lost_contest_is_stay": False}),
                 ("legal_omits_occupied", {"legal_excludes_occupied": True})]


def test_fields(which):
    split = json.load(open(os.path.join(HERE, "ext", "split.json")))
    index = json.load(open(os.path.join(HERE, "ext", "index.json")))
    ext = split[which]
    by = lambda *groups: [n for n in ext if index[n]["group"] in groups]
    stress = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "stress")) if f.endswith(".py"))
    half = stress[::2] if which == "EXT1" else stress[1::2]
    strong = by("hx", "zenith", "outsider", "indep")
    out = [("ai_pasted", by("gpt", "gemini")),
           ("generated", by("gen", "rival")),
           ("other_designs", strong),
           ("stress", half),
           ("unseen_mixed", ext + half)]
    if which == "EXT1":
        out = [("holdout_elite", fields.HOLDOUT_ELITE), ("holdout_rest", fields.HOLDOUT_MID + fields.HOLDOUT_WEAK)] + out
        out.append(("unseen_all", ext + half + fields.HOLDOUT_ALL))
    # a field in which other teams built something like the candidate itself
    out.append(("with_candidate", strong + (fields.HOLDOUT_ELITE if which == "EXT1" else []) + [CANDIDATE] * 4))
    return out


def run(which, maps, out_path, workers=4):
    plan = test_fields(which)
    data = dict(which=which, maps=maps, focals=FOCALS, seed=SEED[which], fields={}, rules={}, started=time.time())
    for k, (name, field) in enumerate(plan):
        fx = arena.fixtures(field, maps=maps, seed=SEED[which] + k, families=FAMILIES)
        per, err = arena.evaluate(FOCALS, fx, workers=workers)
        data["fields"][name] = dict(opponents=field, errors=err, fixtures=[dict(family=f["family"], map_id=f["map_id"]) for f in fx],
                                    per={c: {str(i): v for i, v in rows.items()} for c, rows in per.items()})
        print("%-16s %d fixtures x %d bots, errors %d, %.0fs" % (name, len(fx), len(FOCALS), err, time.time() - data["started"]), flush=True)
        json.dump(data, open(out_path, "w"))
    mixed = dict(plan)["unseen_mixed"]
    for k, (name, rules) in enumerate(RULE_VARIANTS):
        fx = arena.fixtures(mixed, maps=max(8, maps // 3), seed=SEED[which] + 100 + k, families=FAMILIES)
        per, err = arena.evaluate(FOCALS, fx, workers=workers, rules=rules)
        data["rules"][name] = dict(rules=rules, errors=err, fixtures=[dict(family=f["family"], map_id=f["map_id"]) for f in fx],
                                   per={c: {str(i): v for i, v in rows.items()} for c, rows in per.items()})
        print("rule %-22s errors %d, %.0fs" % (name, err, time.time() - data["started"]), flush=True)
        json.dump(data, open(out_path, "w"))
    data["elapsed"] = time.time() - data["started"]
    json.dump(data, open(out_path, "w"))
    return data


def paired(rows_a, rows_b, cluster_of, boot=4000, seed=7):
    """Mean of per-cluster mean differences, with a cluster bootstrap interval."""
    clusters = {}
    for key in set(rows_a) & set(rows_b):
        clusters.setdefault(cluster_of(key), []).append(rows_a[key][0] - rows_b[key][0])
    means = [sum(v) / len(v) for v in clusters.values()]
    if not means:
        return None
    rnd = random.Random(seed)
    n = len(means)
    bs = sorted(sum(rnd.choice(means) for _ in range(n)) / n for _ in range(boot))
    return sum(means) / n, bs[int(0.025 * boot)], bs[int(0.975 * boot) - 1], n


def report(path, quiet=False):
    data = json.load(open(path))
    focals = data["focals"]
    cand = focals[0]
    lines = []
    say = lines.append
    say("test set %s: %d maps per field, 4 fixtures per map, %d focal bots on identical fixtures" % (data["which"], data["maps"], len(focals)))
    pooled = {c: {} for c in focals}
    newmap = {c: {} for c in focals}
    oldmap = {c: {} for c in focals}
    summary = dict(fields={}, rules={})
    faults = {c: 0 for c in focals}
    say("\n%-16s %5s " % ("field", "games") + " ".join("%-9s" % c[-9:] for c in focals) + "   candidate minus each other bot (95% interval)")
    for name, blk in data["fields"].items():
        fx = blk["fixtures"]
        row = "%-16s %5d " % (name, len(fx))
        means = {}
        for c in focals:
            rows = blk["per"][c]
            means[c] = sum(v[0] for v in rows.values()) / len(rows)
            faults[c] += sum(v[3] for v in rows.values())
            row += "%-9.3f " % means[c]
            for i, v in rows.items():
                key = (name, int(i))
                if name not in ("unseen_all", "with_candidate"):      # those two re-use opponents; keep the pool disjoint
                    pooled[c][key] = v
                    (newmap if fx[int(i)]["family"] in sim.NEW_FAMILIES else oldmap)[c][key] = v
        diffs = {}
        for c in focals[1:]:
            d = paired(blk["per"][cand], blk["per"][c], lambda k: blk["per"][cand][k][2])
            diffs[c] = d
            row += "  %+.3f [%+.2f,%+.2f]" % d[:3]
        summary["fields"][name] = dict(means=means, diffs=diffs, games=len(fx))
        say(row)
    say("")
    for label, table in (("POOLED unseen", pooled), ("  known map families", oldmap), ("  new map families", newmap)):
        row = "%-21s" % label + " ".join("%-9.3f" % (sum(v[0] for v in table[c].values()) / max(1, len(table[c]))) for c in focals)
        diffs = {}
        for c in focals[1:]:
            d = paired(table[cand], table[c], lambda k: (k[0], data["fields"][k[0]]["per"][cand][str(k[1])][2]))
            diffs[c] = d
            row += "  %+.3f [%+.2f,%+.2f]" % d[:3]
        summary[label.strip()] = dict(means={c: sum(v[0] for v in table[c].values()) / max(1, len(table[c])) for c in focals},
                                      diffs=diffs, games=len(table[cand]))
        say(row + "   (%d games each)" % len(table[cand]))
    say("")
    for name, blk in data.get("rules", {}).items():
        row = "rule %-22s" % name
        means = {}
        for c in focals:
            rows = blk["per"][c]
            means[c] = sum(v[0] for v in rows.values()) / len(rows)
            faults[c] += sum(v[3] for v in rows.values())
            row += "%-9.3f " % means[c]
        diffs = {}
        for c in focals[1:]:
            d = paired(blk["per"][cand], blk["per"][c], lambda k: blk["per"][cand][k][2])
            diffs[c] = d
            row += "  %+.3f [%+.2f,%+.2f]" % d[:3]
        summary["rules"][name] = dict(means=means, diffs=diffs)
        say(row)
    say("\nfaults (exceptions or illegal answers) over every test game: " + ", ".join("%s %d" % (c, faults[c]) for c in focals))
    errors = sum(b["errors"] for b in data["fields"].values()) + sum(b["errors"] for b in data.get("rules", {}).values())
    say("games that failed to run: %d" % errors)
    summary["faults"] = faults
    summary["errors"] = errors
    if not quiet:
        print("\n".join(lines))
    return summary, "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--report" in args:
        report(args[args.index("--report") + 1])
    else:
        which = args[args.index("--set") + 1]
        maps = int(args[args.index("--maps") + 1]) if "--maps" in args else 48
        out = args[args.index("--out") + 1]
        run(which, maps, out)
        summary, text = report(out)
        open(out.replace(".json", ".txt"), "w").write(text + "\n")
