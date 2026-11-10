"""Assemble the external test opponents: bots from this repository's history that were
never in lab/pool, so the candidate was never developed against them.

  python3 lab/make_ext.py

Needs the corpus built by lab/history_ranking (build_corpus.py, prep.py, make_cands.py,
arch.py). Writes one standalone file per bot to lab/ext/ plus lab/ext/index.json, and
lab/ext/split.json: a seeded, stratified split into EXT1 (the test) and EXT2 (a reserve
that stays untouched unless a second confirmation is needed).

Groups, and who wrote them:
  gpt, gemini   pasted from ChatGPT and Gemini (opponents/ on the combined branch)
  gen           procedurally generated challengers of 12 families that lab/pool has no
                member of (written by an earlier Codex session)
  rival         six small behavioural families from the evolution league
  outsider      eight designs written from the rulebook for the crossfield review
  indep         two independently designed challengers (farmer, raider)
  hx            six "human-like" exploiters from the Apex/Zenith work
  zenith        Zenith, the strongest bot of that line
"""
import hashlib
import json
import os
import random
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HR = os.path.join(HERE, "history_ranking")
EXT = os.path.join(HERE, "ext")
SEED = 20261111


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_show(ref, path):
    return subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)], capture_output=True, check=True).stdout


def main():
    os.makedirs(EXT, exist_ok=True)
    cands = json.load(open(os.path.join(HR, "cands.json")))["cands"]
    arch = json.load(open(os.path.join(HR, "arch.json")))
    pool = set(sha(open(os.path.join(HERE, "pool", f), "rb").read()) for f in os.listdir(os.path.join(HERE, "pool"))
               if f.endswith(".py"))
    pool_families = set()
    for f in os.listdir(os.path.join(HERE, "pool")):
        if f.startswith("n_"):
            m = re.search(r"'family': '(\w+)'", open(os.path.join(HERE, "pool", f)).read())
            if m:
                pool_families.add(m.group(1))
    rnd = random.Random(SEED)
    out = {}        # name -> (group, bytes, origin)

    def read(cid):
        return open(os.path.join(HR, "corpus", cid + ".py"), "rb").read()

    # 1. pasted ChatGPT / Gemini bots, in their latest committed form
    listing = subprocess.run(["git", "-C", ROOT, "ls-tree", "--name-only", "origin/combined", "opponents/"],
                             capture_output=True, check=True, text=True).stdout.split()
    for path in sorted(listing):
        base = os.path.basename(path)[:-3]
        m = re.match(r"opp_(\w+)_(gpt|gemini)(\d)$", base)
        if not m:
            continue
        data = git_show("origin/combined", path)
        out["x_%s_%s%s" % (m.group(2), m.group(1), m.group(3))] = (m.group(2), data, "origin/combined:" + path)

    # 2. generated challengers from families the pool has no member of
    fam = {}
    for cid, a in arch.items():
        if a != 0 or cid not in cands:
            continue
        m = re.search(r"'family': '(\w+)'", read(cid).decode("utf8"))
        if m and m.group(1) not in pool_families:
            fam.setdefault(m.group(1), []).append(cid)
    for family in sorted(fam):
        ids = sorted(fam[family])
        rnd.shuffle(ids)
        for k, cid in enumerate(ids[:4]):
            out["x_gen_%s_%d" % (family, k)] = ("gen", read(cid), "archive " + cid)

    # 3. evolution-league rivals, one per behavioural family
    fam = {}
    for cid, a in arch.items():
        if a == 3 and cid in cands:
            m = re.search(r"'family': '(\w+)'", read(cid).decode("utf8"))
            fam.setdefault(m.group(1), []).append(cid)
    for family in sorted(fam):
        ids = sorted(fam[family])
        rnd.shuffle(ids)
        out["x_rival_%s" % family] = ("rival", read(ids[0]), "archive " + ids[0])

    # 4. outsiders (one class per file) and the two independent challengers
    for cid, a in sorted(arch.items()):
        if cid not in cands:
            continue
        if a == 9:
            m = re.search(r"_PLAYERS\[s\] = _out_(\w+)\(", read(cid).decode("utf8"))
            out["x_outsider_%s" % m.group(1).lower()] = ("outsider", read(cid), "archive " + cid)
        elif a == 26:
            m = re.search(r"_PLAYERS\[seat\] = _m5_Independent(\w+)\(", read(cid).decode("utf8"))
            out["x_indep_%s" % m.group(1).lower()] = ("indep", read(cid), "archive " + cid)

    # 5. human-like exploiters, flattened to one file each (they exec two sibling files)
    hx = "zenith/lab/humanlike/"
    evosim = git_show("a5b462f", "apex/src/evosim.py").decode("utf8")
    core = git_show("a5b462f", hx + "_hxcore.py").decode("utf8")
    cut = re.search(r"_EVO_SRC = .*?exec\(compile\(_ef\.read\(\), _EVO_SRC, \"exec\"\)\)\n", core, re.S)
    assert cut, "unexpected _hxcore.py layout"
    core = core[:cut.start()] + core[cut.end():]
    for style in ("steady", "bait", "cdsnipe", "aggro", "sniper", "mixed"):
        src = ("# Flattened from %shx_%s.py, _hxcore.py and apex/src/evosim.py at a5b462f.\n" % (hx, style)
               + evosim + "\n\n" + core + "\nSTYLE = %r\n" % style)
        out["x_hx_%s" % style] = ("hx", src.encode("utf8"), "a5b462f:%shx_%s.py (flattened)" % (hx, style))

    # 6. Zenith
    out["x_zenith"] = ("zenith", git_show("a5b462f", "zenith/zenith_bot.py"), "a5b462f:zenith/zenith_bot.py")

    index, groups = {}, {}
    for name in sorted(out):
        group, data, origin = out[name]
        if sha(data) in pool:
            continue                      # already known to the candidate's development
        open(os.path.join(EXT, name + ".py"), "wb").write(data)
        index[name] = dict(group=group, sha256=sha(data), bytes=len(data), origin=origin)
        groups.setdefault(group, []).append(name)
    json.dump(index, open(os.path.join(EXT, "index.json"), "w"), indent=1, sort_keys=True)

    split = {"EXT1": [], "EXT2": [], "seed": SEED}
    for group in sorted(groups):
        names = sorted(groups[group])
        rnd.shuffle(names)
        if group == "gen":                # split whole families, so EXT2 holds families EXT1 never shows
            fams = sorted(set(n.rsplit("_", 1)[0] for n in names))
            rnd.shuffle(fams)
            first = set(fams[: (len(fams) + 1) // 2])
            for n in sorted(names):
                split["EXT1" if n.rsplit("_", 1)[0] in first else "EXT2"].append(n)
        else:
            half = (len(names) + 1) // 2
            split["EXT1"] += sorted(names[:half])
            split["EXT2"] += sorted(names[half:])
    json.dump(split, open(os.path.join(EXT, "split.json"), "w"), indent=1)
    print("external bots: %d  (EXT1 %d, EXT2 %d)" % (len(index), len(split["EXT1"]), len(split["EXT2"])))
    for group in sorted(groups):
        print("  %-9s %3d" % (group, len(groups[group])))


if __name__ == "__main__":
    main()
