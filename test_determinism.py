"""
Is the measurement harness actually deterministic?

Every A/B conclusion in this project rests on paired comparison: two variants play
the identical games, and the per-task difference is the signal. That only works if
replaying a task gives the same result every time. If it does not, the pairing
buys nothing and small effects are indistinguishable from scheduling noise.

So this is checked directly, three ways, because each can fail on its own:

  A  the same parameters replayed in one process
  B  the same parameters as two separate variants through the worker pool
  C  the whole run repeated, to catch anything that depends on worker scheduling

A failure here invalidates measurements rather than the bot, which is exactly why
it needs its own test: a non-deterministic harness reports differences that are
not there, and two identical parameter sets separated by 0.06 pairwise wins is
indistinguishable from a real improvement.

    python test_determinism.py [games]
"""
import json
import sys

import measure
import mybot


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    fails = []
    P = dict(mybot.PARAMS)
    P.update(json.load(open("v6_params.json")))
    P["throttle"] = 0
    tasks = measure.make_tasks(games, "peer", seed=4242)

    print("=== A. the same parameters replayed in one process ================")
    r1 = [measure.play(P, t) for t in tasks]
    r2 = [measure.play(P, t) for t in tasks]
    ok = r1 == r2
    print("  %d tasks replayed: %s" % (len(tasks), "identical" if ok else "DIFFER"))
    if not ok:
        for i, (x, y) in enumerate(zip(r1, r2)):
            if x != y:
                print("    first difference at task %d: %s vs %s  opponents=%s"
                      % (i, x, y, tasks[i][2]))
                break
        fails.append("replaying a task in one process is not reproducible")

    print("\n=== B. identical parameters as two pooled variants ================")
    a = ("a", dict(P))
    b = ("b", dict(P))
    res = measure.run([a, b], tasks)
    ra, rb = res["a"], res["b"]
    ok = ra == rb
    n = float(len(ra))
    print("  mean PW: a %.4f   b %.4f   difference %+.4f"
          % (sum(x[0] for x in ra) / n, sum(x[0] for x in rb) / n,
             (sum(x[0] for x in rb) - sum(x[0] for x in ra)) / n))
    print("  per-task results: %s" % ("identical" if ok else "DIFFER"))
    if not ok:
        bad = [i for i in range(len(ra)) if ra[i] != rb[i]]
        print("    %d of %d tasks differ; first few:" % (len(bad), len(ra)))
        for i in bad[:4]:
            print("      task %d: %s vs %s  opponents=%s"
                  % (i, ra[i], rb[i], tasks[i][2]))
        fails.append("two identical variants give different pooled results")

    print("\n=== C. the whole pooled run, repeated =============================")
    res2 = measure.run([a], tasks)
    ok = res2["a"] == ra
    print("  second run vs first: %s" % ("identical" if ok else "DIFFER"))
    if not ok:
        fails.append("repeating a pooled run gives different results")

    print("\n" + "=" * 68)
    if fails:
        print("FAILURES (%d):" % len(fails))
        for f in fails:
            print("  - %s" % f)
        sys.exit(1)
    print("HARNESS IS DETERMINISTIC: paired differences mean what they say")


if __name__ == "__main__":
    main()
