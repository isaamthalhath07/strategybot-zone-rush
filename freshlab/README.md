# Fresh opponents and within-game adaptation

The active submission now uses `v8_fresh_params.json`, the recalibration that
passed both unseen-algorithm confirmations. `baseline.py` is an exact copy of
`mybot.py` when this experiment began; it fixes both implementation and weights
during comparisons. Historical named opponents and previous submission versions
are **never training opponents** in this directory. See `FEATURES.md` for the
accepted change and the learned features that remain experimental.

## What an opponent model can learn

An 80-turn game offers too little evidence to identify an arbitrary algorithm.
Specific conditional probabilities are more defensible:

1. Will this defender shield when I can finish a take on this turn?
2. Does this raider stay or leave when the defender can shield?
3. Does this bot normally finish its own upgrades before moving?

These predictions change raid risk, defensive timing, and whether an occupied
target is likely to open up. Broad personality labels such as "aggressive" are
not the policy inputs. Bayesian smoothing pools sparse context evidence with a
per-player estimate and a prior. Uncertain reads remain near the prior. Future
plans fade back toward the prior rather than assuming behaviour stays fixed.

Only public state transitions reach `Styles`. A frozen STAY is censored, not
counted as voluntary commitment. Cooldown turns are not counted as a decision
not to shield. An upgraded raid still needing three stays is not treated as an
imminent threat. Multiple raiders create one defensive decision. If more than
one set of shielding players explains a transition, only labels on which all
explanations agree are recorded. Possible blocked exits are censored too.

This is still approximate inference: the underlying history tracker can make
cooldown attribution mistakes, and correlations in possible histories are not
represented by a full belief distribution. Prediction quality and tournament
strength must be reported separately.

## Opponents keep changing

`population.py` draws new parameters for every new game. The six discovery
families are rate scheduling, cluster expansion, local sweeps, economic phase
switching, cautious raiding, and bounty hunting. The development algorithms are
two-job lookahead, a changing regime, and territorial pressure. Final evaluation
uses marginal auctions, score denial, and another behaviour-switching design.

The split is by decision algorithm **and** seed, not a shuffled list of known
enemies. Opponents share parsing and rule bookkeeping, so they are not twelve
independent implementations or evidence about twelve actual teams. No generated
opponent is fitted to our submission. No old zoo bot or snapshot enters training.

New map seeds and opponent parameters are used in each discovery round. The
final test also contains rich-corner and inverted maps absent from discovery.
Maps remain four-fold mirrored and within values 1–3.

The first final result received a separate balanced confirmation with four more
unused scheduling rules: persistent reservations, continuous discounting, a
territory/upgrade portfolio, and two-job income sums. `unseen.py` contains them
and `confirm.py` balances every map against all 16 seat/token combinations. The
candidate was fixed before this additional test. Both results are now consumed
evaluation data, never a new training set.

## Test plan and promotion rule

| Test | Purpose |
|---|---|
| Public-transition unit tests | Censor forced actions, count one defensive decision, avoid treating homes as capturable |
| Referee-labelled random sequences | Check inferred labels against hidden actions used solely by the observer |
| Zero-feature paired control | Observation alone must reproduce baseline actions and scores exactly |
| Contract checks on every action | Legal output, unchanged input, and exposed internal planner exceptions |
| Split tests | No architecture overlap; new rounds use new map/style seeds |
| Source hashes before/after a run | Reject measurements if any policy or opponent implementation changes mid-run |
| Discovery comparisons | Explore a short predeclared list; treat confidence intervals as descriptive |
| Development algorithms | Select one candidate using new designs; do not promote on discovery scores |
| Locked final algorithms | Evaluate only baseline and the registered candidate, once, with unchanged hashes |
| Shipping timing | Separate actual deadlines from policy comparisons whose deadlines are disabled |

The frozen submission is promoted only with independent evidence of a gain,
inspection of all map subgroups, and no contract failure. Subgroup intervals do
not establish noninferiority: rich-corner results remain uncertain. A confidence
interval including zero means "inconclusive", never "equivalent". Rejecting every new
feature is a valid result. A single experiment cannot ensure universal
non-overfitting or optimality against arbitrary future competitors.

Reproduction:

```powershell
python test_freshlab.py
python -m freshlab.evaluate --split train --games 192 --seed 183719 --workers 8 --variants baseline observe_only context_commit context_defence guarded context_both future_window dwell --out freshlab/results/train_discovery.json
python -m freshlab.calibration --games 80 --out freshlab/results/calibration.json
python -m freshlab.validate_release
```

`evaluate.py` requires a candidate registration with exact source hashes before
it permits the final split. Keep final outcomes out of later selection. Should
an experiment need revising after final evaluation, retire that test as
development evidence and reserve another untouched architecture family.

## Further features worth testing, in order

The first experiment tests conditional shielding, conditional commitment,
confidence bounds, occupied-cell dwell, and corrected timing of future raids.
Other plausible additions are:

- explicit finite-horizon raid/retreat choices against a ready shield;
- change detection when a rival switches from farming to raiding;
- a distribution over rival next moves, used for contested cells and pruning;
- joint shield value when several intruders threaten different cells;
- predicted ownership survival, rather than assuming every capture lasts to turn 80;
- final-turn exact payoff comparisons for all legal actions;
- short schedules with claim/upgrade/raid ownership transitions represented directly;
- latent policy mixtures updated from observed choices, with a safe fallback;
- map-dependent opening choices selected from board values, not a fixed centre bias;
- compute allocation by decision ambiguity, spending more time only on close choices.

Each adds a forecast or a tradeoff and can lower Elo. New code is an experiment
until it survives the same fresh-opponent process. No finite list exhausts the
space of history-dependent policies.
