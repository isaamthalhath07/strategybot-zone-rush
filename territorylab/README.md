# Territorial intent: responding to the space rivals leave open

This is a historical experiment against the accepted v8 policy, now preserved
exactly at `baselines/v8.py`. The active root export follows main's fusion policy.
The lab imports the frozen comparator explicitly. Historical results and source
registrations remain unchanged; source integration edits correctly invalidate old
final locks. Use commit `9df9497` to run the original report and locked-final
reproduction commands below. New trials require new source registrations.

This research tests the user's hypothesis: opponents skipping nearby claims
may be travelling to the centre; if several do so, an edge-oriented route may
profit from less competition. The new model predicts regional demand from
public history rather than only learning shield and raid decisions.

**Historical result: v8 was retained after this experiment.** The history model gained on one
locked spatial-opponent final test but did not replicate that gain against
four further economic planners. No spatial feature is shipped from this round.

| Test | Paired tasks | Difference in opponents outscored/game | 95% interval |
|---|---:|---:|---|
| Simple two-skippers → edges, discovery | 224 | -0.0759 | [-0.1411, -0.0107] |
| History model, development | 448 | +0.0123 | [-0.0372, +0.0618] |
| Fixed history model, unused spatial rules | 896 | +0.0552 | [+0.0141, +0.0963] |
| Same model, four further economic rules | 896 | -0.0022 | [-0.0622, +0.0578] |
| History versus static regional prior, explanatory ablation | 448 | +0.0033 | [-0.0433, +0.0500] |

The first final alone would have given an overly optimistic impression of
generalisation. This is evidence about these implementations and distributions,
not a refutation of responding to rivals' territorial intent. No actual
competition Elo is estimated. Full results and subgroups are in `RESULTS.md`.

## Start with the rules

All bots start on corners. Either legal first movement enters an outer-edge
cell. That direction alone cannot distinguish a centre rush from an edge tour.
Arriving does not claim a cell: one STAY on a neutral cell is required. The
first useful observation is therefore whether a player continues travelling
instead of claiming its first neighbour. That indicates willingness to travel,
but an edge traveller can make exactly the same choice.

Later evidence includes turning into the interior, repeated skipped claims,
actual captures, and completed upgrades. Frozen STAYs are forced, so they are
not evidence of intent. A stationary observation can also be a failed move or
shield; this model abstains unless actual work completes.
Even completed work is not proof of an intended STAY: a blocked move can also
complete a claim. The prototype does not fully censor that ambiguity, another
reason not to treat its beliefs as exact intent reconstruction.

## The strategic hypothesis

If two players spend several turns travelling inward and contest the same
valuable cells, they can leave profitable neutral edge clusters available.
Taking and upgrading those clusters can generate income while the rivals
travel or block each other. The exact cells matter: two inward players can
also divide the centre without fighting, and the remaining rival may already
be competing for our edge.

Cell count is not the objective. A neutral capture completed on turn t is worth
`base_points * (81 - t)` if held to turn 80. A later 3-point capture can still
outpay an earlier 1-point edge capture. Travel, upgrade work, subsequent loss,
and the other opportunities along a whole route must also be priced.

There are 28 outer-edge cells, of which four are permanent homes. The other
three homes cannot be captured. Capturing all 24 non-home edge cells would
already require at least 24 capture STAYs plus substantial travel. The useful
goal is profitable, reachable, neglected territory, not a complete perimeter.

## Implemented hypotheses

| Variant | What it changes |
|---|---|
| baseline | Accepted v8 bot, without any new spatial modification |
| naive_edges | If two rivals have skipped a neutral claim, boost outer-edge claims and discount inner claims through turn 24 |
| position | Prefer lower-demand neutral cells using current rival distances and cell values, without history |
| territory | Infer inward/perimeter/local intentions, then use their mixture to estimate regional demand |
| cautious | Same model with a smaller effect on claim value |
| prior_only | Explanatory control: same region geometry and strength, but no learned beliefs |

`model.py` uses an approximate, tempered likelihood over possible moves/work.
It ignores the first move, smooths sparse evidence toward a prior, and forgets
stale intentions. Its probabilities are heuristic beliefs, not demonstrated
calibrated probabilities of an actual team's strategy.

`policy.py` turns expected territorial demand into a bounded factor on neutral
claim value. Board values, route costs and the original planner still matter.
It does not force the bot onto edges. The factor is fixed for each observed
turn across all hypothetical walks, avoiding the earlier pacing defect.
Spatial adaptation ends after turn 24. That limit is a modelling assumption.

This is a proxy for competition, not a full forecast of who will own each cell
at our exact arrival time. Region mass is not an independently validated
capture probability. The next stronger design would forecast competing claims
and future ownership changes explicitly inside the route search.

The history model also differs from the position-only control in its static
regional prior. That is why a separate `prior_only` ablation was needed:
history's added value cannot be inferred just from beating the position model.

## A stronger way to use this insight

1. Maintain small, uncertain hypotheses about destinations and work schedules,
   including centre sectors, edge sectors, local farming and changes of goal.
   Do not classify a whole player from one skipped claim.
2. Predict which cells each rival is likely to claim **before our planned
   arrival**, using actual board values, travel, needed STAYs and body blocking.
   Validate against future public captures, not nominal style labels.
3. Score complete routes under those forecasts. A valuable contested cell
   might need taking now, while safe cells can wait; a blanket crowding penalty
   misses that distinction. Already-owned future cells require a raid, not a
   neutral claim. Forecast ownership survival separately from initial capture.
4. Reassess after new evidence and permit retreat from an opening read. If
   everybody responds to a centre rush by taking edges, the centre can become
   attractive again. Keep hysteresis so replanning does not cause pacing.
5. Require gains on unused spatial **and** non-spatial opponents. Retain a
   conservative fallback while forecasts are poorly supported. Compare history
   learning against an otherwise identical prior-only control.

This is the next hypothesis to implement and validate, not a claim that these
steps already solve the simultaneous multiplayer game optimally.

## Test plan and information boundaries

- Nine newly authored spatial scheduling rules are split into three discovery,
  three development and three unused final rules. Every game gets new random
  coefficients. No earlier named competitor or bot snapshot is an opponent.
- Openings include express travel, claims along the way, upgrades before
  launch, perimeter travel that looks like a rush, value-dependent objectives,
  and changes of goal. Final families include decoys and later goal switches.
- Nominal centre-role counts 0, 1, 2 and 3 are balanced. They describe the
  generator's objective, not guaranteed actual movement. Only the observer sees
  those role labels; the played policy receives standard public state only.
- Every map covers all 16 seat/starting-token combinations with new map seeds.
  Both policies in a pair receive identical conditions. Wall-clock truncation
  is disabled for policy comparisons and must be verified separately for release.
- `confirm.py` adds four further new economic planners: short income beam search,
  renewal/cluster work, a frontier market, and reactive spatial allocation.
  They have no fixed centre/rim roles and were never fitted against our bot.
- `attribution.py` separates learned history from a static spatial prior on new
  seeds. It is an explanatory ablation, not another opportunity to select a
  policy using a consumed final test.
- Successful runs bind source hashes and check every action for legality,
  unchanged inputs, and internally swallowed planner exceptions.

Across the five recorded comparisons there were **7,840 games and 2,508,800
checked action calls**, with no detected illegal action, input mutation or
swallowed focal planner exception. The 112 partial trajectory observations
are additional, descriptive data. All nine new unit tests passed. No release
timing or export claim is made for the experimental model; the previously verified v8 artifact remains at `baselines/v8.py`.

Opponents share public observation plumbing and some economic work estimates.
These are different scheduling rules, not thirteen independently authored
programs or a representative sample of actual competition entries. The high
baseline scores on some of these fields also limit discrimination.

Unit tests cover first-move ambiguity, skipped-claim ambiguity, inward turns,
forced stays, reflection symmetry, split isolation, an exact disabled-feature
control, and removal of history in the attribution control. Randomised paired
tournaments supply integration and strength tests. They do not prove universal
non-overfitting or the absence of every possible bug.

## Files and reproduction

`opponents.py` creates the spatial families. `evaluate.py` runs paired games.
`final_registration.json` locks the candidate, code, seed and sample size before
final play. `confirm.py` writes a second registration before its games.
`inspect_openings.py` describes public baseline trajectories through turn 24;
it is not a strength test. `report.py` publishes all comparisons and subgroups.
`results/` preserves the raw data, including unfavourable outcomes.

```powershell
python test_territorylab.py
python -m territorylab.report
# New output paths preserve the original recorded evidence:
python -m territorylab.evaluate --split discovery --games 224 --seed 281741 --workers 8 --out territorylab/results/reproduced_discovery.json
python -m territorylab.evaluate --split final --games 896 --seed 683971 --workers 8 --variants baseline territory --lock territorylab/final_registration.json --out territorylab/results/reproduced_final.json
```

Final outcomes are consumed evaluation data once read. Future policy revisions
need further unused algorithms, rather than tuning against these results and
calling them held out again. Source changes correctly invalidate old locks;
use the experiment's Git commit to reproduce its original code.
