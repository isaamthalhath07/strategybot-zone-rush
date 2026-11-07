"""Separate, source-bound evaluation of corrected continuation experiments."""
import argparse
import hashlib
import json
import multiprocessing as mp
import time
from pathlib import Path

from freshlab.evaluate import summary
from futurelab import agent,alternatives,evaluate


def hashes():
    result = evaluate.hashes()
    for p in ("futurelab/alternatives.py","futurelab/evaluate2.py"):
        result[p] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return result


def initialize():
    agent.FutureAgent = alternatives.ConsistentAgent
    agent.VARIANTS = alternatives.VARIANTS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split",choices=("discovery","development","final"),required=True)
    ap.add_argument("--games",type=int,default=112)
    ap.add_argument("--seed",type=int,required=True)
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--variants",nargs="+",default=list(alternatives.VARIANTS))
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--native",action="store_true")
    ap.add_argument("--lock",type=Path)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("preserve recorded evidence")
    if "baseline" not in args.variants or any(v not in alternatives.VARIANTS for v in args.variants):
        ap.error("include baseline and defined variants")
    sources = hashes()
    if args.split == "final":
        if args.lock is None:
            ap.error("register the final candidate before play")
        lock = json.loads(args.lock.read_text())
        if (lock["sources"] != sources or args.variants != ["baseline",lock["candidate"]]
                or args.games != lock["games"] or args.seed != lock["seed"] or args.native != lock["native"]):
            ap.error("candidate or test differs from registration")
    rows = []
    start = time.perf_counter()
    with mp.Pool(args.workers,initializer=initialize) as pool:
        for row in pool.imap(evaluate.job,[(t,args.variants,args.native) for t in evaluate.tasks(args.split,args.games,args.seed)],chunksize=1):
            rows.append(row)
            if len(rows) % 16 == 0:
                print("%d/%d %.1fs" % (len(rows),args.games,time.perf_counter()-start),flush=True)
    if hashes() != sources:
        raise AssertionError("sources changed")
    report = summary(rows,args.variants)
    payload = dict(split=args.split,seed=args.seed,native=args.native,sources=sources,
                   variants={v:alternatives.VARIANTS[v] for v in args.variants},summary=report,
                   rows=rows,elapsed_seconds=time.perf_counter()-start,
                   caveat="Corrected continuation, new seeds and per-game opponent parameters. Discovery comparisons exploratory. Opponent decision families are held out by split; discovery families were already used for earlier discovery, not falsely called held out here.")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=1),encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
