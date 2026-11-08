"""Frozen corrected-policy protocol, including the matched prior-only control."""
import argparse
import hashlib
import json
import multiprocessing as mp
import time
from pathlib import Path

from freshlab.evaluate import summary
from futurelab import agent,alternatives,evaluate,evaluate2


REGISTRY = dict(alternatives.VARIANTS)
REGISTRY["prior_one_job"] = dict(alternatives.VARIANTS["one_job"],learned=False)


def hashes():
    sources = evaluate2.hashes()
    sources["futurelab/protocol.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return sources


def initialize():
    agent.FutureAgent = alternatives.ConsistentAgent
    agent.VARIANTS = REGISTRY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split",choices=("discovery","development","final"),required=True)
    ap.add_argument("--games",type=int,required=True)
    ap.add_argument("--seed",type=int,required=True)
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--variants",nargs="+",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--native",action="store_true")
    ap.add_argument("--lock",type=Path)
    args = ap.parse_args()
    if args.out.exists() or "baseline" not in args.variants or any(v not in REGISTRY for v in args.variants):
        ap.error("use a new output, a baseline and valid variants")
    sources = hashes()
    if args.split == "final":
        if args.lock is None:
            ap.error("final requires registration before play")
        lock = json.loads(args.lock.read_text())
        if (sources != lock["sources"] or args.variants != ["baseline",lock["candidate"]]
                or args.seed != lock["seed"] or args.games != lock["games"] or args.native != lock["native"]):
            ap.error("final differs from registration")
    start,rows = time.perf_counter(),[]
    with mp.Pool(args.workers,initializer=initialize) as pool:
        for row in pool.imap(evaluate.job,[(t,args.variants,args.native) for t in evaluate.tasks(args.split,args.games,args.seed)],chunksize=1):
            rows.append(row)
            if len(rows) % 16 == 0:
                print("%d/%d %.1fs" % (len(rows),args.games,time.perf_counter()-start),flush=True)
    if sources != hashes():
        raise AssertionError("sources changed")
    report = summary(rows,args.variants)
    payload = dict(split=args.split,seed=args.seed,native=args.native,sources=sources,
                   variants={v:REGISTRY[v] for v in args.variants},summary=report,rows=rows,
                   elapsed_seconds=time.perf_counter()-start,
                   caveat="Matched learned/prior controls, corrected receding continuation. New random opponents per game, architectures disjoint by discovery/development/final. Synthetic field, shared observation infrastructure. Native runs retain actual wall-clock budgets.")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=1),encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
