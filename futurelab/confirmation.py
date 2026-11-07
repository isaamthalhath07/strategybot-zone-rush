"""Further unused opponents and actual interruptible-runtime confirmation."""
import argparse
import hashlib
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

import bot
import maps
from botlib import NEIGH,first_step,man
from freshlab.population import ProceduralOpponent,specification
from freshlab.evaluate import summary
from futurelab import agent,bounded,evaluate,protocol


FAMILIES = ("action_beam","deadline_portfolio","regret_bid","randomized_blocks")


def action_beam(player):
    R = player.R
    mine = sum(1<<p for p in range(64) if player.owner[p] == player.seat)
    upgraded = sum(1<<p for p in range(64) if player.upg[p] and player.owner[p] == player.seat)
    beam = [(0.0,player.me,mine,upgraded,player.progress[player.seat-1],None)]
    best = "STAY"
    for elapsed in range(min(R,player.spec["lookahead"])):
        nxt = {}
        for value,pos,own,up,progress,first in beam:
            options = [("STAY",pos)]+[(bot.STEP_NAME[(pos,p)],p) for p in NEIGH[pos] if p not in player.closed]
            for action,p in options:
                newown,newup,np = own,up,0
                gain = 0.0
                if action == "STAY":
                    if own>>p & 1:
                        if not up>>p & 1:
                            np = progress+1
                            if np>=3:
                                newup |= 1<<p
                                np = 0
                                gain = player.base[p]*(R-elapsed)*player.spec["upgrade"]
                    elif not player.home[p]:
                        needed = 3 if player.owner[p] and player.upg[p] else 1
                        np = progress+1
                        if np>=needed:
                            np = 0
                            newown |= 1<<p
                            gain = player.base[p]*(R-elapsed)*player.spec["claim"]
                            if player.owner[p]:
                                gain = (gain+8*player.base[p]*(2 if player.upg[p] else 1))*player.spec["raid"]*0.5
                f = action if first is None else first
                state = (p,newown,newup,np)
                total = value+gain
                if state not in nxt or total>nxt[state][0]:
                    nxt[state] = (total,f)
        if not nxt:
            break
        ranked = sorted(nxt.items(),key=lambda kv:kv[1][0]+0.15*kv[0][3]*player.base[kv[0][0]]*(R-elapsed),reverse=True)[:16]
        beam = [(v,p,o,u,prog,f) for (p,o,u,prog),(v,f) in ranked]
        best = beam[0][-1]
    return best


class ConfirmationOpponent(ProceduralOpponent):
    def __init__(self,spec):
        super().__init__(spec)
        self.block = None

    def choose(self,state):
        if len(state.legal_actions)==1:
            return state.legal_actions[0]
        if self.shield(state):
            return "SHIELD"
        family = self.spec["family"]
        if family == "action_beam":
            return action_beam(self)
        jobs = self.jobs()
        if not jobs:
            return "STAY"
        if family == "randomized_blocks":
            blocks = {k:[] for k in range(16)}
            for job in jobs:
                p = job[0]
                blocks[(p//8//2)*4+p%8//2].append(job)
            if self.block is None or not blocks[self.block]:
                values = {k:sum(g/(c+2) for p,g,c,d,n in v) for k,v in blocks.items() if v}
                top = sorted(values,key=values.get,reverse=True)[:3]
                self.block = self.rng.choices(top,[values[k] for k in top])[0]
            active = blocks[self.block]
            best = max(active,key=lambda j:j[1]/j[2])[0]
            if self.turn % self.spec["period"] == 0:
                self.block = None
        else:
            scores = {}
            for p,g,c,d,n in jobs:
                rival = min(man(q,p) for j,q in enumerate(self.pos) if j != self.seat-1)
                if family == "deadline_portfolio":
                    expiring = self.owner[p] == 0 and rival <= d+2
                    safe_upgrade = self.owner[p] == self.seat and rival >= 4
                    priority = 1.8 if expiring else 1.3 if safe_upgrade else 0.9
                    scores[p] = g/(c**0.9)*priority
                else:
                    # A relative opportunity bid responds to actual population
                    # positions instead of selecting a fixed map direction.
                    opponent_rate = self.base[p]*self.R/max(1,rival+1)
                    scores[p] = g/c-0.35*opponent_rate+0.20*g/max(1,rival+1)
            best = max(scores,key=scores.get)
        self.target = best
        return "STAY" if best == self.me else first_step(self.me,best,self.closed) or "STAY"


def tasks(count,seed):
    rng = random.Random("native-foresight:%d" % seed)
    kinds = ("standard","noise","flat","edge","richhome","richcorner","inverted")
    result = []
    for i in range(count):
        s = rng.randrange(2**31)
        specs = []
        for _ in range(3):
            spec = specification("train",rng.randrange(2**31))
            spec.update(family=rng.choice(FAMILIES),lookahead=rng.randrange(6,10),period=rng.randrange(7,16))
            specs.append(spec)
        kind = kinds[i//16 % len(kinds)]
        result.append(dict(id=i,seat=i//4 % 4,token=1+i % 4,map_seed=s,map_kind=kind,
                           base=maps.make(s,kind),specs=specs))
    return result


def hashes():
    result = protocol.hashes()
    for p in ("futurelab/bounded.py","futurelab/confirmation.py"):
        result[p] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return result


def initialize():
    agent.FutureAgent = bounded.BoundedAgent
    agent.VARIANTS = protocol.REGISTRY
    evaluate.opponents.FutureOpponent = ConfirmationOpponent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games",type=int,default=448)
    ap.add_argument("--seed",type=int,default=934871)
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--out",type=Path,default=Path("futurelab/results/native_confirmation.json"))
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("preserve independent confirmation")
    sources = hashes()
    registration = dict(candidate="one_job",games=args.games,seed=args.seed,native=True,
                        sources=sources,criterion="Same selected single-job policy, with internal interruptible runtime. Require positive lower endpoint of aggregate paired interval, no illegal/mutated/late actions, and inspect all map/seat groups. No tuning or filtering on this further field.")
    Path("futurelab/native_registration.json").write_text(json.dumps(registration,indent=2),encoding="utf-8",newline="\n")
    variants = ["baseline","one_job"]
    rows = []
    start = time.perf_counter()
    with mp.Pool(args.workers,initializer=initialize) as pool:
        for row in pool.imap(evaluate.job,[(t,variants,True) for t in tasks(args.games,args.seed)],chunksize=1):
            rows.append(row)
            if len(rows) % 16 == 0:
                print("%d/%d %.1fs" % (len(rows),args.games,time.perf_counter()-start),flush=True)
    if sources != hashes():
        raise AssertionError("sources changed")
    report = summary(rows,variants)
    payload = dict(split="native_confirmation",seed=args.seed,native=True,sources=sources,
                   variants={v:protocol.REGISTRY[v] for v in variants},summary=report,rows=rows,
                   elapsed_seconds=time.perf_counter()-start,
                   caveat="Four additional newly authored scheduling rules, including action-level search. No training or selection on them. Actual bounded runtime against 200ms/turn. Same shared public observation plumbing; synthetic opponents.")
    args.out.write_text(json.dumps(payload,indent=1),encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
