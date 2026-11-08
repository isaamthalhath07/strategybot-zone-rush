# Offline observation-branching tree reference

This prototype builds a public-history decision tree. Different future public
observations lead to different continuation nodes, while indistinguishable
histories share the same statistics. It is separate from the existing open-loop
GPU diagnostic and does not change the deployed bot or current campaign.

The implementation uses correlated root-state sampling, node-only UCT, a
public-only rollout policy and optional dynamic top-K pruning. Read
[the design and limitations](DESIGN.md) before interpreting a recommendation.
It is a bounded CPU reference, not a completed per-game BMCTS audit or a proven
stronger policy.

## Reproduce a diagnostic

Only Python's standard library is required. From the repository root:

```powershell
python -m unittest discover -s tree_coach -p "test_*.py" -v
python -m tree_coach --input tree_coach/evidence/opening_input.json --output .cache/tree_coach/new-opening.json
```

The output path must be new. The command refuses to overwrite completed
evidence. The existing GPU worker/queue deliberately does not accept this
different diagnostic schema; there is no distributed tree-search adapter yet.

Each input contains exactly `schema`, `kind`, `job_id`, `initial_observation`,
`transitions` and `search`. Kind is `public_history_tree_coach`. Observations
contain exactly the documented four fields; board cells are six-element public
arrays. Each transition contains only `own_action` and the next focal
`observation`. A complete real opening prefix is required; private snapshots,
joint action histories, opponent seeds and controller identities are rejected.

| Search setting | Default | Bound |
|---|---:|---:|
| `seed` | 0 | 0..2,147,483,646 |
| `horizon` | 6 | 1..12, clipped to remaining turns |
| `simulations` | 256 | 1..2,048; at least two per legal root action |
| `beam_width` | 6 | 1..6; six disables action pruning |
| `support_cap` | 512 | 1..1,024 |
| `income_tail` | 12 | 0..80 |
| `max_nodes` | 4,096 | 1..8,192 |

Search therefore simulates at most 24,576 future turns per call. Prefix
reconstruction has its own finite cost and may dominate a long ambiguous
history. These are resource bounds, not a response-time guarantee.

## Independent map-boundary review

The current source additionally rejects opening maps without the official
horizontal and vertical mirror symmetry. All **15 tests** pass: the original
twelve plus three independent checks for invalid maps, unknown initial priority
and exact terminal return backups. The latter checks 64 nontrivial terminal
simulations in both referees after a reachable 79-turn prefix.

The current source reproduced all three earlier numerical reports and trace
digests exactly. Current source/result pins are in
`evidence/mirror_guard_v3/review.json`. The exact source and evidence before this
boundary fix are preserved in `evidence/prototype_v2_before_map_guard.zip`.
Reproducing earlier cases does not add new unique campaign evidence.

## Evidence and interpretation

Twelve focused tests passed, including reachable private-cooldown ambiguity,
input immutability, strict nested public fields, root action coverage, dynamic
pruning re-entry, sparse-arm root choice, terminal scoring, and **128 hypothetical
transitions compared in both referees** after public policies chose their moves.
The observer-side referee check is confined to tests.

The three stored inputs/results contain **192 simulations and 672 synthetic
turns**. Their source, input, result and trace hashes are in
[the validation receipt](evidence/validation.json). The trace digest binds each
simulated joint action, resulting focal public observation and terminal/cutoff
return. Replaying the same source/input reproduces the numerical report and
trace; wall time may vary.

| Public case | Simulations | Future turns | Tree nodes | Edges with multiple observed outcomes |
|---|---:|---:|---:|---:|
| Opening | 128 | 512 | 129 | 11 |
| Reachable cooldown ambiguity | 32 | 128 | 33 | 4 |
| Actual final-turn prefix | 32 | 32 | 1 | 4 |

In the opening case, 220 decisions used tree-node statistics across 128
simulations, demonstrating revisited continuations as well as new rollouts.
Observed branching also includes terminal/cutoff outcomes; those do not create
future decision nodes. The three recorded runs took about 0.11–0.27 seconds
under concurrent load, including prefix reconstruction but excluding interpreter
startup. This is not a deployment benchmark; the opening already exceeded the
normal 200 ms budget.

The recommendation is the highest empirical root mean, even when one action has
far fewer samples. Two lucky outcomes can outrank a heavily sampled alternative.
Dynamic beam pruning re-ranks all actions on each visit and may re-admit a
previously excluded action. Neither behavior supplies a confidence bound.
At a real terminal state the objective is exact official pairwise points; at a
nonterminal cutoff projected income is a heuristic. Rival models remain simple,
support weights are uncalibrated and capped support can lose the real state.

This evidence grants **zero primary games**, **zero completed per-game BMCTS
audits**, **zero promotion authority** and **no playing-strength or optimality
claim**. The earlier development snapshot, its inputs and source files are
preserved in `evidence/prototype_v1.zip`; it is not additional campaign evidence.
