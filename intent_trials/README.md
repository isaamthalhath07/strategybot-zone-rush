# Does persistent-intent search change useful decisions?

This is a separate offline causal usefulness experiment for the frozen
`intent_search.mcts` teacher. It adds no deployed policy, primary game,
completed per-game BMCTS audit or promotion. Its inputs are already consumed
TRAIN matches, so the result cannot establish fresh-map or universal strength.

The source is exactly the admitted `campaign_v1_20261109/train_000` e8 incumbent
records. Preparation verifies the published accepted-100k snapshot and stage0's
exact raw registration, games, actor-audit log and published receipts. This
reuses the original full actor admission; it does not rerun all20,000 actors.
Catalog metadata is checked for TRAIN assignment and map exclusions. Reserved
development/final game or outcome files are never opened.

Preparation selects sixteen distinct map rotation orbits: decision turns30,
50,65 and75 crossed with economic, independent, erratic and pressure fields.
Only publicly unfrozen focal positions with at least three legal actions are
eligible. At each root, each player's projected final score is its public
reconstructed score plus `(81-turn)*current_public_income`. The selector takes
the smallest absolute focal-versus-rival projected margin, breaks ties by the
fixture SHA, and greedily excludes already used map orbits in turn/field order.
It never consults the recorded current/future action, final score, teacher or
counterfactual outcome. Previous joint actions are used only to replay physics
before the root. Public ownership changes determine capture bonuses and public
postturn holdings determine income; that independent accounting is checked
against the observer after every replayed prior turn.

All eight old coaching maps and all sixteen forecast pilot maps are excluded
by rotation orbit using exact pinned published registration evidence. No
exclusion may be relaxed after preparation. There is no fallback selection if
coverage fails. The exact source hashes, exclusions, sixteen public contexts,
public-prefix fingerprints, search settings, metric and bootstrap recipe are
sealed in `registration.json`.

The interface is deliberately split:

```powershell
python -m intent_trials.experiment prepare --stage .cache/primary/campaign_v1_20261109/train_000 --output intent_trials/evidence/causal_001
# Review and publish/commit the complete sealed registration and source pins.
python -m intent_trials.experiment execute --directory intent_trials/evidence/causal_001
```

Do not execute before that publication gate. Preparation makes no controller
calls or model recommendations and computes no branch outcome. The publication
gate is an explicit human workflow requirement, not an automatic Git check.
At execution the exact protocol is reconstructed from pinned evidence and
public physics, so rehashing an edited metric, setting, case or source pin does
not authorize drift.

Each teacher gets only the opening public observation, accepted own past
actions and following focal public observations. It receives no actual rival
seed, controller/type/state, current rival intention or future tape. The fixed
search uses96 simulations, horizon6, beam6,512 nodes and public-order diagnostic
seeds202611092300 through202611092315. All inference/joint-work caps are fixed;
any capacity failure aborts the whole experiment without pruning or omission.

For each case the observer independently rebuilds real controllers, their RNG
and past memories for the baseline and every legal one-step intervention. All
four actors get frozen four-field snapshots of the same preturn state, with
the original legal-action ordering retained for exact actor reproduction. All
four original actions are computed before the focal root action is replaced.
Its accepted-action memory `last` is synchronized; planner intent/target/bait
updates remain. The original focal policy then continues. This is the declared
hybrid intervention. Rival controllers respond to the changed boards; recorded
future actions are never substituted after a deviation.

Every branch measures all320 actual callbacks and80 turns in two referees.
Checks cover legality, first/regular deadlines, immutable public inputs, silent
fallback counters and supported public memory oracles. Both the unchanged
baseline and explicit baseline-action branch must reproduce the complete
original transcript and scores, and match one another. An exception preserves
completed branch files and the failed branch's partial trace/coverage in an
error record. Existing execution markers prevent automatic reruns of partial
or completed experiments; no unfavorable case may be replaced or tuned away.

The main metric is selected teacher minus baseline official pairwise points,
on the0..3 scale. All sixteen case outcomes and every legal alternative are
reported. Hindsight-best-one-step is the best tested intervention against this
realized responding rival instance, not a globally optimal policy. Teacher
delta and hindsight opportunity share20,000 within-field four-map bootstrap
draws with seed202611092330 and percentile indices499/19499. These intervals
describe the selected consumed TRAIN sample only. Offline teacher latency is
not an online200ms runtime qualification.
