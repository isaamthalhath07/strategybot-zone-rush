"""Assemble a two-mode candidate: plays exactly like zr6 (generation 2 decisions) until
rivals have shown that they raid un-upgraded land, then plays the cautious generation 4
decisions for the rest of the game.

  python3 lab/build_hybrid.py NAME [lost1=1] [seen1=0] [start=0]  -> lab/cand/NAME.py

  lost1  switch once this many of my own un-upgraded cells have been taken (0 = never)
  seen1  switch once rivals have taken this many un-upgraded cells from anybody (0 = never)
  start  1 = start in the cautious mode (reproduces zr8); with lost1=0 seen1=0 start=0 the
         result reproduces zr6. Both are checked with lab/equiv.py.

The tracker is _head5.py (generation 4's, plus a count of my own lost cells). Each
decision half is wrapped in a function so the two sets of names cannot collide.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))


def body(tailfile):
    src = open(os.path.join(HERE, "cand", tailfile)).read()
    cut = src.index("\n_clock = None")
    return src[:cut].rstrip() + "\n", src[cut:]


def wrap(name, src):
    out = ["def %s():" % name]
    for line in src.split("\n"):
        out.append(("    " + line) if line.strip() else "")
    out.append("    return _decide, _fallback")
    return "\n".join(out) + "\n"


def build(name, lost1=1, seen1=0, start=0):
    head = open(os.path.join(HERE, "cand", "_head5.py")).read()
    t2, _ = body("_tail2.py")
    t4, tail_act = body("_tail4.py")
    glue = '''

# ----------------------------------------------------------------------------- two modes
# Plain mode is the release that passed two out-of-sample tests. It claims land fast and
# leaves it un-upgraded for a while, which is right unless rivals raid such land. Wary mode
# prices un-upgraded land as at risk and upgrades before leaving. The switch is one-way
# and is made on what rivals have actually done in this game, not on who they are.
_PLAIN, _FALLBACK = _plain_mode()
_WARY, _ = _wary_mode()
_SWITCH = {"lost1": %d, "seen1": %d, "start": %d}


def _decide(v, m):
    if not m.wary:
        k = _SWITCH["lost1"]
        if _SWITCH["start"] or (k and m.lost_land[0] >= k):
            m.wary = True
        else:
            k = _SWITCH["seen1"]
            if k and sum(m.took1[s] for s in range(1, 5) if s != v.me) >= k:
                m.wary = True
    return _WARY(v, m) if m.wary else _PLAIN(v, m)


def _fallback(v):
    return _FALLBACK(v)

''' % (lost1, seen1, start)
    src = head + wrap("_plain_mode", t2) + "\n\n" + wrap("_wary_mode", t4) + glue + tail_act.lstrip("\n")
    path = os.path.join(HERE, "cand", name + ".py")
    open(path, "w").write(src)
    return path


if __name__ == "__main__":
    kw = {}
    for arg in sys.argv[2:]:
        k, val = arg.split("=")
        kw[k] = int(val)
    print(build(sys.argv[1], **kw))
