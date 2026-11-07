"""
Round 2, rulebook 4.4: a robot that misses its cell is frozen for 3 turns. That
freeze is not caused by any shield, but the tracker's attribution solver assumes
every new freeze is. Inject penalty freezes into the engine and measure how often
the tracker then believes a rival is on shield cooldown when it is not (finding C1).

    python audit/penalty.py [variant]

`variant` is any edge_audit variant spec (default `base`); AUDIT_BOT chooses the
bot, as for edge_audit.py. E.g. AUDIT_BOT=mybot python audit/penalty.py @v8_params.json
"""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
os.chdir(REPO)
import random
import engine, measure
import edge_audit

bot = edge_audit.bot
SPEC = sys.argv[1] if len(sys.argv) > 1 else "base"

def run(p_pen, games=60):
    tasks = measure.make_tasks(games, "strangers", seed=11)
    unsafe = safe = exact = 0     # unsafe: tracker thinks rival CAN'T shield but it can
    phantom_turns = 0
    for (map_seed, myseat, opps, token) in tasks:
        rnd = random.Random(map_seed)
        bots, k = [], 0
        for i in range(4):
            if i == myseat:
                ag = bot.Agent(seed=1, params=edge_audit.parse_variant(SPEC)[0]); bots.append(ag)
            else:
                bots.append(measure._make(opps[k], map_seed * 4 + i)); k += 1
        g = engine.Game(base=engine.make_map(seed=map_seed), start_token=token)
        while not g.over():
            vs = g.views()
            acts = []
            for i in range(4):
                a = bots[i](vs[i])
                acts.append(a if a in vs[i].legal_actions else "STAY")
            if g.turn > 2:
                for j in range(4):
                    if j == myseat:
                        continue
                    tc, ec = ag.tr.cd[j], g.cd[j]
                    if tc == ec: exact += 1
                    elif tc > ec:
                        unsafe += 1
                        if ec == 0: phantom_turns += 1
                    else: safe += 1
            g.step(acts)
            for i in range(4):          # hardware time penalty: 3-turn freeze, progress reset
                if g.frozen[i] == 0 and rnd.random() < p_pen:
                    g.frozen[i] = 3; g.prog[i] = 0
    tot = unsafe + safe + exact
    return exact / tot, unsafe / tot, safe / tot, phantom_turns / tot

for p in (0.0, 0.01, 0.03):
    e, u, s, ph = run(p)
    print("penalty rate %.2f/bot/turn: rival-cooldown exact %.1f%%, UNSAFE (thinks rival can't "
          "shield, it can) %.2f%%, of which rival fully ready %.2f%%, safe-side errors %.2f%%"
          % (p, 100 * e, 100 * u, 100 * ph, 100 * s))
