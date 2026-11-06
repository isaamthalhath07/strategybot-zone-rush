import random, engine, mybot, zoo
base = engine.make_map(seed=3)
rnd = random.Random(3)
g = engine.Game(base=base, start_token=1)
bots = [zoo.GreedyShieldBot(1), zoo.RaiderBot(2), zoo.BaiterBot(3), zoo.CamperBot(4)]
tr = mybot.Tracker(); seat = 1
hist = []
while not g.over():
    vs = g.views(); v = vs[seat-1]
    cells = [v.board[r][c] for r in range(8) for c in range(8)]
    owner=[c.owner for c in cells]; upg=[1 if c.is_upgraded else 0 for c in cells]
    occ=[c.occupant for c in cells]; frz=[1 if c.is_frozen else 0 for c in cells]
    home=[c.owner if c.is_home else 0 for c in cells]; bse=[c.base_points for c in cells]
    pre_cd = g.cd[:]; pre_fr = g.frozen[:]; pre_prog = g.prog[:]
    tr.observe(owner,upg,occ,frz,seat,v.is_priority_token,bse,home)
    if tr.cd != pre_cd or tr.prog != pre_prog:
        print("=== first mismatch at turn", g.turn)
        print(" engine cd  ", pre_cd, " tracker cd  ", tr.cd)
        print(" engine prog", pre_prog, " tracker prog", tr.prog)
        print(" engine frz ", pre_fr, " tracker frz ", tr.frozen)
        print(" last 3 turns of real effective actions:")
        for h in hist[-3:]:
            print("   turn %2d eff=%s cd_after=%s frozen_after=%s prog_after=%s"
                  % (h[0], h[1], h[2], h[3], h[4]))
        break
    acts=[]
    for i in range(4):
        a = bots[i](vs[i])
        if a not in vs[i].legal_actions: a="STAY"
        acts.append(a)
    eff = g.step(acts)
    hist.append((g.turn-1, eff, g.cd[:], g.frozen[:], g.prog[:]))
