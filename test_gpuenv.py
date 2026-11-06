"""
Prove the batched tensor engine matches engine.py exactly.

Identical action sequences go through both, and the FULL state is compared after
every single turn: ownership, upgrade flags, positions, freeze counters, shield
cooldowns, progress, income, score and the token. Any divergence is reported with
the turn it happened on, because an RL agent trained against a subtly wrong
simulator learns a subtly wrong game.
"""
import random
import sys

import torch

import engine
import gpuenv

DEV = sys.argv[1] if len(sys.argv) > 1 else "cpu"
NGAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 48
RULESETS = [
    ("defaults", None),
    ("frozen_stay_counts", {"frozen_stay_counts": True}),
    ("no claim reset", {"claim_resets_progress": False}),
    ("catch ignores stay", {"catch_requires_stay": False}),
    ("no home upgrade", {"home_upgradable": False}),
]
A2I = dict((a, i) for i, a in enumerate(engine.ACTIONS))

fails = []
checked = 0

for rname, rules in RULESETS:
    rnd = random.Random(1234)
    maps = [engine.make_map(seed=i + 1) for i in range(NGAMES)]
    tokens = [rnd.randint(1, 4) for _ in range(NGAMES)]
    cpu = [engine.Game(base=maps[i], rules=rules, start_token=tokens[i])
           for i in range(NGAMES)]
    base_t = torch.tensor(maps, dtype=torch.long)
    tok_t = torch.tensor(tokens, dtype=torch.long)
    gpu = gpuenv.BatchGame(base_t, n=NGAMES, device=DEV, rules=rules,
                           start_token=tok_t)

    bad = False
    for turn in range(1, 81):
        acts = []
        for i in range(NGAMES):
            row = []
            for b in range(4):
                # mostly legal actions, with a sprinkle of illegal ones so the
                # normalisation paths get exercised too
                if rnd.random() < 0.85:
                    row.append(rnd.choice(cpu[i].legal(b)))
                else:
                    row.append(rnd.choice(engine.ACTIONS))
            acts.append(row)
        for i in range(NGAMES):
            cpu[i].step(acts[i])
        gpu.step(torch.tensor([[A2I[a] for a in row] for row in acts],
                              dtype=torch.long))

        g_owner = gpu.owner.cpu().tolist()
        g_upg = gpu.upg.long().cpu().tolist()
        g_pos = gpu.pos.cpu().tolist()
        g_frz = gpu.frozen.cpu().tolist()
        g_cd = gpu.cd.cpu().tolist()
        g_prog = gpu.prog.cpu().tolist()
        g_sc = gpu.score.cpu().tolist()
        g_inc = gpu.income.cpu().tolist()
        g_tok = gpu.token.cpu().tolist()
        for i in range(NGAMES):
            c = cpu[i]
            checked += 1
            for label, a, b in (("owner", c.owner, g_owner[i]),
                                ("upg", c.upg, g_upg[i]),
                                ("pos", c.pos, g_pos[i]),
                                ("frozen", c.frozen, g_frz[i]),
                                ("cd", c.cd, g_cd[i]),
                                ("prog", c.prog, g_prog[i]),
                                ("score", c.score, g_sc[i]),
                                ("income", c.income, g_inc[i]),
                                ("token", c.token, g_tok[i])):
                if list(a) != list(b) if label != "token" else a != b:
                    fails.append("%s: %s diverged, game %d turn %d\n"
                                 "      cpu %s\n      gpu %s"
                                 % (rname, label, i, turn, a, b))
                    bad = True
                    break
            if bad:
                break
        if bad:
            break
    if not bad:
        print("  OK  %-20s %d games x 80 turns" % (rname, NGAMES))
    else:
        print("  BAD %-20s" % rname)

print("\nstate comparisons: %d" % checked)
if fails:
    print("DIVERGENCE (%d):" % len(fails))
    for f in fails[:4]:
        print("  - %s" % f)
    sys.exit(1)
print("GPU ENGINE MATCHES engine.py EXACTLY (device=%s)" % DEV)
