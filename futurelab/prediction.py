"""Prequential ownership forecasts on fixed baseline trajectories.

Future public boards are labels only. They never enter a played policy or an
earlier forecast. Game-level paired errors avoid treating 64 cells or repeated
turns as independent experimental units.
"""
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path

from baselines import v8 as bot
import engine
from botlib import parse
from futurelab import agent,evaluate,models,opponents,rollout


def forecast(player,board,beliefs,action):
    world = rollout.reconstruct(board,player.tr)
    seat = player.seat-1
    R = 81-world.turn
    care = player._care(seat+1,R)
    proposals = agent.routes(player,board[1],board[2],board[0],world.home,board[4],
                             seat+1,world.pos[seat],R,max(1,player.P["kappa"]*R),care)
    if not proposals or proposals[0][0][0] != player.plan_target:
        return {}
    hist = {h:[[0.0]*5 for p in range(64)] for h in (4,8,16) if world.turn+h <= 80}
    if not hist:
        return {}
    particles = 6
    for sample in range(particles):
        profiles = [beliefs.profile(j,sample,particles,True) for j in range(4)]
        initial = world.clone()
        if not player.tr.token_known:
            initial.token = [j for j in range(1,5) if j != seat+1][sample % 3]
        _,_,traces = rollout.simulate(initial,seat,proposals[0],profiles,sample,max(hist),True,first_action=action)
        for h,rows in hist.items():
            for p,o in enumerate(traces[h-1][0]):
                rows[p][o] += 1/particles
    return hist


def job(task):
    player = bot.Agent(seed=task["map_seed"],params={"throttle":0,"budget_ms":10000})
    player.seat = task["seat"]+1
    beliefs = models.Beliefs()
    others = iter(opponents.FutureOpponent(s) for s in task["specs"])
    bots = [player if j == task["seat"] else next(others) for j in range(4)]
    game = engine.Game(base=task["base"],start_token=task["token"])
    pending = {}
    totals = {h:{k:[0.0,0] for k in ("persistence","raw","shrunk")} for h in (4,8,16)}
    while not game.over():
        views = game.views()
        board = parse(views[task["seat"]])
        for h,old,predicted in pending.pop(game.turn,[]):
            for p,actual in enumerate(board[1]):
                previous = old[p]
                persistent = [float(previous == o) for o in range(5)]
                shrunk = [(a+b)/2 for a,b in zip(predicted[p],persistent)]
                for name,probs in (("persistence",persistent),("raw",predicted[p]),("shrunk",shrunk)):
                    error = sum((v-float(actual == o))**2 for o,v in enumerate(probs))
                    totals[h][name][0] += error
                    totals[h][name][1] += 1
        beliefs.observe(board)
        actions = [b(v) for b,v in zip(bots,views)]
        if game.turn % 8 == 1 and actions[task["seat"]] != "SHIELD":
            hist = forecast(player,board,beliefs,actions[task["seat"]])
            for h,predicted in hist.items():
                pending.setdefault(game.turn+h,[]).append((h,board[1][:],predicted))
        beliefs.predict(rollout.reconstruct(board,player.tr),board)
        game.step(actions)
    return dict(task=task,errors={h:{name:a/max(1,n) for name,(a,n) in group.items()} for h,group in totals.items()},
                cells={h:group["raw"][1] for h,group in totals.items()})


def main():
    out = Path("futurelab/results/prediction.json")
    if out.exists():
        raise SystemExit("preserve prior prediction evaluation")
    sources = evaluate.hashes()
    extra = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with mp.Pool(8) as pool:
        rows = list(pool.imap(job,evaluate.tasks("discovery",56,531881),chunksize=1))
    if sources != evaluate.hashes() or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != extra:
        raise AssertionError("prediction sources changed")
    report = {}
    for h in (4,8,16):
        usable = [r for r in rows if r["cells"][h]]
        report[h] = {}
        for name in ("persistence","raw","shrunk"):
            values = [r["errors"][h][name] for r in usable]
            delta = [r["errors"][h][name]-r["errors"][h]["persistence"] for r in usable]
            mean = sum(delta)/len(delta)
            se = math.sqrt(sum((x-mean)**2 for x in delta)/max(1,len(delta)-1)/len(delta))
            report[h][name] = dict(games=len(usable),brier=sum(values)/len(values),
                                 difference=mean,ci95=[mean-2*se,mean+2*se])
    payload = dict(seed=531881,sources=sources,extra_sources={"futurelab/prediction.py":extra},
                   summary=report,rows=rows,
                   caveat="Five-class ownership Brier loss on future public boards, averaged per game. Baseline plays unchanged. Scores measure prediction, not policy improvement. Raw and 50-percent persistence-shrunk forecasts were defined before labels.")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=1),encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
