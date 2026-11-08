"""Prediction-only validation on baseline trajectories, without policy changes.

Observed hidden actions are labels for this test harness only. Neither the
observer model nor the played policy receives them. Reports prediction quality
separately from whether acting on a prediction wins more games.
"""
import argparse
import json
from pathlib import Path

import engine
from freshlab import baseline, candidate, evaluate, model, population


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=80)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    params = dict(baseline.PARAMS)
    params.update(json.loads(Path("v7_params.json").read_text()))
    params.update(throttle=0, budget_ms=10000.0, first_turn_ms=0)
    scores = {k: {s: [0., 0] for s in ("constant", "per_player", "context")}
              for k in ("shield", "commit")}
    labelled, bad, ambiguous, inconsistent = 0, 0, 0, 0
    for task in evaluate.tasks("train", args.games, 877331):
        seat = task["seat"]
        bot = candidate.AdaptiveAgent(task["map_seed"], params, {})
        others = iter(population.ProceduralOpponent(s) for s in task["specs"])
        bots = [bot if j == seat else next(others) for j in range(4)]
        game = engine.Game(base=task["base"], start_token=task["token"])
        trackers = {k: model.Evidence() for k in scores}
        last = None
        old_count = 0
        while not game.over():
            states = game.views()
            acts = [b(v) for b, v in zip(bots, states)]
            events = bot.tr.styles.observations
            for kind, j, context, outcome in events[old_count:]:
                expected = last[j] == ("SHIELD" if kind == "shield" else "STAY")
                labelled += 1
                bad += outcome != int(expected)
                prior = params["q_prior"] if kind == "shield" else params["commit_prior"]
                evidence = trackers[kind]
                y, n = evidence.counts.get((j, None), (0., 0))
                pooled = (prior * 4 + y) / (4 + n)
                estimates = dict(constant=prior, per_player=pooled,
                                 context=evidence.predict(j, context, prior))
                for name, p in estimates.items():
                    scores[kind][name][0] += (p - outcome) ** 2
                    scores[kind][name][1] += 1
                evidence.add(j, context, outcome, estimates["context"])
            old_count = len(events)
            last = game.step(acts)
        ambiguous += bot.tr.styles.ambiguous
        inconsistent += bot.tr.styles.inconsistent
    payload = dict(games=args.games, labelled=labelled, incorrect_labels=bad,
                   ambiguous_transitions=ambiguous, unexplained_transitions=inconsistent,
                   brier={k: {s: a / max(1, n) for s, (a, n) in d.items()}
                          for k, d in scores.items()},
                   counts={k: d["context"][1] for k, d in scores.items()},
                   caveat="Prequential public-transition prediction on fixed baseline trajectories; this measures prediction, not playing strength or actual competitors.")
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if bad:
        raise AssertionError("public inference produced incorrect labels")


if __name__ == "__main__":
    main()
