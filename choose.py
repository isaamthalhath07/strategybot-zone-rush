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
    print("\n" + "=" * 76)
    print("%-10s %10s %10s %10s    %s"
          % ("variant", "realistic", "peer", "heldout", "verdict vs %s" % ref))
    print("-" * 76)
    # The three tiers are NOT equal evidence, which cost a wrong conclusion once.
    # `realistic` is a fair model of the Round 1 field, weak entries included --
    # and that is exactly why it saturates: the bot already wins about 85% of its
    # pairings there, so a real improvement has almost nowhere to register. The
    # same candidate measured -0.007 on realistic and +0.254 on peer. So peer
    # decides, realistic only has to not regress, and heldout catches a candidate
    # that was fitted to the training field.
    for n, _ in variants:
        d = summary[n]
        if n == ref:
            note = "reference"
        else:
            dp = d["peer"] - summary[ref]["peer"]
            dr = d["realistic"] - summary[ref]["realistic"]
            dh = d["heldout"] - summary[ref]["heldout"]
            if dr < -0.03 or dh < -0.03:
                note = "REJECT: regressed on %s" % (
                    "realistic" if dr < -0.03 else "heldout")
            elif dp > 0.02:
                note = "SHIP: +%.3f on peer, no regression" % dp
            elif dp < -0.02:
                note = "reject: %.3f on peer" % dp
            else:
                note = "level on peer (%+.3f) -- no reason to switch" % dp
        print("%-10s %10.3f %10.3f %10.3f    %s"
              % (n, d["realistic"], d["peer"], d["heldout"], note))
    print("\npeer decides (it discriminates); realistic must not regress;")
    print("heldout catches a candidate fitted to the training field.")
    if len(variants) > 1:
        sat = summary[ref]["realistic"]
        if sat > 2.4:
            print("\nnote: realistic is at %.3f of a maximum 3.000 for the "
                  "reference, so it is\n      near its ceiling and cannot "
                  "separate strong candidates." % sat)


if __name__ == "__main__":
    main()
