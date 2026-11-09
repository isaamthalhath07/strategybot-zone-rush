# Independent trial review

Review scope: the new `intent_trials` causal-position protocol, its public
selection features, evidence admission, sealed plan, completeness checks and
descriptive statistics. Existing policy, primary campaign, predictor, search and
older coaching sources are frozen. No real trial preparation, teacher search,
counterfactual outcome or new match is executed by this review.

The full public prefix determines each player's score. Start at zero; an
ownership change between two different nonzero owners reveals the capture
bonus, `8 * previous_base * previous_level`, for the new owner. Add each turn's
income from the resulting public ownership, base and upgrade fields. Opening
income is not opening score. Before turn `t`, `81 - t` scoring turns remain.
Consequently `public_score + (81 - t) * public_income` needs no referee score,
cooldown, progress, actual controller or future action. Its nearest absolute
focal-versus-rival difference is a static-income selection heuristic. Future
captures, freezing and rank reversals can invalidate that projection.

The estimand is the final pairwise score of the fixed teacher's one accepted
root action followed by the declared original focal continuation, minus that
same position's regenerated unchanged baseline. It is conditional on the fixed
map, controllers, private RNG seeds, public prefix and accepted-action memory
synchronization. Every legal root action may be evaluated for hindsight
diagnostics; choosing the best resulting action is an evaluator oracle, not an
available public policy or a globally optimal strategy.

The sixteen positions are deliberately selected close-margin TRAIN positions,
one per fixed turn and rival-field cell, on distinct maps and rotation orbits.
They are not an independent random sample of future games. A stratified paired
bootstrap resamples four whole map/position records within each of the four
fields, with the same sampled indices for every diagnostic in a replicate.
Its interval describes this small selected-position sample, conditional on the
one frozen teacher seed per case. It does not cover model misspecification,
teacher seed variation, policy adaptation, selection uncertainty or fresh-map
playing strength. Four maps per field is a small descriptive sample.

No result here grants primary-match credit, completed per-game BMCTS audit
credit, deployment qualification or promotion. Offline teacher duration does
not establish the 200 ms actor deadline. Forecast-loss improvement from the
separate predictor pilot is not a win-rate result.

Source review found no remaining blocking defect in these boundaries. The
review requested two changes now present: reject impossible/non-half-point
official pairwise diagnostics, and use an atomic exclusive execution claim so
concurrent callers cannot both pass an existence check and run the same sealed
experiment. An existing or failed claim is preserved. Failure evidence retains
the active case/branch and accumulated partial branch trace and coverage; no
partial experiment receives aggregate statistics or game credit. Ordinary
exceptions, `KeyboardInterrupt` and `SystemExit` preserve sealed failure
evidence and re-raise the same interruption; the execution claim remains.

The runtime source closure, original accepted snapshot, stage registration/raw
game and actor-audit bytes, exact published receipt copies, prior experiment
exclusions, catalog metadata and current source guards are bound before use.
The complete semantic plan is reconstructed from admitted sources and compared
canonically on execution. Rehashing a changed plan or sidecar cannot change its
cases, claims, settings or schedule. Source pins are checked before admission
work and before final results publication. These are trusted-source inspection
and reproducibility checks, not a hostile-code security proof. The instruction
to publish and commit the registration before execution is a manual workflow
gate: the executable does not inspect Git commits or establish publication.

Independent verification: `python -m unittest intent_trials.test_protocol -v`
passed **15 tests in 1.334 seconds**. Tests cover opening score versus income,
all-seat public accounting on four synthetic 80-turn legal trajectories, an
upgraded rival capture, true remaining clock/public eligibility, fixed
margin/fixture ordering and orbit exclusions, fail-closed insufficient maps,
poisoned final scores and current/future source actions, exact semantic plan
drift despite updated sidecars, raw log/receipt/source mutation, snapshot stage
identity, whole-case completeness and official metric consistency, independent
reconstruction of all 20,000 shared within-field bootstrap draws and quantiles,
existing-output preservation, a synthetic concurrent execution loser and
sealed active/partial error evidence on both kinds of process interruption.

Accepted-data admission is replaced with synthetic metadata in protocol tests;
raw admission tests use deliberately synthetic pinned bytes and receipts.
Neither is a substitute for admitting the real source stage at preparation.
No real campaign transcript/outcome, teacher recommendation, actual controller
callback, real trial preparation or full trial execution was consumed by these
tests. Synthetic physics transitions are test witnesses, not matches.
The separate continuation review covers responding-controller behavior and
measured callback/referee completeness.

Reviewed runtime `intent_trials/experiment.py` SHA256:
`93862a0c5ef24c08a6d8c95a7a111b8598c55a399521d45cf27f7f790cff5125`.
Independent test `intent_trials/test_protocol.py` SHA256:
`e86a682652ab8514daca033b503edab59ec22c2a7a5a87652329d6879c3a1acf`.
This is approval of the protocol and synthetic checks for a frozen,
descriptive experiment. It is not evidence that the experiment completed or
that any recommendation improved a game.
