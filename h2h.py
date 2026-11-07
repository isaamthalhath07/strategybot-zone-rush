"""
Head-to-head dyad measurement: is an attacker beating one specific defender, or
is it simply a stronger bot than everything?

exploit.py asks "how does one attacker do against three copies of a defender".
That number conflates three different things:

  1. the attacker genuinely exploiting that defender's policy,
  2. the attacker just being better than it in general,
  3. three identical defenders cannibalising each other, which inflates the
     attacker's placement without the attacker doing anything at all.

Round 1 scores none of those. It scores pairwise results: each four-bot game
becomes three one-on-one outcomes, and Elo is built from those. So the quantity
that decides the ranking is the dyad -- in a game holding one attacker, one
defender and two neutral field bots, does the attacker finish ahead of the
defender? Margin is irrelevant and third parties only matter through the board
they leave behind.

Measuring every attacker against every defender then separates (1) from (2) for
free. An attacker with a real exploit beats its own target far more often than
it beats the versions it was never shown. An attacker that is merely strong
beats them all by about the same amount, and the `spread` column is the tell.

Every pair plays the identical maps, lineups and tokens, and every task is
played twice with the attacker's and defender's seats exchanged, so seat bias
cancels exactly rather than on average. Both bots also get the same rng seed,
so neither is handed better luck inside its own planner.

Either side may be given as `name=file.json` (my planner with those weights)
or as a bare registry name from field.opponent, which is any opponent in the
field. The second form is what turns this into a leak detector rather than a
duel: it asks which of the bots I already have beats mine one-on-one.

    python h2h.py <games> <tier> att:<spec> def:<spec> ...
    python h2h.py 300 strangers att:n4=n4_v7.json def:v7=v7_params.json
    python h2h.py 200 strangers att:spine att:pro_tuned def:v7=v7_params.json
"""
import math
import multiprocessing as mp
import os
import random
import sys

import engine
import field as fieldmod
import maps
import measure
import mybot


def _default_procs():
    """PROCS caps the pool, so a measurement can share the machine with a
    tuner instead of oversubscribing it. Results do not depend on it: both
    clock-reading paths are pinned off, which is the whole point of that
    pinning."""
    n = int(os.environ.get("PROCS", "0"))
    return n if n > 0 else min(24, mp.cpu_count())


def _pin(p):
    """Measurement must not depend on how loaded the machine is. Both the
    adaptive beam and the hard deadline inside the beam search read the clock,
    so both are switched off here; see the note in measure.play."""
    p = dict(p)
    p["throttle"] = 0
    p["budget_ms"] = 10000.0
    return p


def resolve(spec):
    """A contestant is either `name=file.json`, meaning my own planner with
    those weights, or a bare registry name from field.opponent.

    Allowing registry names is the point of this script rather than a detail:
    the question worth asking is not only "can a bot built like mine beat mine"
    but "which of the opponents I already have beats mine one-on-one". A bot
    can be weaker than me against the field as a whole and still take most of
    our own pairings, and in a ranking built from pairwise results that costs
    exactly as much as being outplayed by a better bot.
    """
    if "=" in spec:
        name, params = measure.load(spec)
        return name, ("params", _pin(params))
    return spec, ("reg", spec)


def _agent(side, seed):
    kind, payload = side
    if kind == "params":
        return mybot.Agent(seed=seed, params=payload)
    return fieldmod.opponent(payload)(seed)


def make_tasks(n, tier, seed=20261107):
    """Each task fixes a map, the two contested seats, two field bots and the
    starting token. The seat pair is drawn without replacement so the attacker
    and defender are never asked to share a seat."""
    rnd = random.Random(seed)
    pool = fieldmod.tier(tier)
    out = []
    for _ in range(n):
        sa, sd = rnd.sample(range(4), 2)
        out.append((rnd.randrange(1 << 30), sa, sd,
                    [pool[rnd.randrange(len(pool))] for _ in range(2)],
                    rnd.randint(1, 4)))
    return out


def _pw(places, me):
    pw = 0.0
    for j in range(4):
        if j == me:
            continue
        if places[me] < places[j]:
            pw += 1.0
        elif places[me] == places[j]:
            pw += 0.5
    return pw


def _one(pa, pd, task, x, y):
    """One game with the attacker at seat x and the defender at seat y."""
    map_seed, _sa, _sd, opps, token = task
    base = maps.make(map_seed)      # MAPS picks the family; default unchanged
    bots = [None] * 4
    # Same rng seed on both contested seats, so neither side is handed better
    # luck inside its own planner and the self-test stays exact.
    bots[x] = _agent(pa, map_seed & 0xffff)
    bots[y] = _agent(pd, map_seed & 0xffff)
    k = 0
    for i in range(4):
        if i in (x, y):
            continue
        bots[i] = fieldmod.opponent(opps[k])(map_seed * 4 + i)
        k += 1
    g = engine.Game(base=base, start_token=token)
    while not g.over():
        vs = g.views()
        acts = []
        for i in range(4):
            try:
                a = bots[i](vs[i])
            except Exception:
                a = "STAY"
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        g.step(acts)
    pl = g.places()
    if pl[x] < pl[y]:
        dyad = 1.0
    elif pl[x] == pl[y]:
        dyad = 0.5
    else:
        dyad = 0.0
    return dyad, _pw(pl, x), _pw(pl, y), g.score[x], g.score[y]


def play_pair(pa, pd, task):
    """The task played both ways round, averaged. Returns one observation."""
    _ms, sa, sd, _o, _t = task
    a = _one(pa, pd, task, sa, sd)
    b = _one(pa, pd, task, sd, sa)
    return tuple((a[i] + b[i]) / 2.0 for i in range(5))


def _worker(arg):
    pa, pd, tasks = arg
    return [play_pair(pa, pd, t) for t in tasks]


def run(atts, defs, tasks, procs=None, chunk=6):
    """Returns (att_name, def_name) -> per-task observations."""
    jobs = []
    owner = []
    for an, pa in atts:
        for dn, pd in defs:
            for i in range(0, len(tasks), chunk):
                jobs.append((pa, pd, tasks[i:i + chunk]))
                owner.append((an, dn))
    pool = mp.Pool(procs or _default_procs())
    res = pool.map(_worker, jobs, chunksize=1)
    pool.close()
    pool.join()
    out = {}
    for key, r in zip(owner, res):
        out.setdefault(key, []).extend(r)
    return out


def _stats(obs):
    n = len(obs)
    d = [o[0] for o in obs]
    m = sum(d) / n
    if n > 1:
        var = sum((x - m) ** 2 for x in d) / (n - 1)
        se = math.sqrt(var / n)
    else:
        se = float("inf")
    return m, se, sum(o[1] for o in obs) / n, sum(o[2] for o in obs) / n


def _paired(atts, defs, res):
    """Is an attacker doing better against one defender than the other?

    The two cells share their task list exactly, so the difference must be
    tested paired. Comparing the two cells' own error bars instead would be
    wrong in the usual direction: map and lineup luck is common to both and
    cancels in the difference, so the unpaired bars are far too wide and a real
    difference hides inside them.
    """
    (d0, _p0), (d1, _p1) = defs
    print()
    print("Paired difference, same tasks: does the attacker do better against "
          "%s than %s?" % (d0, d1))
    print("%-12s %10s %9s %8s" % ("attacker", "dyad diff", "+/- SE", "z"))
    print("-" * 43)
    for an, _pa in atts:
        a = res[(an, d0)]
        b = res[(an, d1)]
        n = min(len(a), len(b))
        d = [a[i][0] - b[i][0] for i in range(n)]
        m = sum(d) / n
        var = sum((x - m) ** 2 for x in d) / (n - 1) if n > 1 else 0.0
        se = (var / n) ** 0.5
        z = m / se if se > 0 else 0.0
        mark = "  **" if abs(z) >= 2.58 else ("  * " if abs(z) >= 1.96 else "")
        print("%-12s %+10.4f %9.4f %+8.2f%s" % (an, m, se, z, mark))


def report(atts, defs, res, tier, ngames):
    print("\n%d paired tasks on the '%s' field, each played both seat orders "
          "(%d games per cell)." % (ngames, tier, ngames * 2))
    print("Dyad = how often the attacker finishes ahead of that defender. "
          "0.500 is even.\n")
    head = "%-12s" % "attacker"
    for dn, _ in defs:
        head += " %14s" % ("vs " + dn)
    head += " %9s %8s" % ("spread", "own PW/3")
    print(head)
    print("-" * len(head))
    for an, _pa in atts:
        row = "%-12s" % an
        vals = []
        pws = []
        for dn, _pd in defs:
            m, se, pwa, _pwd = _stats(res[(an, dn)])
            vals.append(m)
            pws.append(pwa)
            z = (m - 0.5) / se if se > 0 else 0.0
            mark = "**" if abs(z) >= 2.58 else ("* " if abs(z) >= 1.96 else "  ")
            row += " %7.3f%s%5.3f" % (m, mark, se)
        row += " %9.3f %8.3f" % (max(vals) - min(vals), sum(pws) / len(pws))
        print(row)
    if len(defs) == 2:
        _paired(atts, defs, res)
    print("\nEach cell is   dyad  significance  standard error.")
    print("  * differs from 0.500 at 5%, ** at 1%.")
    print("spread = best dyad minus worst, across defenders. A real exploit is")
    print("  concentrated on its own target, so it shows up as a large spread;")
    print("  an attacker that is simply stronger beats every defender alike and")
    print("  its spread stays near zero.")


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    ngames = int(sys.argv[1])
    tier = sys.argv[2]
    atts = []
    defs = []
    for spec in sys.argv[3:]:
        kind, _, rest = spec.partition(":")
        if kind not in ("att", "def"):
            raise SystemExit("want att:name=file or def:name=file, got %r" % spec)
        name, side = resolve(rest)
        (atts if kind == "att" else defs).append((name, side))
    if not atts or not defs:
        raise SystemExit("need at least one attacker and one defender")
    tasks = make_tasks(ngames, tier)
    res = run(atts, defs, tasks)
    report(atts, defs, res, tier, ngames)


if __name__ == "__main__":
    main()
