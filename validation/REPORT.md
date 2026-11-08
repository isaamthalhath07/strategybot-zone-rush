> Historical presence-rule validation (`catch_requires_stay=False`). These results are preserved for their recorded local model and are not current STAY-only strength evidence. The new release uses [the explicit clarification](official/rule_contract.json) and [separate validation](official/REPORT.md).

# Consolidation validation

## Selected artifact

The release is the guarded presence-based Transfer policy, SHA-256
`fc00af81fdf7e457b1256a838f363cd536cce9cb2eaa4e68d096622cd74b84cf`.
Root `bot.py` is byte-for-byte the frozen candidate used in the final comparison.
It imports only `collections`, exposes one `act(state)` and requires no other
file, learned weights, repository module, network connection or private input.

Ten remote branch tips, the open fork PR #10 and the existing local forward
export were inventoried. There were 282 distinct Python blobs; every inventoried
blob parsed. Shared branch exports were deduplicated by exact bytes. The review
combined static inventory with targeted source, rule-boundary, implementation
and evidence review; it does not claim line-by-line manual review of generated
result dumps. [Full branch and strategy findings](review/BRANCH_REVIEW.md).

## Changes that survived review

- Preserve the strong economic macro-action/route pricing and completion-turn
  income. Preserve conditional raid continuation and escape from repeatedly
  defended upgraded land. These remain heuristics rather than a solved equilibrium.
- Infer Shield causes from post-movement positions and pre-capture ownership.
  Include arrivals, moves within one owner's land and mutually shielding rivals.
  Keep ambiguous cooldown possibilities instead of inventing a certain explanation.
- Count only productive work; retain scores, progress, freeze/cooldown history
  from public transitions. An escape must leave the defender's whole territory.
- Preserve original action objects while normalizing public board/action formats.
  Abandon a repeatedly unsuccessful job only when its expected completion has
  failed to change the cell. Expose unexpected input/policy failures to tests.
- Keep per-seat process isolation, immutable source snapshots, exact public inputs,
  move deadlines, stale/concurrent action guards and durable match recording.

The three new variants were developed after exploratory screening and frozen
before final confirmation. The guarded core preserved all 5,120 canonical actions
of its parent while adding interface/failed-job guards. A legacy-pricing ablation
kept corrected tracking but disabled three strategic additions; it passed 2,560
public oracle callbacks but scored lower. A corrected PR10 goal-forecast variant
passed moving/mutual-Shield and 1,280-callback tracker oracles, yet lost strength.
It was not concatenated into the selected policy. More mechanisms did not imply
better play. Existing forecasts, exact-copy exploitation, neural/GPU work and
territorial-intent hypotheses remain assessed in the branch review/history.

## Registered comparison

| Round | Policies | Games | Timed callbacks | Purpose |
|---|---:|---:|---:|---|
| All-source screen | 69 | 828 | 264,960 | Broad selection, including twelve exported novel class-based testers |
| Balanced development | 15 | 1,920 | 614,400 | Four fresh boards, all 16 corner/token combinations in both fields |
| Frozen final confirmation | 6 | 2,304 | 737,280 | Eight further boards, all 16 combinations in three contrasting fields |
| **Total** | **72 distinct policies across rounds** | **5,052** | **1,616,640** | |

Every seat ran in its own fresh Python worker per game. First calls had a
2,000 ms limit; subsequent calls had 200 ms. Only `board`, `bot_id`,
`is_priority_token` and `legal_actions` were passed. The referee and worker were
pinned before each run; source, benchmark and fixture hashes were checked again
afterward. Accepted actions, scores, timing and faults are stored in the compressed
full results, so the scoreboards can be independently replayed.

The screen recorded 961 faults, all from two excluded tester/control sources:
`agent_new.py` was incompatible with the public interface (960 exceptions), and
an intentionally buggy opponent returned one illegal action. None is retained.
Every development and final callback completed without a recorded worker fault.
All retained testers had zero worker faults in their measured comparisons.

## Final result and uncertainty

| Frozen policy | Opponents outscored / 3 | Mean score | Worst focal callback |
|---|---:|---:|---:|
| **Guarded corrected Transfer** | **1.8750** | **2903.32** | **1.21 ms** |
| Previous Transfer release | 1.8516 | 2899.08 | 1.59 ms |
| Original Transfer | 1.7474 | 2881.07 | 1.45 ms |
| Corrected Transfer, legacy task pricing | 1.7279 | 2882.28 | 2.10 ms |
| Repaired evolved research | 1.5391 | 2862.42 | 2.02 ms |
| Previous main fusion | 1.5247 | 2854.85 | 1.72 ms |

Each policy played exactly 384 common fixtures. Ties contribute half a result.
These are local paired outcome measurements, not actual tournament win rates.
The selected policy led both development and final point estimates. Its final
+0.3503 over previous main has an eight-map clustered 95% bootstrap interval
[+0.0547,+0.6641]. The +0.0234 over the closest prior release has interval
[-0.0495,+0.0964]; that small difference is inconclusive. It also has verified
current-rule tracking and a stronger public-input contract than that older file.
The economic-pressure subgroup favors the previous release slightly. Finite
fields and eight map clusters cannot prove a universally strongest strategy.
No code or weights were changed after the final registration.

## Release and simulator checks

**93 Python tests and six offline interface logic groups pass after removing the
old research dependencies.** Tests cover rule corner cases, 24 full randomized
differential games against an independent engine, public-history inference,
real worker failures/deadlines, strict AI view, recording corruption/durability,
request races and downloaded-folder operation without Git. The selected bot also
passes 1,280 direct public self-play calls with exact own score/progress/clock,
actual cooldowns retained in its public belief sets, no input mutation and no
fallback. Its worst callback in that run was below 1 ms. A separate real-worker
human-play pipeline completed and recorded all 80 turns, then reproduced every
recorded transition and score from the saved actions with zero faults.

The independent reference engine is used only by tests; it is never a playing
input. Source/AST checks reject development imports and I/O/dynamic execution in
the submitted bot. Historical private counters used for offline labels are not
passed to players. Visual testing is optional under the user's latest instruction.
The existing live game was not advanced, replaced or reset during this work.

## Compact branch and reproduction

The runtime has one bot, six standalone tester bots and one simulator. Old
experiments and bulky historical result trees stay in Git history at `d385e00`
and the recorded branch commits. New findings, complete compressed comparison
actions/results and all 72 exact policy sources are retained as validation evidence.
They are not rebound to incompatible historical measurements.

Run `python tools/check_release.py` for the automated checks. To repeat a
comparison, run `python tools/unpack_sources.py`, then the benchmark command in
the root README with a fresh output path. The archived source hashes, registered
fixtures and full result data remain available without Git or external services.
