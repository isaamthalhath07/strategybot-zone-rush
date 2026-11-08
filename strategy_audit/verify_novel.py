"""
Independent check of the novel opponents in strategy_audit/novel/.

The agents that wrote them reported their own test numbers; this does not rely on
those. For every bot it:

  * calls act() directly -- not __call__, whose try/except would turn a crash
    into a silent STAY -- so any exception is counted;
  * times every call (mean and max);
  * measures strength against three STAY bots, and against the repository's
    spine / pro / camper (the same yardstick used for the outside designs, which
    all scored 1,500-2,050 there), so a strawman cannot slip into the field.

    python strategy_audit/verify_novel.py [games] [name-prefix]
"""
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)

import engine  # noqa: E402
import edge_audit  # noqa: E402


class Probe(object):
    def __init__(self, cls, seed):
        self.b = cls(seed)
        self.calls = self.errors = self.stays = self.shields = 0
        self.t = []
        self.first_error = None

    def __call__(self, view):
        self.calls += 1
        t0 = time.perf_counter()
        try:
            a = self.b.act(view)
        except Exception as e:
            self.errors += 1
            if self.first_error is None:
                self.first_error = repr(e)
            a = "STAY"
        self.t.append(time.perf_counter() - t0)
        if a not in view.legal_actions:
            a = "STAY"
        self.stays += a == "STAY"
        self.shields += a == "SHIELD"
        return a


def check(args):
    name, games = args
    cls = edge_audit.NOVEL[name]
    res = {"errors": 0, "calls": 0, "t": [], "stay": 0, "shield": 0,
           "vs_stay": [], "vs_strong": [], "err": None}
    for gi in range(games):
        for kind in ("stay", "strong"):
            seat = gi % 4
            p = Probe(cls, 1000 + gi)
            bots = []
            k = 0
            for i in range(4):
                if i == seat:
                    bots.append(p)
                elif kind == "stay":
                    bots.append(lambda v: "STAY")
                else:
                    bots.append(edge_audit.make_opponent(("spine", "pro", "camper")[k],
                                                         gi * 4 + i))
                    k += 1
            g = engine.Game(base=engine.make_map(seed=500 + gi), start_token=gi % 4 + 1)
            while not g.over():
                vs = g.views()
                acts = []
                for i in range(4):
                    a = bots[i](vs[i])
                    acts.append(a if a in vs[i].legal_actions else "STAY")
                g.step(acts)
            res["errors"] += p.errors
            res["calls"] += p.calls
            res["t"] += p.t
            res["stay"] += p.stays
            res["shield"] += p.shields
            res["err"] = res["err"] or p.first_error
            res["vs_" + kind].append(g.score[seat])
    return name, res


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    names = sorted(n for n in edge_audit.NOVEL if n.startswith(prefix))
    if not names:
        raise SystemExit("no novel bots found in strategy_audit/novel/")
    with mp.Pool(min(4, mp.cpu_count())) as pool:
        out = pool.map(check, [(n, games) for n in names], chunksize=1)
    lines = ["novel opponents: %d bots, %d games each against 3x STAY and against "
             "spine/pro/camper (seat rotated)" % (len(names), games), "",
             "%-18s %6s %8s %8s %7s %7s %10s %12s" % ("bot", "errors", "mean ms", "max ms",
                                                      "STAY %", "shld %", "vs STAY",
                                                      "vs strong")]
    bad = []
    for name, r in out:
        t = r["t"]
        mean = 1000.0 * sum(t) / max(1, len(t))
        mx = 1000.0 * max(t) if t else 0.0
        vs_stay = sum(r["vs_stay"]) / float(len(r["vs_stay"]))
        vs_strong = sum(r["vs_strong"]) / float(len(r["vs_strong"]))
        lines.append("%-18s %6d %8.1f %8.1f %6.0f%% %6.1f%% %10.0f %12.0f"
                     % (name, r["errors"], mean, mx, 100.0 * r["stay"] / r["calls"],
                        100.0 * r["shield"] / r["calls"], vs_stay, vs_strong))
        if r["errors"]:
            bad.append("%s raised %d times, first: %s" % (name, r["errors"], r["err"]))
        if vs_strong < 1200:
            bad.append("%s is weak against strong opponents (%.0f)" % (name, vs_strong))
    lines.append("")
    lines += (["PROBLEMS:"] + ["  " + b for b in bad]) if bad else ["no problems found"]
    txt = "\n".join(lines)
    print(txt)
    if prefix:
        return                       # a partial check is not the record
    path = os.path.join(HERE, "results", "novel_verification.txt")
    with open(path + ".partial", "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    os.replace(path + ".partial", path)


if __name__ == "__main__":
    main()
