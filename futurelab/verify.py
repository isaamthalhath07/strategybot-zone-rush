"""Verify exported behaviour separately from statistical playing strength."""
import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import time
from pathlib import Path
from functools import partial

import engine
from freshlab.evaluate import signature
from futurelab import bounded,evaluate,opponents,protocol


ARTIFACT = Path("futurelab/submission/bot.py")


def load(artifact=ARTIFACT):
    spec = importlib.util.spec_from_file_location("future_submission",artifact)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expose_errors(player,errors):
    original = player.decide
    def checked(view):
        try:
            return original(view)
        except Exception as e:
            errors.append(repr(e))
            raise
    player.decide = checked


def equivalent(task, artifact=ARTIFACT):
    module = load(artifact)
    feature = module.FUTURE_FEATURES
    params = {"throttle":0,"budget_ms":10000,"first_turn_ms":0}
    expected = bounded.BoundedAgent(seed=task["map_seed"],params=params,feature=feature)
    actual = module.Agent(seed=task["map_seed"],params=params)
    failures = []
    expose_errors(expected,failures)
    expose_errors(actual,failures)
    others = iter(opponents.FutureOpponent(s) for s in task["specs"])
    bots = [expected if j == task["seat"] else next(others) for j in range(4)]
    game = engine.Game(base=task["base"],start_token=task["token"])
    calls = 0
    while not game.over():
        actions = []
        for j,(b,view) in enumerate(zip(bots,game.views())):
            before = signature(view)
            action = b(view)
            if j == task["seat"]:
                exported = actual(view)
                if exported != action:
                    raise AssertionError(("export diverged",task["id"],game.turn,action,exported))
                calls += 1
            if action not in view.legal_actions or signature(view) != before:
                raise AssertionError("input/output contract")
            actions.append(action)
        game.step(actions)
    if failures:
        raise AssertionError(failures)
    return calls


def public_contract(module):
    calls,worst = 0,0.0
    for case,base in enumerate((engine.make_map(seed=6721),[1]*64,[3]*64,engine.make_map(seed=6723))):
        game = engine.Game(base=base,start_token=case+1)
        while not game.over():
            actions = []
            for view in game.views():
                if case == 1:
                    view.board = [c for row in view.board for c in row]
                elif case == 2:
                    view.board = tuple(tuple(row) for row in view.board)
                # General snapshot supports both documented board shapes.
                cells = view.board if not isinstance(view.board[0],(tuple,list)) else [c for row in view.board for c in row]
                before = (view.bot_id,view.is_priority_token,tuple(view.legal_actions),
                          tuple((c.owner,c.occupant,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for c in cells))
                start = time.perf_counter()
                action = module.act(view)
                elapsed = (time.perf_counter()-start)*1000
                after = (view.bot_id,view.is_priority_token,tuple(view.legal_actions),
                         tuple((c.owner,c.occupant,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for c in cells))
                if before != after or action not in view.legal_actions or elapsed >= (2000 if game.turn == 1 else 200):
                    raise AssertionError(("public entry point failed",case,game.turn,action,elapsed))
                actions.append(action)
                worst = max(worst,elapsed)
                calls += 1
            game.step(actions)
        print("Public entry game %d passed" % (case+1),flush=True)
    return calls,worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--artifact",type=Path,default=ARTIFACT,
                    help="artifact to verify; rebuilt research exports need --quick")
    ap.add_argument("--report",type=Path,default=Path("futurelab/research_release_verification.json"))
    args = ap.parse_args()
    artifact = args.artifact.resolve()
    manifest = json.loads(artifact.with_suffix(".manifest.json").read_text())
    for filename,expected in manifest["sources"].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
            raise AssertionError("source changed: "+filename+"; historical verification requires commit 9df9497, or rebuild separately and use --artifact PATH --quick")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if manifest["sha256"] != sha:
        raise AssertionError("artifact changed")
    module = load(artifact)
    if module.FUTURE_FEATURES != protocol.REGISTRY[manifest["candidate"]]:
        raise AssertionError("wrong exported features")
    with mp.Pool(4) as pool:
        exact = sum(pool.imap(partial(equivalent,artifact=artifact),evaluate.tasks("development",8,1047121),chunksize=1))
    print("Exact exported actions:",exact,flush=True)
    if args.quick:
        return
    frozen = json.loads(Path("futurelab/submission/bot.manifest.json").read_text())
    if sha != frozen["sha256"] or manifest != frozen:
        raise AssertionError("rebuilt code has no new strength confirmation; use --quick for behavior checks and register fresh trials before promotion")
    primary = json.loads(Path("futurelab/results/final.json").read_text())
    native = json.loads(Path("futurelab/results/native_confirmation.json").read_text())
    if primary["summary"]["one_job"]["ci95"][0] <= 0 or native["summary"]["one_job"]["ci95"][0] <= 0:
        raise AssertionError("do not promote an unconfirmed candidate")
    calls,worst = public_contract(module)
    payload = dict(sha256=sha,manifest=manifest,exact_actions=exact,public_calls=calls,
                   worst_public_ms=worst,primary_sha256=hashlib.sha256(Path("futurelab/results/final.json").read_bytes()).hexdigest(),
                   native_sha256=hashlib.sha256(Path("futurelab/results/native_confirmation.json").read_bytes()).hexdigest(),
                   note="Source flattening matches research policy with clocks disabled. Actual entry point passes four shared-module games including flat/tuple boards and state reuse. No universality or Elo guarantee.")
    if args.report.exists():
        raise AssertionError("preserve existing verification evidence; choose a new --report")
    args.report.write_text(json.dumps(payload,indent=2),encoding="utf-8",newline="\n")
    print(json.dumps(payload,indent=2))


if __name__ == "__main__":
    main()
