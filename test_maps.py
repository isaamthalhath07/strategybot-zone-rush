"""
Does the bot survive, and stay strong, on maps my generator never produces?

Every game this bot was trained, tuned and measured on came from one generator
with an inward gradient and a home capped at 2 points. The rulebook promises far
less: values 1..3, four-fold mirrored, "generally" richer toward the middle. So
this replays the shipped bot on every family in maps.py and asks two questions,
in order of how much they would cost:

  survival  the SHIPPED bot.py, with decide() called directly rather than
            through act(). act() wraps decide() in a fallback policy, so through
            act() a crash would show up as weaker play rather than as a crash --
            exactly the failure this is trying to catch. Also checks it never
            returns an illegal action and stays inside the 200 ms turn budget.

  strength  paired games against the strangers tier, v7 against two variants of
            its home weighting. v7 discounts work on its own home by 19%
            (home_bonus 0.812), learned on maps where the home was nearly
            worthless; on a map where the home is worth 3 that discount is
            pointed at the single safest cell on the board. If the weight is
            miscalibrated there, the neutral variant beats it on exactly those
            families and nowhere else.

    python test_maps.py [games per family] [families...]
"""
import json
import os
import sys
import time

import engine
import field as fieldmod
import maps
import measure
import mybot

FAMILIES = sys.argv[2:] or list(maps.FAMILIES)
GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 240
SURVIVAL_GAMES = 8


def survival(family):
    """Shipped bot.py, decide() called directly, mixed strangers opponents."""
    import bot as shipped
    pool = fieldmod.tier("strangers")
    raised = []
    illegal = 0
    worst_ms = 0.0
    turns = 0
    home_up = []          # turn my own home got upgraded; 81 means never
    for gi in range(SURVIVAL_GAMES):
        seed = 880000 + gi
        base = maps.make(seed, family)
        seat = gi % 4
        g = engine.Game(base=base, start_token=(gi % 4) + 1)
        me = shipped.Agent(seed=gi)
        opps = [fieldmod.opponent(pool[(gi * 3 + k) % len(pool)])(seed * 4 + k)
                for k in range(3)]
        home = g.home.index(seat + 1)        # engine seats are 1-based
        up_at = 81
        while not g.over():
            vs = g.views()
            t0 = time.perf_counter()
            try:
                a = me.decide(vs[seat])            # NOT through __call__/act
            except Exception as e:
                raised.append(repr(e))
                a = "STAY"
            dt = (time.perf_counter() - t0) * 1000.0
            if dt > worst_ms and turns > 0:        # first turn has a 2 s budget
                worst_ms = dt
            turns += 1
            if a not in vs[seat].legal_actions:
                illegal += 1
                a = "STAY"
            acts = []
            k = 0
            for i in range(4):
                if i == seat:
                    acts.append(a)
                    continue
                try:
                    x = opps[k](vs[i])
                except Exception:
                    x = "STAY"
                acts.append(x if x in vs[i].legal_actions else "STAY")
                k += 1
            g.step(acts)
            if up_at == 81 and g.upg[home]:
                up_at = g.turn
        home_up.append(up_at)
    return raised, illegal, worst_ms, sorted(home_up)


def main():
    v7 = dict(mybot.PARAMS)
    v7.update(json.load(open("v7_params.json")))
    variants = [("v7", v7)]
    for hb in (1.0, 1.4):
        p = dict(v7)
        p["home_bonus"] = hb
        variants.append(("home%.1f" % hb, p))

    rows = []
    bad = []
    for fam in FAMILIES:
        raised, illegal, worst, home_up = survival(fam)
        ok = not raised and not illegal and worst < 200.0
        if not ok:
            bad.append(fam)
        print("[%s] survival: %d exceptions, %d illegal actions, worst turn "
              "%.1f ms  %s" % (fam, len(raised), illegal, worst,
                               "OK" if ok else "<-- FAIL " + (raised[:1] or [""])[0]))
        hv = maps.make(880000, fam)[0]
        print("[%s] home worth %d; turn v7 upgraded it, per game: %s"
              % (fam, hv, " ".join("never" if t == 81 else str(t) for t in home_up)))

        # Workers are spawned inside measure.run and inherit the environment,
        # so setting MAPS here is what puts them all on the same family.
        os.environ["MAPS"] = fam
        tasks = measure.make_tasks(GAMES, "strangers", seed=6060)
        res = measure.run(variants, tasks)
        measure.report(variants, res, label="[%s]" % fam)
        base = res["v7"]
        n = len(base)
        row = [fam, sum(x[0] for x in base) / n, sum(x[1] for x in base) / n]
        for name, _p in variants[1:]:
            d = [res[name][i][0] - base[i][0] for i in range(n)]
            m = sum(d) / n
            var = sum((x - m) ** 2 for x in d) / (n - 1)
            se = (var / n) ** 0.5
            row.append((m, m / se if se > 0 else 0.0))
        rows.append(row)
    os.environ.pop("MAPS", None)

    print("\n" + "=" * 74)
    print("%-11s %8s %7s   %18s %18s" % ("family", "v7 PW/3", "score",
                                         "home 1.0 vs v7", "home 1.4 vs v7"))
    print("-" * 74)
    for r in rows:
        cells = ""
        for m, z in r[3:]:
            mark = "**" if abs(z) >= 2.58 else ("* " if abs(z) >= 1.96 else "  ")
            cells += "   %+8.4f z%+5.2f%s" % (m, z, mark)
        print("%-11s %8.3f %7.0f%s" % (r[0], r[1], r[2], cells))
    print("\nPW/3 is pairwise wins out of 3 against the strangers tier; 1.50 is "
          "break-even.")
    print("A home weight that is miscalibrated off-distribution shows up as the "
          "home 1.0 or\nhome 1.4 column turning significantly positive on the "
          "rich-home families only.")
    if bad:
        raise SystemExit("\nSURVIVAL FAILED on: %s" % ", ".join(bad))
    print("\nsurvival: the shipped bot ran clean on every family")


if __name__ == "__main__":
    main()
