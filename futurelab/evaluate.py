"""Paired forward-planning trials on unused procedural opponent families."""
import argparse
import hashlib
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

import bot
import engine
import maps
from freshlab.evaluate import signature, summary
from futurelab import agent,opponents


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("bot.py","engine.py","maps.py","botlib.py","freshlab/population.py",
           "freshlab/evaluate.py","futurelab/models.py","futurelab/rollout.py",
           "futurelab/agent.py","futurelab/opponents.py","futurelab/evaluate.py")


def hashes():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def tasks(split,count,seed):
    rng = random.Random("future-tasks:%s:%d" % (split,seed))
    kinds = ("standard","noise","flat","edge","richhome","richcorner","inverted")
    if split == "final":
        kinds += ("corridors","pockets")
    result = []
    for i in range(count):
        s = rng.randrange(2**31)
        kind = kinds[i//16 % len(kinds)]
        if kind == "corridors":
            base = maps._mirror([[3 if r == 2 or c == 2 else 1 for c in range(4)] for r in range(4)])
        elif kind == "pockets":
            base = maps._mirror([[rng.choice((1,1,3)) for c in range(4)] for r in range(4)])
        else:
            base = maps.make(s,kind)
        result.append(dict(id=i,seat=i//4 % 4,token=1+i % 4,map_seed=s,
                           map_kind=kind,base=base,
                           specs=[opponents.sample(split,rng.randrange(2**31)) for _ in range(3)]))
    return result


def play(task,variant,native=False):
    params = dict(throttle=int(native),budget_ms=60 if native else 10000,first_turn_ms=0)
    kwargs = dict(seed=task["map_seed"],params=params)
    focal = bot.Agent(**kwargs) if variant == "baseline" else agent.FutureAgent(**kwargs,feature=agent.VARIANTS[variant])
    errors = []
    original = focal.decide
    def checked(view):
        try:
            return original(view)
        except Exception as e:
            errors.append(repr(e))
            raise
    focal.decide = checked
    others = iter(opponents.FutureOpponent(s) for s in task["specs"])
    bots = [focal if j == task["seat"] else next(others) for j in range(4)]
    game = engine.Game(base=task["base"],start_token=task["token"])
    digest = hashlib.sha256()
    worst,calls = 0.0,0
    while not game.over():
        actions = []
        for j,(policy,view) in enumerate(zip(bots,game.views())):
            before = signature(view)
            start = time.perf_counter()
            a = policy(view)
            elapsed = (time.perf_counter()-start)*1000
            if a not in view.legal_actions or before != signature(view):
                raise AssertionError("illegal action or mutated input")
            if j == task["seat"]:
                worst = max(worst,elapsed)
                if native and elapsed >= 200:
                    raise AssertionError("public deadline exceeded: %.2fms" % elapsed)
            actions.append(a)
            calls += 1
        game.step(actions)
        digest.update("|".join(actions).encode())
    if errors:
        raise AssertionError("swallowed planner failure: %s" % errors)
    me = task["seat"]
    pw = sum(1 if game.score[me] > s else 0.5 if game.score[me] == s else 0 for j,s in enumerate(game.score) if j != me)
    return dict(pw=pw,score=game.score[me],scores=game.score,calls=calls,max_ms=worst,
                action_hash=digest.hexdigest(),future_decisions=getattr(focal,"decisions",0),
                changed=getattr(focal,"changed",0),particles=getattr(focal,"particles_done",0))


def job(arg):
    task,variants,native = arg
    order = variants if task["id"] % 2 else variants[::-1]
    return dict(task=task,results={v:play(task,v,native) for v in order})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split",required=True,choices=opponents.SPLITS)
    ap.add_argument("--games",type=int,default=112)
    ap.add_argument("--seed",type=int,required=True)
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--variants",nargs="+",default=["baseline","prior24","future24","careful24","future36"])
    ap.add_argument("--native",action="store_true")
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--lock",type=Path)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("preserve measured results; use a fresh output file")
    if args.games < 4 or "baseline" not in args.variants or any(v not in agent.VARIANTS for v in args.variants):
        ap.error("include baseline and valid variants, at least four games")
    sources = hashes()
    if args.split == "final":
        if args.lock is None:
            ap.error("final requires a candidate registration")
        lock = json.loads(args.lock.read_text())
        if (sources != lock["sources"] or args.variants != ["baseline",lock["candidate"]]
                or args.seed != lock["seed"] or args.games != lock["games"] or args.native != lock["native"]):
            ap.error("final does not match registration")
    start = time.perf_counter()
    rows = []
    with mp.Pool(args.workers) as pool:
        for row in pool.imap(job,[(t,args.variants,args.native) for t in tasks(args.split,args.games,args.seed)],chunksize=1):
            rows.append(row)
            if len(rows) % 16 == 0:
                print("%d/%d %.1fs" % (len(rows),args.games,time.perf_counter()-start),flush=True)
    if hashes() != sources:
        raise AssertionError("source changed during measurement")
    report = summary(rows,args.variants)
    payload = dict(split=args.split,seed=args.seed,native=args.native,sources=sources,
                   variants={v:agent.VARIANTS[v] for v in args.variants},summary=report,
                   rows=rows,elapsed_seconds=time.perf_counter()-start,
                   caveat="Fresh scheduling families and parameters, shared public parsing/bookkeeping. Discovery comparisons exploratory. Conditional simulated futures are approximate opponent hypotheses; engine physics is exact, opponent forecasts are not.")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=1),encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
