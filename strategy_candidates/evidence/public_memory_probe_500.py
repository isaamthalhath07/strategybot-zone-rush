import copy,random
from tests import reference_engine as engine
from evolution.oversight import referee,state_equal
from strategy_candidates.test_public_memory import CORRECTED
fail=[]; observed=0; shields=0
for seed in range(500):
    rng=random.Random(0x55A17+seed)
    g=engine.Game(base=engine.make_map(seed=seed), start_token=1+seed%4, rules={'catch_requires_stay':True})
    other=referee.Referee(g.base,start_token=g.token,rules=g.rules)
    players=[CORRECTED(seed=i+1) for i in range(4)]
    trace=[]
    for turn in range(81):
        views=g.views()
        for i,view in enumerate(views):
            players[i]._observe(copy.deepcopy(view)); observed+=1
            if players[i].prog != g.prog[i]:
                fail.append(dict(seed=seed,turn=g.turn,seat=i,actual=g.prog[i],inferred=players[i].prog,trace=trace))
                break
        if fail or turn==80: break
        joint=[]
        for i,view in enumerate(views):
            legal=list(view.legal_actions)
            weighted=legal+(['STAY']*4)+(['SHIELD']*2 if 'SHIELD' in legal else [])
            a=rng.choice(weighted); joint.append(a); players[i].last=a
        shields+=joint.count('SHIELD'); trace.append(joint)
        g.step(joint);other.step(joint);state_equal(g,other)
    if fail: break
print(dict(seeds_completed=seed+1,public_observations=observed,shield_actions=shields,failures=len(fail),primary_credit=0))
if fail:
    import json
    from pathlib import Path
    Path('.cache/independent_public_memory_failure.json').write_text(json.dumps(fail[0]))
    print({k:v for k,v in fail[0].items() if k!='trace'})
