import sys, os, random, collections
sys.path.insert(0,'apex'); sys.path.insert(0,'.'); sys.path.insert(0,'crossfield')
import agent, engine, xfield, zarena
agent.FLAGS.update({"rollout": 0})
names = [n for g in ("main","indep","research","shipped","weak","opp_orig","opp_llm") for n in zarena.GROUPS[g]]
rnd = random.Random(7)
maxhits = collections.defaultdict(list)
alive_turns = collections.defaultdict(list)
for gi in range(int(sys.argv[1])):
    agent._SEATS.clear()
    opps = [rnd.choice(names) for _ in range(3)]
    seat = rnd.randrange(4)
    lineup = opps[:seat] + ["*"] + opps[seat:]
    g = engine.Game(base=xfield.make_map(rnd.choice(["slope","balanced","patchy"]), rnd.randrange(1<<30)), start_token=rnd.randint(1,4))
    bots = [agent.act if n == "*" else zarena.opponent(n)(i) for i, n in enumerate(lineup)]
    while not g.over():
        vs = xfield._views(g, rnd.random() < 0.5)
        acts = []
        for i in range(4):
            a = bots[i](vs[i]); acts.append(a if a in vs[i].legal_actions else "STAY")
        g.step(acts)
        ag = agent._SEATS[seat+1].agent
        for s, m in ag.mirrors.items():
            if any(h[1] for h in m.hyps):
                alive_turns[lineup[s-1]].append(g.turn)
    ag = agent._SEATS[seat+1].agent
    for s, m in ag.mirrors.items():
        maxhits[lineup[s-1]].append(max(h[2] for h in m.hyps))
evo = {"evolved","fused","evolved_tc","economic_b9fdc45f4957","economic_f04298fe614d","economic_11c655468adf"}
print("non-E bots: max evidence before death (top)")
rows = sorted(((max(v), sum(v)/len(v), n) for n, v in maxhits.items() if n not in evo), reverse=True)[:15]
for mx, av, n in rows: print("  %-28s max %3d mean %5.1f" % (n, mx, av))
print("E-family:", [(n, min(v), sum(v)/len(v)) for n, v in maxhits.items() if n in evo])
