"""Generate inspectable Zone Rush replays from the local reference engine.

This is an observer/replay tool, not the official StrategyBot Arena. Bots receive
only engine.View; full engine state is recorded afterward for the human viewer.

    python visual_harness.py
    python visual_harness.py --bot bot.py --out visual
    python -m http.server 8765 --bind 127.0.0.1 --directory visual

Open http://127.0.0.1:8765/ in a browser. No third-party dependency is required.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import time

from baselines import engine_v8 as engine
import field


ROOT = Path(__file__).resolve().parent
SCENARIOS = [
    ("Unfamiliar strong opponents", ["submission", "pro_tuned", "spine", "ai_hawk"], 73191, 2),
    ("Raid and shield pressure", ["baiter", "submission", "cdraider", "hunter"], 84023, 4),
    ("Four independent submissions", ["submission"] * 4, 92017, 1),
    ("Different AI architectures", ["ai_homefort", "ai_route", "submission", "ai_elo"], 101063, 3),
    ("Fresh independent challengers", ["submission", "independent_farmer", "independent_raider", "pro_tuned"], 20261107, 3),
]


def sha(path):
    # Normalise line endings before hashing. git stores LF and may check a file
    # out as CRLF, so hashing raw bytes made this pass on the machine that
    # wrote the evidence and fail on every fresh clone.
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def opponent(name):
    if name in ("independent_farmer", "independent_raider"):
        # audit.py is a diagnostic module, so load this policy by exact path
        # rather than treating the same-named audit directory as a package.
        spec = importlib.util.spec_from_file_location(
            "independent_challengers", ROOT / "audit" / "independent_bot.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return (module.IndependentFarmer if name == "independent_farmer"
                else module.IndependentRaider)
    return field.opponent(name)


def view_signature(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen,
                   c.base_points) for row in view.board for c in row))


def submission(path, number, internal_errors):
    """Load each seat separately, as independent competition entries would be."""
    spec = importlib.util.spec_from_file_location("replay_submission_%d" % number, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Observe swallowed planner exceptions without bypassing the public act().
    # Preserve its fallback and time guards. This observer is not part of bot.py.
    if hasattr(module, "Agent") and hasattr(module.Agent, "decide"):
        original = module.Agent.decide

        def checked(self, view):
            try:
                return original(self, view)
            except Exception as exc:
                internal_errors.append(type(exc).__name__ + ": " + str(exc))
                raise

        module.Agent.decide = checked
    return module.act


def snapshot(g, completed_turn, transition=None):
    return dict(turn=completed_turn, owner=g.owner[:], upgraded=g.upg[:],
                positions=g.pos[:], frozen=g.frozen[:], cooldown=g.cd[:],
                progress=g.prog[:], score=g.score[:], income=g.income[:],
                token=g.token, transition=transition)


def capture(path, scenario, number):
    title, names, seed, token = scenario
    internal = [[] for _ in range(4)]
    bots = [submission(path, number * 4 + i, internal[i]) if name == "submission"
            else opponent(name)(seed * 4 + i) for i, name in enumerate(names)]
    g = engine.Game(base=engine.make_map(seed=seed), start_token=token)
    frames = [snapshot(g, 0)]
    failures = []
    timing = [[] for _ in range(4)]
    while not g.over():
        turn = g.turn
        views = g.views()
        requests, accepted, elapsed, legal = [], [], [], []
        for i, bot in enumerate(bots):
            view = views[i]
            before = view_signature(view)
            old_internal = len(internal[i])
            error = None
            t0 = time.perf_counter()
            try:
                action = bot(view)
            except Exception as exc:
                action = "STAY"
                error = ("exception", type(exc).__name__ + ": " + str(exc))
            ms = (time.perf_counter() - t0) * 1000.0
            timing[i].append(ms)
            legal.append(list(before[2]))
            if view_signature(view) != before:
                failures.append(dict(turn=turn, seat=i + 1, kind="input mutation", detail="state changed"))
            for msg in internal[i][old_internal:]:
                failures.append(dict(turn=turn, seat=i + 1, kind="internal fallback", detail=msg))
            # Match the documented server's STAY substitution. This local timing
            # is diagnostic; it is not proof of performance on grader hardware.
            if error:
                failures.append(dict(turn=turn, seat=i + 1, kind=error[0], detail=error[1]))
            if not isinstance(action, str) or action not in before[2]:
                failures.append(dict(turn=turn, seat=i + 1, kind="illegal action", detail=repr(action)))
                applied = "STAY"
            else:
                applied = action
            if ms > (2000 if turn == 1 else 200):
                failures.append(dict(turn=turn, seat=i + 1, kind="timeout", detail="%.3f ms" % ms))
                applied = "STAY"
            requests.append(action if isinstance(action, str) else repr(action))
            accepted.append(applied)
            elapsed.append(round(ms, 3))
        previous_owner, previous_upg = g.owner[:], g.upg[:]
        effective = g.step(accepted)
        events = []
        for p in range(64):
            if previous_owner[p] != g.owner[p]:
                events.append(dict(kind="raid" if previous_owner[p] else "claim", cell=p,
                                   seat=g.owner[p], previous=previous_owner[p]))
            elif previous_upg[p] != g.upg[p]:
                events.append(dict(kind="upgrade", cell=p, seat=g.owner[p]))
        frames.append(snapshot(g, turn, dict(requested=requests, accepted=accepted,
                    effective=effective, elapsed_ms=elapsed, legal=legal, events=events)))
    # This digest ignores machine-specific timing and binds the exact action/board
    # trace. Seed alone is not a promise of identical time-guarded regeneration.
    canonical = [{k: v for k, v in frame.items() if k != "transition"} |
                 {"actions": frame["transition"]["effective"] if frame["transition"] else []}
                 for frame in frames]
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    return dict(title=title, names=names, seed=seed, start_token=token,
                base=g.base, homes=g.home, rules=g.rules, frames=frames,
                scores=g.score, places=g.places(), failures=failures,
                max_ms=[round(max(x), 3) for x in timing], trace_sha256=digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot", type=Path, default=ROOT / "bot.py")
    parser.add_argument("--out", type=Path, default=ROOT / "visual")
    parser.add_argument("--scenario", type=int, choices=range(1, len(SCENARIOS) + 1),
                        help="one of the five scenarios")
    args = parser.parse_args()
    path = args.bot.resolve()
    args.out = args.out.resolve()
    # Opponent factories load their tuned snapshots from the project directory.
    # Resolve user paths first, then make this work from any launch directory.
    os.chdir(ROOT)
    scenarios = [(i, s) for i, s in enumerate(SCENARIOS) if args.scenario in (None, i + 1)]
    games = []
    for i, scenario in scenarios:
        game = capture(path, scenario, i)
        games.append(game)
        print("%s: scores=%s, failures=%d, worst=%.3f ms, trace=%s" %
              (game["title"], game["scores"], len(game["failures"]), max(game["max_ms"]),
               game["trace_sha256"][:12]), flush=True)
    data = dict(format_version=1, engine="Local reimplementation; not the official StrategyBot Arena",
                bot_file=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                bot_sha256=sha(path), engine_file="baselines/engine_v8.py", engine_sha256=sha(ROOT / "baselines/engine_v8.py"),
                python=platform.python_version(), games=games)
    data["independent_opponent_sha256"] = sha(ROOT / "audit" / "independent_bot.py")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "replays.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    template = (ROOT / "visual" / "viewer.html").read_text(encoding="utf-8")
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    (args.out / "index.html").write_text(template.replace("/* REPLAY_DATA */null", payload), encoding="utf-8")
    print("Viewer: " + str((args.out / "index.html").resolve()))
    if any(game["failures"] for game in games):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
