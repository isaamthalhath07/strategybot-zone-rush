# First training stage: bounded live oversight

Snapshot: **2026-11-08 19:28:43 UTC**. This document describes that snapshot,
not the run's eventual completion status. Machine-readable proof is at
`.cache/primary/campaign_v1_20261109/live_review_001.json`.

**No blocker was found in this bounded review.** The single-owner, eight-worker
run may continue to its mandatory full independent audit. The review accepts
**zero primary games** and records **zero BMCTS audits**. No candidate was ranked
or promoted using partial results.

## Verified at the snapshot

- The sealed full plan contains 10,000 maps: 8,000 training, 1,000 development
  and 1,000 final. Current source files and the frozen source ZIP match their
  hashes. The incumbent remains unchanged.
- The first stage has 20,000 single-assignment tasks and 60,000 context-bound
  rival instances. Its eight candidates each have 2,500 planned games, with the
  reviewed field/corner/token balancing and exact rival-generation recipes.
- **8,238 complete game records** were observed. Their task assignments and
  identities were unique and correct. Structural/action-name checks, callback
  counts and finite timing records passed; recorded faults were zero.
- **17 games** were independently replayed in both referees, regenerating all
  **5,440 actor decisions** exactly and checking **2,640 supported public-memory
  states**. The sample covered all eight candidates, all 16 field/corner pairs,
  all four map families, and the worst recorded timing outlier.
- The largest recorded normal call was **89.33 ms** across all players; the
  focal maximum was **45.07 ms**. All observed timing records met the 200 ms
  normal and 2,000 ms first-turn limits. There were 1,556 games containing at
  least one call of 10 ms or more. These remain valid, but increasing concurrency
  without checking the timing tail would reduce safety margin.

The family counts show no obvious large phase/family imbalance:

| Phase | Centre biased | Noisy centre | Uniform stress | Rich-home stress |
|---|---:|---:|---:|---:|
| Training | 4,798 | 1,558 | 821 | 823 |
| Development | 607 | 184 | 104 | 105 |
| Final | 606 | 194 | 106 | 94 |

This is descriptive coverage, not proof against overfitting. The custom map
distribution and finite related opponent implementations retain the limitations
listed in [the pre-scale review](REVIEW.md).

## What this review does not establish

The 8,238 records received structural and timing checks; only the stated 17-game
sample received this additional independent action/physics replay. The active
runner must still finish all 20,000 games and regenerate every actor decision in
both referees before the stage is credited or its fitness can breed another
generation. A completed append is not independent acceptance.

The live log was read without modifying it. Any incomplete trailing bytes would
have been ignored in memory, never repaired while the writer was active. This
snapshot had no such trailing bytes. The additional replay is oversight work,
not new primary games. It makes no GPU or BMCTS contribution claim.

Handoff: preserve the frozen sources, keep one owner, continue the automatic
full-stage gate, and quarantine any mismatch rather than substituting a successful
record. Check the final sealed audit for accepted counts; do not infer them from
this live snapshot or from partial outcome averages.
