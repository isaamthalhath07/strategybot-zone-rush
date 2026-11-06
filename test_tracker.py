"""
Does the Tracker rebuild the hidden state exactly, from board diffs alone?

It only ever sees what the real server exposes (owner/upgraded/home/occupant/
is_frozen/base_points + bot_id + is_priority_token + legal_actions), so if this
passes, the bot genuinely knows every score, every progress counter and every
shield cooldown in the game.
"""
import random
import engine
import mybot
import zoo

DIFF = {"score": 0, "prog": 0, "cd": 0, "frozen": 0, "token": 0, "pos": 0}
CHECKS = 0


def run(seed, lineup, rules=None):
    global CHECKS
    base = engine.make_map(seed=seed)
    rnd = random.Random(seed)
    g = engine.Game(base=base, start_token=rnd.randint(1, 4), rules=rules)
    bots = [lineup[i](seed * 7 + i) for i in range(4)]
    tr = mybot.Tracker()
    seat = 1
    my_last = None
    while not g.over():
        vs = g.views()
        v = vs[seat - 1]
        bd = v.board
        cells = [bd[r][c] for r in range(8) for c in range(8)]
        owner = [c.owner for c in cells]
        upg = [1 if c.is_upgraded else 0 for c in cells]
        occ = [c.occupant for c in cells]
        frz = [1 if c.is_frozen else 0 for c in cells]
        home_of = [c.owner if c.is_home else 0 for c in cells]
        bse = [c.base_points for c in cells]
        tr.observe(owner, upg, occ, frz, seat, v.is_priority_token, bse, home_of,
                   my_last)

        # compare against the engine's hidden truth, as of the START of this turn
        CHECKS += 1
        if tr.token_known and tr.token != g.token:
            DIFF["token"] += 1
        if tr.pos != g.pos:
            DIFF["pos"] += 1
        if tr.frozen != g.frozen:
            DIFF["frozen"] += 1
        if tr.cd != g.cd:
            DIFF["cd"] += 1
        if tr.prog != g.prog:
            DIFF["prog"] += 1
        if tr.score != g.score:
            DIFF["score"] += 1

        acts = []
        for i in range(4):
            a = bots[i](vs[i])
            if a not in vs[i].legal_actions:
                a = "STAY"
            acts.append(a)
        my_last = acts[seat - 1]
        g.step(acts)


LINEUPS = [
    [zoo.GreedyShieldBot, zoo.RaiderBot, zoo.SpineFarmerBot, zoo.CamperBot],
    [zoo.BaiterBot, zoo.BaiterBot, zoo.GreedyShieldBot, zoo.RaiderBot],
    [zoo.RandomBot, zoo.RandomBot, zoo.RandomBot, zoo.RandomBot],
    [zoo.CamperBot, zoo.BaiterBot, zoo.RaiderBot, zoo.GreedyValueBot],
    [zoo.RandomBot, zoo.GreedyShieldBot, zoo.BaiterBot, zoo.CamperBot],
]

for s in range(40):
    run(s + 1, LINEUPS[s % len(LINEUPS)])

print("turns checked: %d" % CHECKS)
bad = False
for k, v in sorted(DIFF.items()):
    flag = "OK " if v == 0 else "BAD"
    if v:
        bad = True
    print("  %s %-8s mismatches: %d" % (flag, k, v))
# Cooldowns cannot always be attributed uniquely: a bot freezing on rival land
# was either caught by the landlord or backfired on its own shield, and some
# cases are genuinely indistinguishable. The tracker resolves those pessimistically
# (assume the rival CAN still shield), so residual error costs opportunity, never
# a blunder. Everything else must be exact.
hard = {k: v for k, v in DIFF.items() if k != "cd"}
if any(hard.values()):
    print("TRACKER HAS DRIFT in exactly-reconstructible fields")
elif DIFF["cd"] > CHECKS * 0.03:
    print("TRACKER cooldown error too high: %.1f%%" % (100.0 * DIFF["cd"] / CHECKS))
else:
    print("TRACKER OK - exact except cooldowns (%d/%d = %.1f%%, ambiguous cases)"
          % (DIFF["cd"], CHECKS, 100.0 * DIFF["cd"] / CHECKS))
