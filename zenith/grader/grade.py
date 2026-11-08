"""Move grader command line.

    # grade every move of one seat in one game, printed move by move
    python zenith/grader/grade.py game --lineup apex,fused,evolved,v7 --seat 1 [--family slope]
                                       [--map-seed 7] [--token 1] [--samples 4] [--eps 0.04]

    # grade one bot's moves over many games of an arena mode (parallel across games)
    python zenith/grader/grade.py batch 40 --focus gen:apex --mode gens --seed 1 --out g.jsonl

    # grade a recorded game (zenith/play.py writes these), e.g. a human's moves
    python zenith/grader/grade.py review game.json [--seats 1] [--continuation gen:zenith]

    # aggregate graded moves: categories, accuracy, and where the loss concentrates
    python zenith/grader/grade.py analyze g.jsonl [more.jsonl ...]

Bot specs are the arena's (zenith/lab/genarena.py): gen:NAME, opp:NAME, file:PATH.
A bare name in --lineup is tried as a generation first, then as an opponent.
"""
import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "zenith", "lab"))

import movegrade as mg  # noqa: E402
import genarena as arena  # noqa: E402
import xfield  # noqa: E402


def factory(name):
    if ":" in name:
        return arena.resolve(name)
    if name in arena.GENS:
        return arena.resolve(arena.GENS[name])
    return arena.opponent(name)


def _bots(names, map_seed):
    return [factory(n)(map_seed * 4 + i) for i, n in enumerate(names)]


# ---------------------------------------------------------------- one game
def cmd_game(a):
    os.chdir(ROOT)
    names = a.lineup.split(",")
    assert len(names) == 4, "--lineup needs four bots"
    base = xfield.make_map(a.family, a.map_seed)
    bots = _bots(names, a.map_seed)
    seats = [int(s) - 1 for s in a.seat.split(",")]
    t0 = time.time()

    def log(d):
        print(mg.describe(d), flush=True)
    dec, scores = mg.grade_game(bots, base, a.token, a.excl, seats, rseed=a.map_seed,
                                samples=a.samples, eps=a.eps, tau=a.tau, workers=a.workers,
                                log=log)
    print("\nfinal scores: " + "  ".join("%s %d" % (names[i], scores[i]) for i in range(4)))
    for s in seats:
        sm = mg.summarise([d for d in dec if d["seat"] == s + 1])
        print_summary("seat %d (%s)" % (s + 1, names[s]), sm)
    print("%.0f s" % (time.time() - t0))
    if a.out:
        with open(a.out, "w") as f:
            for d in dec:
                d["bot"] = names[d["seat"] - 1]
                f.write(json.dumps(d) + "\n")


def print_summary(title, sm, out=sys.stdout):
    w = out.write
    w("\n%s: %d moves, accuracy %.1f%% (%.1f%% on the %d critical moves), "
      "average loss %.3f PW/move, total %.2f PW\n" % (
          title, sm["moves"], sm["accuracy"] or 0, sm.get("critical_accuracy") or 0,
          sm.get("critical", 0), sm["avg_loss"] or 0, sm["total_loss"]))
    w("  " + "  ".join("%s %d" % (c, sm["categories"][c]) for c in mg.CATEGORIES
                       if sm["categories"][c]) + "\n")


# ---------------------------------------------------------------- batch
def _batch_job(arg):
    os.chdir(ROOT)
    task, focus, samples, eps, tau, store, stride = arg
    names = [focus if nm == "*" else nm for nm in task["lineup"]]
    base = xfield.make_map(task["family"], task["map_seed"])
    bots = _bots(names, task["map_seed"])
    me = task["lineup"].index("*")
    dec, scores = mg.grade_game(bots, base, task["token"], task["excl"], [me],
                                rseed=task["rseed"], samples=samples, eps=eps, tau=tau,
                                workers=1, store=store,
                                turns=(set(range(1 + task["rseed"] % stride, 81, stride))
                                       if stride > 1 else None))
    for d in dec:
        d["bot"] = focus
        d["lineup"] = task["lineup"]
        d["family"] = task["family"]
        d["final"] = scores
    return dec


def cmd_batch(a):
    tasks = arena.make_tasks(a.games, a.mode, seed=a.seed)
    jobs = [(t, a.focus, a.samples, a.eps, a.tau, a.store, a.stride) for t in tasks]
    t0 = time.time()
    pool = mp.Pool(a.procs)
    allx = []
    with open(a.out, "w") as f:
        for k, dec in enumerate(pool.imap_unordered(_batch_job, jobs)):
            for d in dec:
                f.write(json.dumps(d) + "\n")
            f.flush()
            allx.extend(dec)
            sm = mg.summarise(dec)
            print("game %d/%d  acc %.1f%%  loss %.2f  blunders %d mistakes %d  (%.0f s)" % (
                k + 1, len(jobs), sm["accuracy"] or 0, sm["total_loss"],
                sm["categories"]["Blunder"], sm["categories"]["Mistake"], time.time() - t0),
                flush=True)
    pool.close()
    pool.join()
    print_summary(a.focus, mg.summarise(allx))


# ---------------------------------------------------------------- review a record
def cmd_review(a):
    os.chdir(ROOT)
    with open(a.record) as f:
        rec = json.load(f)
    names = rec["lineup"]
    cont = []
    for i, nm in enumerate(names):
        if nm in ("human", "*"):
            cont.append(a.continuation)
        else:
            cont.append(nm)
    base = rec["base"]
    seed = rec.get("seed", 0)
    bots = _bots(cont, seed)
    if a.seats:
        seats = [int(s) - 1 for s in a.seats.split(",")]
    else:
        seats = [i for i, nm in enumerate(names) if nm in ("human", "*")] or [0]

    def log(d):
        print(mg.describe(d), flush=True)
    dec, scores = mg.grade_game(bots, base, rec["token"], rec.get("excl", False), seats,
                                rseed=seed, actions=rec["actions"], samples=a.samples,
                                eps=a.eps, tau=a.tau, workers=a.workers,
                                log=None if a.quiet else log)
    review = {"lineup": names, "final": scores, "decisions": dec, "summary": {}}
    for s in seats:
        sm = mg.summarise([d for d in dec if d["seat"] == s + 1])
        review["summary"][str(s + 1)] = sm
        print_summary("seat %d (%s)" % (s + 1, names[s]), sm)
        worst = sorted([d for d in dec if d["seat"] == s + 1], key=lambda d: -d["loss"])[:8]
        if worst:
            print("  costliest moves:")
            for d in worst:
                if d["loss"] > 0:
                    print("   " + mg.describe(d))
    out = a.out or (os.path.splitext(a.record)[0] + ".review.json")
    with open(out, "w") as f:
        json.dump(review, f)
    print("\nreview written to %s" % out)
    return review


# ---------------------------------------------------------------- analyze
def load(paths):
    out = []
    for p in paths:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    out.append(json.loads(ln))
    return out


def _bucket_table(rows, key, title, out=sys.stdout):
    acc = {}
    for d in rows:
        if d["acc"] is None:
            continue
        k = key(d)
        b = acc.setdefault(k, [0, 0.0, 0, 0])
        b[0] += 1
        b[1] += d["loss"]
        b[2] += d["category"] in ("Mistake", "Blunder")
        b[3] += d["category"] == "Blunder"
    tot = sum(v[1] for v in acc.values()) or 1.0
    out.write("\n%s\n  %-26s %6s %9s %7s %8s %8s\n" % (
        title, "bucket", "moves", "loss/mv", "share", "mist+bl", "blunder"))
    for k, v in sorted(acc.items(), key=lambda kv: -kv[1][1]):
        out.write("  %-26s %6d %9.4f %6.1f%% %8d %8d\n" % (
            str(k)[:26], v[0], v[1] / v[0], 100 * v[1] / tot, v[2], v[3]))


def phase(t):
    if t <= 10:
        return "1-10 opening"
    if t <= 30:
        return "11-30 build"
    if t <= 60:
        return "31-60 middle"
    if t <= 75:
        return "61-75 late"
    return "76-80 final"


def cmd_analyze(a):
    rows = load(a.files)
    bots = sorted(set(d.get("bot", "?") for d in rows))
    for b in bots:
        rb = [d for d in rows if d.get("bot", "?") == b]
        print_summary(b, mg.summarise(rb))
        _bucket_table(rb, lambda d: phase(d["turn"]), "loss by phase")
        _bucket_table(rb, lambda d: "%s -> %s" % (kind(d["played"]), kind(d["best"])),
                      "loss by played -> best action kind")
        _bucket_table(rb, lambda d: d["ctx"]["where"], "loss by where the bot stood")
        _bucket_table(rb, lambda d: "intruders=%d" % d["ctx"]["intruders"],
                      "loss by rivals on my land")
        _bucket_table(rb, lambda d: "%s/prog%d" % (d["ctx"]["where"], d["ctx"]["prog"]),
                      "loss by cell and progress")
        if any("lineup" in d for d in rb):
            def opp(d):
                return ",".join(sorted(nm for nm in d["lineup"] if nm != "*"))
            _bucket_table(rb, opp, "loss by line-up")
        worst = sorted(rb, key=lambda d: -d["loss"])[:a.top]
        print("\n  costliest moves")
        for d in worst:
            print("   " + mg.describe(d) + "  [%s]" % d["ctx"]["where"])


def kind(a):
    return "MOVE" if a in mg.MOVES else a


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--samples", type=int, default=4)
        sp.add_argument("--eps", type=float, default=0.04)
        sp.add_argument("--tau", type=float, default=60.0)
    g = sub.add_parser("game")
    g.add_argument("--lineup", required=True)
    g.add_argument("--seat", default="1")
    g.add_argument("--family", default="slope")
    g.add_argument("--map-seed", type=int, default=7)
    g.add_argument("--token", type=int, default=1)
    g.add_argument("--excl", action="store_true")
    g.add_argument("--workers", type=int, default=4)
    g.add_argument("--out")
    common(g)
    b = sub.add_parser("batch")
    b.add_argument("games", type=int)
    b.add_argument("--focus", required=True)
    b.add_argument("--mode", default="gens")
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--procs", type=int, default=mp.cpu_count())
    b.add_argument("--out", required=True)
    b.add_argument("--stride", type=int, default=1,
                   help="grade every Nth turn (offset varies by game)")
    b.add_argument("--store", action="store_true",
                   help="store each position and the planner memory (for distill.py)")
    common(b)
    r = sub.add_parser("review")
    r.add_argument("record")
    r.add_argument("--seats")
    r.add_argument("--continuation", default="gen:zenith")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--out")
    r.add_argument("--quiet", action="store_true")
    common(r)
    an = sub.add_parser("analyze")
    an.add_argument("files", nargs="+")
    an.add_argument("--top", type=int, default=25)
    a = p.parse_args(argv)
    return {"game": cmd_game, "batch": cmd_batch, "review": cmd_review,
            "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
