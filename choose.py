"""
Pick the version to submit, on evidence rather than on training score.

A tuner's own number is the one thing that cannot be trusted to choose between
versions: it is the quantity that was maximised, on the task set it was maximised
over. So this re-measures every candidate three ways, each answering a different
question:

  realistic  paired games against the full mixed field -- the closest thing to
             the Round 1 field, weak entries included.
  peer       paired games against near-peers only. Far more sensitive, because
             every game is close; this is where a real improvement shows up.
  held-out   opponents that appear in no tuning field at all, to separate genuine
             strength from having fitted the training field.

A candidate ships only if it is at least level on all three. The version that won
on training score and lost everywhere else (v5) is why this script exists.

Named choose.py rather than select.py on purpose: a file called select.py in the
working directory shadows the standard library's select module, which
multiprocessing imports, and that silently broke every parallel script here.

    python choose.py [games] [name=file.json ...]
"""
import json
import os
import sys

import field as fieldmod
import measure
import mybot

# A tier of opponents that no tuning field contains, so no candidate can have
# been fitted to it.
HELDOUT = ["turtle", "hunter", "centre", "cdraider", "ai_route", "ai_centre",
           "pacifist", "greedy"]
TIERS = ("realistic", "peer", "heldout")


def candidates(args):
    if args:
        return [measure.load(a) for a in args]
    out = []
    for n, f in (("v3", "v3_params.json"), ("v6", "v6_params.json"),
                 ("v7", "v7_params.json"), ("v8", "v8_params.json")):
        if os.path.exists(f):
            p = dict(mybot.PARAMS)
            p.update(json.load(open(f)))
            # Pin the adaptive beam off. It reacts to wall-clock time, so with it
            # on the comparison depends on how loaded the machine was.
            p["throttle"] = 0
            out.append((n, p))
    return out


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 700
    variants = candidates(sys.argv[2:])
    if len(variants) < 2:
        raise SystemExit("need at least two candidates to compare")
    fieldmod.TIERS["heldout"] = list(HELDOUT)
    print("candidates: %s" % ", ".join(n for n, _ in variants))
    print("%d paired games per tier; every candidate plays the identical "
          "maps, seats and line-ups\n" % games)

    summary = {}
    for tier in TIERS:
        tasks = measure.make_tasks(games, tier, seed=4242)
        res = measure.run(variants, tasks)
        measure.report(variants, res, label="[%s]" % tier)
        for n, _ in variants:
            b = res[n]
            summary.setdefault(n, {})[tier] = sum(x[0] for x in b) / float(len(b))

    ref = variants[0][0]
    print("\n" + "=" * 72)
    print("%-10s %10s %10s %10s    %s"
          % ("variant", "realistic", "peer", "heldout", "verdict vs %s" % ref))
    print("-" * 72)
    for n, _ in variants:
        d = summary[n]
        if n == ref:
            note = "reference"
        else:
            deltas = [d[t] - summary[ref][t] for t in TIERS]
            wins = [t for t, x in zip(TIERS, deltas) if x > 0.004]
            losses = [t for t, x in zip(TIERS, deltas) if x < -0.004]
            if not losses:
                note = "better on %s" % ", ".join(wins) if wins else "level"
            elif not wins:
                note = "worse everywhere"
            else:
                note = "mixed: wins %s, loses %s" % (", ".join(wins),
                                                     ", ".join(losses))
        print("%-10s %10.3f %10.3f %10.3f    %s"
              % (n, d["realistic"], d["peer"], d["heldout"], note))
    print("\nShip a candidate only if it is at least level on all three tiers.")


if __name__ == "__main__":
    main()
