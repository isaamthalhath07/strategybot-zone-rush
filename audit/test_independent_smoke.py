"""Untuned smoke test; does not load the submission or measure against it."""
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "audit"))
import engine
from independent_bot import IndependentFarmer, IndependentRaider


def snapshot(view):
    return (view.bot_id, view.is_priority_token, tuple(view.legal_actions),
            tuple((c.occupant, c.owner, c.is_upgraded, c.is_home, c.is_frozen, c.base_points)
                  for row in view.board for c in row))


def main():
    calls = 0
    worst = 0
    for seed in range(8):
        base = ([1] * 64 if seed == 0 else [3] * 64 if seed == 1
                else engine.make_map(seed=70931 + seed))
        game = engine.Game(base=base, start_token=seed % 4 + 1)
        policies = [(IndependentFarmer if (i + seed) % 2 else IndependentRaider)(seed * 4 + i)
                    for i in range(4)]
        while not game.over():
            actions = []
            for policy, view in zip(policies, game.views()):
                before = snapshot(view)
                start = time.perf_counter()
                action = policy(view)
                elapsed_ms = (time.perf_counter() - start) * 1000
                worst = max(worst, elapsed_ms)
                assert elapsed_ms < (2000 if game.turn == 1 else 200), "late result"
                assert action in view.legal_actions, action
                assert snapshot(view) == before, "mutated public input"
                actions.append(action)
                calls += 1
            game.step(actions)
        assert all(game.owner[p] == seat for seat, p in engine.CORNERS.items())
    print("PASS: %d public-interface calls, eight full independent-only games, "
          "no exception/illegal result/input mutation; worst %.3f ms" % (calls, worst))


if __name__ == "__main__":
    main()
