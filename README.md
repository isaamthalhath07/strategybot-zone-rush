# StrategyBot: evolved Zone Rush bot

The recommended single-file submission is [`bot.py`](bot.py). It exposes `act(state)` and uses only the Python standard library.

The research completed 22 evolutionary rounds and 33,312 training games, followed by separate selection and matched comparison panels. On the latest panel, with 1,024 identical fixtures per version:

| Program | Pairwise credit | Outright first |
| --- | ---: | ---: |
| Recommended evolved bot | 64.13% | 37.30% |
| New evolutionary finalist | 64.88% | 40.04% |
| Original external submission | 53.32% | 23.24% |
| Updated external development build | 53.19% | 23.14% |

Pairwise credit is the fraction of rivals outscored, with half credit for ties. The newer finalist did not clear the predeclared replacement rule: its improvement interval included zero. The first evolved winner therefore remains the recommendation.

These are local simulations under the published rules and organiser clarifications. They do not guarantee tournament performance. Compatibility with the organisers' server remains unverified.

## Files

- [`outputs/Evolution_Comparison.md`](outputs/Evolution_Comparison.md): full methodology, opponent fields, uncertainty, model comparisons and reproduced failures.
- [`outputs/Evolution_TestKit.zip`](outputs/Evolution_TestKit.zip): portable trainers, checkpoints, referee, opponents, source snapshots, raw results, traces and tests. Extract it into a separate directory and follow its README.
- [`outputs/bot_transfer_candidate.py`](outputs/bot_transfer_candidate.py): preserved second-run finalist, with an inconclusive gain.
- [`outputs/bot_user_corrected.py`](outputs/bot_user_corrected.py): isolated repairs to the original v6 comparison bot. Its strategic weights are preserved.
- [`outputs/bot_before_evolution.py`](outputs/bot_before_evolution.py) and [`outputs/StrategyBot_Research.md`](outputs/StrategyBot_Research.md): historical baseline and earlier rule analysis.
- [`submission_manifest.json`](submission_manifest.json): selected artifact hash, source and audit summary.

The root `bot.py` and `outputs/bot.py` are identical. Their SHA-256 is `fe71fcc6a82122aa09d311db0bba92ab90639b2e679bb1ef3abbcc0d87dd0486`.

The test package was extracted and verified, including 23 referee tests, 4,533 final-turn joint-action profiles, memory-recovery tests and two exact portable audit replays. Historical checkpoints are preserved as evidence; use a new directory for new training runs.
