# Does the search advice help?

This is an offline usefulness experiment for the observation-tree coach. It
preregisters eight incumbent positions from an accepted training stage: turns
34 and 60, all four rival fields and eight distinct maps. Selection uses fixed
fixture hashes, without looking at outcomes.

The coach receives only the opening view, own accepted past actions and later
own public views. A separate observer reconstructs the real controller histories
and evaluates every legal current action through the end of the match. Each
rival responds to the changed boards using its actual policy and private RNG.
The observer never feeds those controllers, seeds or future actions to the coach.
Recorded future action lists are used only to check the unchanged baseline.

After the one-step intervention, the original focal planner continues. Its
accepted-action memory is synchronized with the intervention; its other planner
intent updates remain intact. This is the declared diagnostic hybrid, not the
unchanged original policy. Every callback is legal, immutable, on time and
checked against supported public-memory oracles; all turns match two referees.
The best evaluated root is a hindsight opportunity under those continuations,
not a globally optimal partially observed policy.

The first run changed three recommendations. All three had the same final
pairwise outcome as the baseline: **zero improvements, zero losses, mean delta
zero**. In another position the evaluator found a two-point opportunity, while
the coach retained the weaker baseline action. Eight cases are too few to settle
strength, but this run does not justify assigning hours of search as a proven
improvement method. Better horizon/model choices need fresh usefulness evidence.

These are counterfactual replays, not new seeded primary matches. They grant
zero primary games, zero completed per-game BMCTS audits and no promotion.
The coach's offline search time is not a deployment deadline claim.

```powershell
python -m coaching_trials.trial --stage .cache/primary/campaign_v1_20261109/train_000 --output .cache/coaching_trials/new-trial
```

The output directory must be new. Complete public inputs, source hashes,
recommendations, per-root outcomes and the preregistration are preserved. The
command checks the source stage's complete independent admission before use.
