"""Tests for the move grader (zenith/grader/movegrade.py).

    python zenith/tests/test_grader.py

  1  fork_map returns every child's result, in order, from the parent's state
  2  candidates: a move into an occupied cell is not a separate choice; frozen = forced
  3  the cross-fitted loss is unbiased where the naive one is not (synthetic noise)
  4  category boundaries and the accuracy curve
  5  a real graded decision: the rollouts reproduce the actual game for the played move
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "zenith", "grader"))
sys.path.insert(0, os.path.join(ROOT, "zenith", "lab"))

import movegrade as mg  # noqa: E402
import engine  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("  %-62s %s %s" % (name, "ok" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def t1():
    print("1  fork_map")
    state = {"x": 41}
    res = mg.fork_map(lambda j: state["x"] + j, list(range(12)), 4)
    check("12 children, results in order", res == [41 + j for j in range(12)])
    res = mg.fork_map(lambda j: 1 // 0, [0], 1)
    check("a failing child reports an error, parent survives", "error" in res[0])


def t2():
    print("2  candidates")
    g = engine.Game(base=engine.make_map(canonical=True))
    g.pos = [9, 1, 63, 56]                       # seat 2 sits just north-east of seat 1
    c = mg.candidates(g, 0, g.legal(0))
    check("move into an occupied cell dropped", "NORTH" not in c and "EAST" in c, str(c))
    g.frozen[0] = 2
    check("frozen seat is forced to STAY", mg.candidates(g, 0, g.legal(0)) == ["STAY"])


def t3():
    print("3  cross-fitted loss")
    rnd = random.Random(3)
    naive, cf = [], []
    for _ in range(3000):
        # five actions with the same true value, noisy samples: the true loss is 0
        per = dict((a, [rnd.gauss(1.5, 0.4) for _k in range(6)]) for a in "ABCDE")
        loss, nv, _se, _b = mg.debiased_loss(per, "A")
        naive.append(nv)
        cf.append(loss)
    mn, mc = sum(naive) / len(naive), sum(cf) / len(cf)
    check("naive loss is biased upward (true loss 0)", mn > 0.15, "%.3f" % mn)
    check("cross-fitted loss is not", abs(mc) < 0.03, "%+.3f" % mc)
    per = {"A": [1.0] * 6, "B": [1.6] * 6}
    loss, nv, se, b = mg.debiased_loss(per, "A")
    check("a real 0.6 gap is measured as 0.6", abs(loss - 0.6) < 1e-9 and b == "B")


def t4():
    print("4  categories and accuracy")
    check("accuracy of a perfect move is 100", abs(mg.accuracy(0.0) - 100) < 0.01)
    check("accuracy falls with loss", mg.accuracy(0.3) > mg.accuracy(0.6) > mg.accuracy(1.5))
    names = [n for n, _t in mg.THRESH]
    check("thresholds ordered Best..Mistake", names == ["Best", "Excellent", "Good",
                                                         "Inaccuracy", "Mistake"])


def t5():
    print("5  a graded decision on a real table")
    os.chdir(ROOT)
    import genarena
    import xfield
    base = xfield.make_map("slope", 21)
    bots = [genarena.resolve(genarena.GENS["evolved"])(i) for i in range(4)]
    table = mg.Table(base, 1, False, bots, rseed=5)
    # the played move, rolled out with no noise, must reproduce the real game
    ref = [genarena.resolve(genarena.GENS["evolved"])(i) for i in range(4)]
    g = engine.Game(base=base, start_token=1)
    first = None
    while not g.over():
        vs = mg.views(g, False)
        acts = [mg._call(ref[i], vs[i]) for i in range(4)]
        if first is None:
            first = acts[0]
        g.step(acts)
    out = mg.fork_map(lambda _j: table.rollout(0, first, 0, 0.0, 60.0), [0], 1)[0]
    check("exact rollout of the played move = the real game", out["score"] == g.score[0],
          "%s vs %s" % (out["score"], g.score[0]))
    d = mg.grade_decision(table, 0, first, samples=2, eps=0.04, tau=60.0, workers=4)
    check("decision graded with every candidate", set(d["q"]) == set(d["cands"]), str(d["q"]))


if __name__ == "__main__":
    t1()
    t2()
    t3()
    t4()
    t5()
    print("\n%s" % ("ALL PASSED" if not FAILS else "FAILED: %s" % ", ".join(FAILS)))
    sys.exit(1 if FAILS else 0)
