import random, engine, mybot, zoo
LINEUPS = [
    [zoo.GreedyShieldBot, zoo.RaiderBot, zoo.SpineFarmerBot, zoo.CamperBot],
    [zoo.BaiterBot, zoo.BaiterBot, zoo.GreedyShieldBot, zoo.RaiderBot],
    [zoo.RandomBot, zoo.RandomBot, zoo.RandomBot, zoo.RandomBot],
    [zoo.CamperBot, zoo.BaiterBot, zoo.RaiderBot, zoo.GreedyValueBot],
    [zoo.RandomBot, zoo.GreedyShieldBot, zoo.BaiterBot, zoo.CamperBot],
]
safe = risky = 0
for s in range(40):
    lineup = LINEUPS[s % len(LINEUPS)]
    base = engine.make_map(seed=s+1); rnd = random.Random(s+1)
    g = engine.Game(base=base, start_token=rnd.randint(1,4))
    bots = [lineup[i]((s+1)*7+i) for i in range(4)]
    tr = mybot.Tracker(); seat = 1; my_last=None
    while not g.over():
        vs = g.views(); v = vs[seat-1]
        cells=[v.board[r][c] for r in range(8) for c in range(8)]
        tr.observe([c.owner for c in cells],[1 if c.is_upgraded else 0 for c in cells],
                   [c.occupant for c in cells],[1 if c.is_frozen else 0 for c in cells],
                   seat, v.is_priority_token,[c.base_points for c in cells],
                   [c.owner if c.is_home else 0 for c in cells], my_last)
        for i in range(4):
            if tr.cd[i] != g.cd[i]:
                if tr.cd[i] < g.cd[i]: safe += 1      # think they can shield; they can't
                else: risky += 1                       # think they're on cooldown; they aren't
        acts=[]
        for i in range(4):
            a=bots[i](vs[i])
            if a not in vs[i].legal_actions: a="STAY"
            acts.append(a)
        my_last=acts[seat-1]; g.step(acts)
print("cooldown errors in the SAFE direction (underestimate our window): %d" % safe)
print("cooldown errors in the RISKY direction (overestimate our window): %d" % risky)
