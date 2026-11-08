"""Play Zone Rush against the bots in a terminal, then get every move graded.

    python zenith/play.py                       # you are seat 1 against three Zenith bots
    python zenith/play.py --seat 3 --opponents apex,zenith,fused --map example
    python zenith/play.py --no-review           # skip the graded review at the end
    python zenith/play.py --review-bots         # grade the bots' moves too

Controls each turn:  w = NORTH   a = WEST   s = SOUTH   d = EAST
                     x (or Enter) = STAY    f = SHIELD    q = quit (game is saved)

The bots see exactly what the server shows them (board, seat, token flag,
legal_actions) and keep their memory between turns, as in the competition. You
see more than they do: scores, the turn, cooldowns and progress, as a person
at the table would keep track of them.

Every game is saved to zenith/games/. The review grades each of your moves by
how it changed your chance of finishing above each rival, played out to turn 80
with the bots continuing and a Zenith engine finishing the game for you (see
zenith/grader/movegrade.py). Re-run a review later with:

    python zenith/grader/grade.py review zenith/games/<file>.json
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, os.path.join(ROOT, "crossfield"), os.path.join(HERE, "lab"),
           os.path.join(HERE, "grader")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402
import xfield  # noqa: E402
import genarena  # noqa: E402

KEYS = {"w": "NORTH", "a": "WEST", "s": "SOUTH", "d": "EAST", "x": "STAY", "": "STAY",
        "f": "SHIELD", "n": "NORTH", "e": "EAST", "stay": "STAY", "shield": "SHIELD",
        "north": "NORTH", "south": "SOUTH", "east": "EAST", "west": "WEST"}
COLOR = {0: "", 1: "\033[41m", 2: "\033[44m", 3: "\033[42m", 4: "\033[43m"}
FG = {1: "\033[91m", 2: "\033[94m", 3: "\033[92m", 4: "\033[93m"}
RESET = "\033[0m"
BOLD = "\033[1m"


def factory(name):
    if ":" in name:
        return genarena.resolve(name)
    if name in genarena.GENS:
        return genarena.resolve(genarena.GENS[name])
    return genarena.opponent(name)


def render(g, me, names, color=True, out=sys.stdout):
    w = out.write
    c = (lambda k: COLOR[k]) if color else (lambda k: "")
    f = (lambda k: FG.get(k, "")) if color else (lambda k: "")
    r = RESET if color else ""
    w("\n   " + "".join("  %d  " % col for col in range(8)) + "\n")
    occ = dict((g.pos[i], i + 1) for i in range(4))
    for row in range(8):
        line = " %d " % row
        for col in range(8):
            p = row * 8 + col
            o = g.owner[p]
            who = occ.get(p)
            up = "+" if g.upg[p] else " "
            if who:
                mark = ("*%d" if g.frozen[who - 1] else "@%d") % who
            elif g.home[p]:
                mark = "H "
            else:
                mark = "  "
            cell = "%d%s%s" % (g.base[p], up, mark)
            line += c(o) + cell + r + " "
        w(line + "\n")
    w("\n  cell = base points, '+' upgraded, @n bot n, *n frozen bot n, H home; colour = owner\n")
    w("  turn %d/80   token: seat %d\n" % (g.turn, g.token))
    order = sorted(range(4), key=lambda i: -g.score[i])
    for i in order:
        tag = " <- you" if i == me else ""
        w("  %sseat %d%s %-14s score %5d  income %3d  cooldown %d  frozen %d  progress %d%s\n" % (
            f(i + 1), i + 1, r, names[i][:14], g.score[i], g.income[i], g.cd[i], g.frozen[i],
            g.prog[i], tag))


def ask(legal, g, me):
    while True:
        try:
            raw = input("  your move %s > " % "/".join(
                k for k, v in (("w", "NORTH"), ("a", "WEST"), ("s", "SOUTH"), ("d", "EAST"),
                               ("x", "STAY"), ("f", "SHIELD")) if v in legal)).strip().lower()
        except EOFError:
            return None
        if raw == "q":
            return None
        a = KEYS.get(raw)
        if a is None:
            print("  keys: w a s d move, x stay, f shield, q quit")
            continue
        if a not in legal:
            print("  %s is not legal now (legal: %s)" % (a, ", ".join(legal)))
            continue
        return a


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seat", type=int, default=1, choices=(1, 2, 3, 4))
    p.add_argument("--opponents", default="zenith,zenith,zenith",
                   help="three bots: generation names (v7, evolved, fused, apex, zenith), "
                        "opponent names, or specs")
    p.add_argument("--map", default="random",
                   help="'example', 'random', or FAMILY:SEED (slope, balanced, patchy, edge, flat)")
    p.add_argument("--token", type=int, default=0, help="starting token holder (0 = random)")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("--review-bots", action="store_true")
    p.add_argument("--samples", type=int, default=6, help="rollouts per move in the review")
    p.add_argument("--continuation", default="gen:zenith",
                   help="the engine that finishes the game for you when grading a move")
    a = p.parse_args(argv)
    os.chdir(ROOT)
    seed = random.randrange(1 << 30)
    if a.map == "random":
        fam = random.choice(["slope", "balanced", "patchy", "example"])
        mseed = seed
    elif a.map == "example":
        fam, mseed = "example", 0
    else:
        fam, _, ms = a.map.partition(":")
        mseed = int(ms or seed)
    base = xfield.make_map(fam, mseed)
    token = a.token or random.randint(1, 4)
    opps = a.opponents.split(",")
    if len(opps) != 3:
        raise SystemExit("--opponents needs exactly three names")
    me = a.seat - 1
    names, specs, bots = [], [], []
    k = 0
    for i in range(4):
        if i == me:
            names.append("you")
            specs.append("human")
            bots.append(None)
        else:
            nm = opps[k]
            k += 1
            names.append(nm)
            specs.append(nm)
            bots.append(factory(nm)(mseed * 4 + i))
    g = engine.Game(base=base, start_token=token)
    actions = []
    quit_early = False
    color = not a.no_color and sys.stdout.isatty()
    print("%sZone Rush%s: you are seat %d (%s corner). Map %s:%d, token starts at seat %d." % (
        BOLD if color else "", RESET if color else "", a.seat,
        ("top-left", "top-right", "bottom-right", "bottom-left")[me], fam, mseed, token))
    while not g.over():
        vs = genarena.xfield._views(g, False)
        render(g, me, names, color)
        human = ask(vs[me].legal_actions, g, me)
        if human is None:
            quit_early = True
            break
        acts = []
        for i in range(4):
            if i == me:
                acts.append(human)
                continue
            try:
                x = bots[i](vs[i])
            except Exception:
                x = "STAY"
            if x not in vs[i].legal_actions:
                x = "STAY"
            acts.append(x)
        actions.append(list(acts))
        g.step(acts)
        print("  played: " + "  ".join("seat %d %s" % (i + 1, acts[i]) for i in range(4)))
    render(g, me, names, color)
    places = g.places()
    print("\nfinal: " + "   ".join("seat %d (%s) %d, place %g" % (
        i + 1, names[i], g.score[i], places[i]) for i in range(4)))
    beaten = sum(1 for i in range(4) if i != me and g.score[me] > g.score[i])
    print("you finished above %d of 3 bots" % beaten)
    os.makedirs(os.path.join(HERE, "games"), exist_ok=True)
    path = os.path.join(HERE, "games", time.strftime("%Y%m%d-%H%M%S") + "-seat%d.json" % a.seat)
    with open(path, "w") as f:
        json.dump({"lineup": specs, "base": base, "token": token, "excl": False,
                   "seed": mseed, "family": fam, "actions": actions, "final": list(g.score),
                   "complete": not quit_early}, f)
    print("game saved to %s" % os.path.relpath(path, ROOT))
    if quit_early or a.no_review:
        return
    print("\ngrading every move (this takes a minute or two)...")
    import grade
    args = ["review", path, "--samples", str(a.samples), "--continuation", a.continuation,
            "--quiet"]
    if a.review_bots:
        args += ["--seats", "1,2,3,4"]
    grade.main(args)


if __name__ == "__main__":
    main()
