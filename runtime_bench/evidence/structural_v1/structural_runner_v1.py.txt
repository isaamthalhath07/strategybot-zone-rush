"""EXPERIMENTAL structural public-copy runner v1; zero primary credit.

Selected functions are exact copies of the hash-pinned base runner, with only
the public-view copy call replaced. No registration/execution/promotion CLI is
included. The production runner and live campaign remain unchanged.
"""
import hashlib
import math
from pathlib import Path
import time
from evolution.genomes import digest
from evolution.opponents import Rival
from tests import reference_engine as engine
from runtime_bench.public_copy_v1 import clone_public

ROOT = Path(__file__).resolve().parents[1]
BASE_RUNNER_SHA256 = 'bae5c92c51efa83eaef90db0ede9940be72201d2bb78e9d0527e3f6139d7503b'
if hashlib.sha256((ROOT/'evolution/runner.py').read_bytes()).hexdigest() != BASE_RUNNER_SHA256:
    raise ValueError('Experimental base runner no longer matches frozen source')
_CODE = {}

def signature(v):
    return (v.bot_id, v.is_priority_token, tuple(v.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in v.board for c in row))

def namespace(path, expected):
    path = Path(path)
    body = path.read_bytes()
    if digest(body) != expected:
        raise ValueError("Worker source hash mismatch")
    if expected not in _CODE:
        _CODE[expected] = compile(body, str(path), "exec")
    ns = {"__name__": "_trusted_evolution_player", "__file__": str(path)}
    exec(_CODE[expected], ns)  # Only locally pinned code; never code from results.
    return ns

def init_worker():
    # Keep the worker independent of parent module state, including resume runs.
    _CODE.clear()

def opponent(spec, sources):
    family = spec["family"]
    if family in ("planner", "research", "racer", "blocker"):
        source = sources[family]
        ns = namespace(source["path"], source["sha256"])
        if family in ("planner", "research"):
            ns["CONFIG"] = dict(spec["genes"])
        else:
            cls = ns["RacerBot" if family == "racer" else "BlockerBot"]
            ns["_CONSOLIDATED_PLAYERS"][spec["seat"]+1] = cls(seed=spec["seed"])
        return ns["act"], ns
    player = Rival(spec)
    return player.act, None

def play_game(candidate, fixture, sources):
    started = time.perf_counter()
    focal_ns = namespace(candidate["path"], candidate["sha256"])
    players, namespaces = [], []
    by_seat = {spec["seat"]: spec for spec in fixture["opponents"]}
    for seat in range(4):
        if seat == fixture["seat"]:
            players.append(focal_ns["act"])
            namespaces.append(focal_ns)
        else:
            act, ns = opponent(by_seat[seat], sources)
            players.append(act)
            namespaces.append(ns)
    game = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    actions, timing = [], [{"calls": 0, "total_ms": 0.0, "max_ms": 0.0,
                           "first_ms": 0.0, "regular_max_ms": 0.0} for _ in range(4)]
    while not game.over():
        chosen = []
        for seat, view in enumerate(game.views()):
            view = clone_public(view)
            if set(view.__slots__) != {"board", "bot_id", "is_priority_token", "legal_actions"}:
                raise ValueError("Actor observation contract changed")
            before = signature(view)
            call_start = time.perf_counter()
            action = players[seat](view)
            ms = (time.perf_counter()-call_start)*1000
            rec = timing[seat]
            rec["calls"] += 1
            rec["total_ms"] += ms
            rec["max_ms"] = max(rec["max_ms"], ms)
            if game.turn == 1:
                rec["first_ms"] = ms
            else:
                rec["regular_max_ms"] = max(rec["regular_max_ms"], ms)
            if action not in view.legal_actions or signature(view) != before:
                raise ValueError("Illegal action or input mutation")
            if ms > (2000 if game.turn == 1 else 200):
                raise ValueError("Decision deadline exceeded; reject this comparison")
            ns = namespaces[seat]
            if ns and (ns.get("_input_failures", 0) or ns.get("_policy_failures", 0)):
                raise ValueError("Policy used a hidden failure fallback")
            # Referee-only oracle audit AFTER the public-input decision. Private
            # counters never reach an actor, candidate genome, or search feature.
            memory = ns.get("_history", {}).get(seat+1, {}) if ns else {}
            if "cooldown_possible" in memory:
                if (memory.get("inference_failures", 0) or memory["progress"] != game.prog[seat]
                        or memory["scores"][1:] != game.score
                        or any(game.cd[i] not in memory["cooldown_possible"][i+1] for i in range(4))):
                    raise ValueError("Public-history tracker lost referee-consistent possibilities")
            chosen.append(action)
        actions.append(chosen)
        game.step(chosen)
    seat = fixture["seat"]
    pw = sum(1 if game.score[seat] > other else 0.5 if game.score[seat] == other else 0
             for j, other in enumerate(game.score) if j != seat)
    return dict(candidate=candidate["sha256"], fixture=fixture["id"], map_id=fixture["map_id"], focal_seat=seat,
                field=fixture["field"], scores=game.score, focal_pw=pw, focal_score=game.score[seat],
                opponent_ids=[s["id"] for s in fixture["opponents"]], actions=actions,
                timing=timing, faults=[], elapsed_s=time.perf_counter()-started)

def verify_row(row, candidate, fixture):
    if row["candidate"] != candidate["sha256"] or row["fixture"] != fixture["id"]:
        raise ValueError("Result belongs to another registered task")
    if row["map_id"] != fixture["map_id"] or row["field"] != fixture["field"] or row["focal_seat"] != fixture["seat"]:
        raise ValueError("Result map/field mismatch")
    if row["opponent_ids"] != [s["id"] for s in fixture["opponents"]] or row["faults"]:
        raise ValueError("Opponent identities changed or faults occurred")
    if len(row["actions"]) != 80 or any(len(a) != 4 for a in row["actions"]):
        raise ValueError("Incomplete game")
    g = engine.Game(base=fixture["base"], start_token=fixture["token"], rules={"catch_requires_stay": True})
    for actions in row["actions"]:
        if any(action not in g.legal(i) for i, action in enumerate(actions)):
            raise ValueError("Recorded illegal action")
        g.step(actions)
    seat = fixture["seat"]
    pw = sum(1 if g.score[seat] > x else 0.5 if g.score[seat] == x else 0 for i, x in enumerate(g.score) if i != seat)
    if row["scores"] != g.score or row["focal_pw"] != pw or row["focal_score"] != g.score[seat]:
        raise ValueError("Score does not replay")
    if len(row["timing"]) != 4:
        raise ValueError("Invalid callback records")
    for timing in row["timing"]:
        if type(timing["calls"]) is not int or timing["calls"] != 80:
            raise ValueError("Invalid callback count")
        for key in ("max_ms", "total_ms", "first_ms", "regular_max_ms"):
            if type(timing[key]) not in (float, int) or not math.isfinite(timing[key]) or timing[key] < 0:
                raise ValueError("Invalid callback duration")
        if (timing["first_ms"] > 2000 or timing["regular_max_ms"] > 200
                or timing["max_ms"] != max(timing["first_ms"], timing["regular_max_ms"])
                or timing["total_ms"] < timing["max_ms"]):
            raise ValueError("Invalid or late callback record")
