"""Development suite, third generation: every opponent group separately, now that
nothing is held out any more (lab/PROGRESS.md section 15).

  python3 lab/suite3.py [--ref zr6] [--seed 2000] [--maps 30] [--only a,b] cand ...

The point of reporting groups separately: a change that helps one group and costs
another is fitted to that group. Sections 11 to 15 showed a gain against the strong bots
of this repository's own history that vanished against strong bots from elsewhere. A
change is only worth keeping if no group pays for it.

Groups
  hist_elite   17 strong bots from this repository's history (development + lab hold-out)
  ext1_strong  9 strong designs from elsewhere (first external half)
  ext2_strong  8 strong designs from elsewhere (second external half)
  hist_mid     mid-strength bots from the repository's history
  ext1_gen     generated families and rival types, first half
  ext2_gen     generated families and rival types, second half
  hist_weak    weak bots from the repository's history
  pasted       ChatGPT and Gemini bots (both halves)
  stress       all 14 stress bots
  everything   all of the above mixed
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena, fields, sim

HERE = os.path.dirname(os.path.abspath(__file__))
FAMS = sim.FAMILIES + sim.NEW_FAMILIES


def groups():
    split = json.load(open(os.path.join(HERE, "ext", "split.json")))
    index = json.load(open(os.path.join(HERE, "ext", "index.json")))
    by = lambda half, *g: [n for n in split[half] if index[n]["group"] in g]
    strong = ("hx", "zenith", "outsider", "indep")
    stress = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "stress")) if f.endswith(".py"))
    out = [("hist_elite", fields.HOLDOUT_ELITE + fields.DEV_ELITE),
           ("ext1_strong", by("EXT1", *strong)), ("ext2_strong", by("EXT2", *strong)),
           ("hist_mid", fields.DEV_MID + fields.HOLDOUT_MID),
           ("ext1_gen", by("EXT1", "gen", "rival")), ("ext2_gen", by("EXT2", "gen", "rival")),
           ("hist_weak", fields.DEV_WEAK + fields.HOLDOUT_WEAK),
           ("pasted", by("EXT1", "gpt", "gemini") + by("EXT2", "gpt", "gemini")),
           ("stress", stress)]
    out.append(("everything", [n for _, f in out for n in f]))
    return out


def run(cands, ref, seed=2000, maps=30, which=None, workers=4):
    allc = [ref] + [c for c in cands if c != ref]
    table, names = {}, []
    for k, (name, field) in enumerate(groups()):
        if which and name not in which:
            continue
        names.append(name)
        fx = arena.fixtures(field, maps=maps * (2 if name == "everything" else 1), seed=seed + k, families=FAMS)
        per, err = arena.evaluate(allc, fx, workers=workers)
        for e in arena.summarize(per, ref=ref):
            table.setdefault(e["cand"], {})[name] = e
    print("%-13s" % "group" + "%-9s" % ref[-8:] + "".join("%-26s" % c[-24:] for c in allc[1:]))
    for n in names:
        row = "%-13s%-9.3f" % (n, table[ref][n]["pw"])
        for c in allc[1:]:
            e = table[c][n]
            row += "%+.3f [%+.2f,%+.2f]      " % (e["diff"], e["lo"], e["hi"])
        print(row)
    worst = {c: min(table[c][n]["diff"] for n in names) for c in allc[1:]}
    mean = {c: sum(table[c][n]["diff"] for n in names if n != "everything") / max(1, len([n for n in names if n != "everything"])) for c in allc[1:]}
    print("%-22s" % "mean over groups" + "".join("%-26s" % ("%+.3f" % mean[c]) for c in allc[1:]))
    print("%-22s" % "worst group" + "".join("%-26s" % ("%+.3f" % worst[c]) for c in allc[1:]))
    return table


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = {"--ref": "zr6", "--seed": "2000", "--maps": "30", "--only": None}
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    t = time.time()
    run(args, opt["--ref"], int(opt["--seed"]), int(opt["--maps"]), opt["--only"].split(",") if opt["--only"] else None)
    print("%.0fs" % (time.time() - t))
