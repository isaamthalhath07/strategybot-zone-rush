"""Immutable, resumable branch comparison with audited public callbacks."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"simulator/vendor_harness"))
from tools import benchmark
import match
from referee import DEFAULT_RULES,Referee,pairwise


WORKER = ROOT/"tools/audit_worker.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AuditProcess(match.BotProcess):
    def __init__(self,path,diagnostic=False):
        super().__init__(path)
        self.diagnostic = diagnostic
        self.audit_message = {}

    def receive(self,timeout):
        result = super().receive(timeout)
        self.audit_message = result
        return result

    def send(self,message):
        if self.diagnostic and message.get("cmd")=="act" and message["turn"] % 8 == 1:
            message = dict(message,audit_trace=True)
        return super().send(message)

    def act(self,observation,turn,timing):
        result = super().act(observation,turn,timing)
        extra = self.audit_message
        result["input_mutated"] = bool(extra.get("mutated"))
        result["handled_exceptions"] = extra.get("handled_exceptions",[])
        if result["input_mutated"] and result["status"]=="ok":
            result.update(status="input-mutation",used="STAY",error="public input changed")
        return result


def job(candidate,fixture,sources,rules,timing,diagnostic):
    assignment = list(fixture["opponents"])
    assignment.insert(fixture["seat"],candidate)
    workers = [AuditProcess(str((ROOT/sources[name]["path"]).resolve()),diagnostic and i==fixture["seat"])
               for i,name in enumerate(assignment)]
    stats = [dict(calls=0,total_ms=0.0,max_ms=0.0) for _ in range(4)]
    faults,actions,exceptions = [],[],[]
    started = time.perf_counter()
    complete = False
    try:
        for worker in workers:
            worker.spawn()
        for i,worker in enumerate(workers):
            result = worker.finish_load(timing["load_s"])
            if not result["ok"]:
                faults.append(dict(turn=0,seat=i,source=assignment[i],status="load",error=result["error"]))
        game = Referee(fixture["base"],rules=rules,start_token=fixture["token"])
        while not game.over():
            chosen = []
            for i,worker in enumerate(workers):
                view = game.observation(i+1)
                assert set(view)=={"board","bot_id","is_priority_token","legal_actions"}
                result = worker.act(view,game.turn,timing)
                stats[i]["calls"] += 1
                ms = result.get("ms") or 0.0
                stats[i]["total_ms"] += ms
                stats[i]["max_ms"] = max(stats[i]["max_ms"],ms)
                if result["status"]!="ok":
                    faults.append(dict(turn=game.turn,seat=i,source=assignment[i],status=result["status"],
                                       ms=ms,error=result.get("error"),input_mutated=result["input_mutated"]))
                if result["handled_exceptions"]:
                    exceptions.append(dict(turn=game.turn,source=assignment[i],events=result["handled_exceptions"]))
                chosen.append(result["used"])
            actions.append(chosen)
            game.step(chosen)
            if diagnostic and sum(f["source"]==candidate for f in faults)>=3:
                break
        complete = game.over()
        pw = [3*p for p in pairwise(game.score)]
        return dict(candidate=candidate,fixture=fixture["id"],map_group=fixture["map_group"],
                    field=fixture["field"],focal_seat=fixture["seat"],assignment=assignment,
                    complete=complete,scores=game.score,pw=pw,focal_pw=pw[fixture["seat"]],
                    focal_score=game.score[fixture["seat"]],timing=stats,faults=faults,
                    handled_exceptions=exceptions,actions=actions,elapsed_s=time.perf_counter()-started)
    finally:
        for worker in workers:
            worker.close()


def run(spec_path,out,workers,resume=False):
    if out.exists():
        raise ValueError("never overwrite consumed outcomes")
    spec = json.loads(spec_path.read_text())
    sources = {s["name"]:s for s in spec["sources"]}
    used = set(spec["candidates"]) | {n for f in spec["fixtures"] for n in f["opponents"]}
    guards = {str(ROOT/sources[n]["path"]):sources[n]["sha256"] for n in used}
    for p in (Path(__file__),WORKER,Path(benchmark.__file__),Path(match.__file__),
              ROOT/"simulator/vendor_harness/referee.py",spec_path):
        guards[str(p)] = sha(p)
    for p,expected in guards.items():
        if sha(p)!=expected:
            raise AssertionError("source hash mismatch: "+p)
    rules = dict(DEFAULT_RULES,**spec["rules"])
    if rules["catch_requires_stay"] is not True:
        raise ValueError("this campaign uses explicitly registered effective-STAY rules")
    diagnostic = spec.get("diagnostic",False)
    timing = dict(match.DEFAULT_TIMING,hard_s=8.0 if diagnostic else 1.0,load_s=5.0)
    if diagnostic:
        timing.update(enforce=False,turn_ms=5000,first_ms=5000)
    registration_path = out.with_suffix(".registration.json")
    journal_path = out.with_suffix(".journal.jsonl")
    registration = dict(spec=spec,timing=timing,rules=rules,
                        guards={str(Path(p).relative_to(ROOT)).replace("\\","/"):h for p,h in guards.items()},
                        note="Exception tracing is sampled only in diagnostic mode; its timings are not competition timings. State fingerprints are outside measured callback time. Matched strength games use actual 200ms / 2s limits.")
    out.parent.mkdir(parents=True,exist_ok=True)
    rows,done = [],set()
    if registration_path.exists():
        if not resume or json.loads(registration_path.read_text())!=registration:
            raise ValueError("existing registration; resume only identical code/spec")
        if journal_path.exists():
            for line in journal_path.read_text().splitlines():
                row = json.loads(line)
                key = (row["candidate"],row["fixture"])
                if key in done:
                    raise ValueError("duplicate completed fixture")
                rows.append(row)
                done.add(key)
    else:
        registration_path.write_text(json.dumps(registration,indent=2),encoding="utf8",newline="\n")
    match.WORKER = str(WORKER)
    jobs = [(n,f) for n in spec["candidates"] for f in spec["fixtures"] if (n,f["id"]) not in done]
    started = time.perf_counter()
    with journal_path.open("a",encoding="utf8",newline="\n") as journal:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = [pool.submit(job,n,f,sources,rules,timing,diagnostic) for n,f in jobs]
            for future in as_completed(pending):
                row = future.result()
                journal.write(json.dumps(row,separators=(",",":"))+"\n")
                journal.flush()
                os.fsync(journal.fileno())
                rows.append(row)
                if len(rows)%32==0 or len(rows)==len(done)+len(jobs):
                    print("%s %d/%d (%.1fs)" % (spec["id"],len(rows),len(done)+len(jobs),time.perf_counter()-started),flush=True)
    for p,expected in guards.items():
        if sha(p)!=expected:
            raise AssertionError("source changed during evaluation: "+p)
    rows.sort(key=lambda r:(r["candidate"],r["fixture"]))
    summary = benchmark.summarize(rows)
    pairs = [] if diagnostic or len(summary)>16 else benchmark.paired(rows,list(summary))
    result = dict(registration=registration,summary=summary,paired=pairs,games=rows,
                  elapsed_s=time.perf_counter()-started,
                  caveat="Frozen candidates; no weight fitting. Branch ranking is conditional on registered fields. Diagnostic scores are not strength evidence. Final intervals cluster matched results by distinct board contents, not by individual turns.")
    with gzip.open(out,"wt",encoding="utf8",newline="\n") as stream:
        json.dump(result,stream,separators=(",",":"))
    concise = {k:v for k,v in result.items() if k not in ("registration","games")}
    concise.update(games=len(rows),timed_callbacks=sum(s["calls"] for r in rows for s in r["timing"]),
                   all_faults=sum(len(r["faults"]) for r in rows))
    out.with_suffix(".summary.json").write_text(json.dumps(concise,indent=2),encoding="utf8",newline="\n")
    print(json.dumps({k:v for k,v in concise.items() if k!="paired"},indent=2),flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--resume",action="store_true")
    args = parser.parse_args()
    run(args.spec.resolve(),args.out.resolve(),args.workers,args.resume)


if __name__=="__main__":
    main()
