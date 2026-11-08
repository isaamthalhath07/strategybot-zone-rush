"""Exercise the shipped entry point with only documented public input fields."""
import importlib.util
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine


def snapshot(view):
    return (
        view.bot_id, view.is_priority_token, tuple(view.legal_actions),
        tuple(tuple((c.occupant, c.owner, c.is_upgraded, c.is_home,
                     c.is_frozen, c.base_points) for c in row)
              for row in view.board),
    )


def main():
    spec = importlib.util.spec_from_file_location("submission_contract", ROOT / "bot.py")
    submission = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(submission)
    maps = [engine.make_map(canonical=True), [1] * 64, [3] * 64,
            engine.make_map(seed=20261107)]
    calls = 0
    worst_ms = 0.0
    for mi, base in enumerate(maps):
        game = engine.Game(base=base, start_token=mi + 1)
        while not game.over():
            views = game.views()
            actions = []
            for view in views:
                before = snapshot(view)
                started = time.perf_counter()
                action = submission.act(view)
                elapsed_ms = (time.perf_counter() - started) * 1000
                worst_ms = max(worst_ms, elapsed_ms)
                assert snapshot(view) == before, ("input mutated", mi, game.turn, view.bot_id)
                assert action in view.legal_actions, ("illegal output", action)
                limit_ms = 2000 if game.turn == 1 else 200
                assert elapsed_ms < limit_ms, ("late output", elapsed_ms, mi, game.turn)
                calls += 1
                actions.append(action)
            game.step(actions)
    print("PASS: %d calls across four full games, four seats sharing one module; "
          "no input mutation or illegal/late result; worst %.3f ms" % (calls, worst_ms))


if __name__ == "__main__":
    main()
