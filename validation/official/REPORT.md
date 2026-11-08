# STAY-only Shield clarification: release validation

## Authority and exact behavior

The explicit clarification supplied by the user supersedes the earlier
territory-presence interpretation. The current contract is stored in
`rule_contract.json`: movement resolves first; Shield catches only eligible
rivals whose effective action is STAY on the shielder's land. Successful movement
escapes even between two cells owned by the shielder. A blocked or lost-contest
move becomes STAY and can be caught. A valid Shield action is not STAY.
Already-frozen rivals remain ineligible.

Caught or backfired on turn 10 means forced STAY on turns 11 and 12. Shield
used on turn 10 is unavailable on 11Ã¢â‚¬â€œ14, so the earliest next use is 15.
Empty catches backfire without removing cooldown. Scoring, work requirements,
full-land protection and the exclusion of frozen work are unchanged.

The pinned referee already implements this mode. Its source, the worker and
independent test oracle remain unchanged. New simulator matches explicitly set
`catch_requires_stay=True` and save their actual full rules/hash. The new port is
8779; older running matches retain their original rules and source snapshots.

## Original turn 34

The original uploaded `44e7eb1d...` transcript contains the STAY-only flag.
All 34 before-states, resolutions and after-states replay exactly under the
clarified rule. On turn 34 Red moves WEST from D4 to C4 and escapes. Blue catches
no eligible rival, backfires and is frozen for the next two turns. The original
recording was correct; the later territory-presence reinterpretation is now
superseded. `turn34_verification.json` preserves the input-file hash, base,
recorded actions and exact final transition without editing the download.

## Current single-file bot

The selected release is `stay_guarded_resilient`, SHA-256
`e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5`.
Root `bot.py` is byte-identical to the registered source. It imports only
`collections` and needs no extra file, weights, private state or future actions.
The standalone research alternative differs only in its historical CONFIG genome.
No strategic coefficient was fitted during this correction.

The correction restores effective-STAY catch inference, excludes active
shielders as rivals' victims, learns actual stationary commitment and permits
valid same-owner-cell feints. It retains every feasible ordinary Shield cause
and cooldown set. Its public-input normalization, original action-object return,
failed-job escape and legal fallback guards remain intact. Known available own
casts remain identifiable even when they backfire; unfiltered legal-action lists
cannot fabricate availability or enable known cooldown violations.

The audit found an additional external-substitution edge: a late requested
Shield can become STAY while module memory remembers the request. The recovery
revision retries a physically contradicted own-cast assumption and reconciles
productive STAY work. Six directed tests cover incomplete/completed own work,
neutral claim, incomplete/completed upgraded raid and a visibly excluded own
cast with a rival catch. Independent probes verify retained cooldown truth and
accepted-backfire certainty.

Recovery is bounded by information. Legal timely own requests are assumed
accepted unless public evidence contradicts them. An accepted backfire and a
silently substituted STAY caught by a landlord can be observationally identical
under this four-field interface. No private acknowledgement is invented, and
that unidentifiable case is documented in
`unacknowledged_substitution_ambiguity.json`.

## New comparison, separate from historical False-rule data

| Round | Focal policies | Games | Timed callbacks |
|---|---:|---:|---:|
| Archived admissible-policy screen | 70 | 840 | 268,800 |
| Balanced selection | 12 | 1,536 | 491,520 |
| Frozen six-policy round | 6 | 2,304 | 737,280 |
| Recovery-only two-genome follow-up | 2 | 1,152 | 368,640 |
| **Total current-rule evidence** | **74 distinct admissible implementations across rounds** | **5,832** | **1,866,240** |

All current-rule callbacks completed without a recorded worker fault. Two
previously identified incompatible/deliberately faulty controls were excluded
before this screen; exclusions are registered. Every seat runs in a fresh
isolated process for each game, with 200 ms per regular call and 2,000 ms for
its first call. Only the four documented public fields reach the policy.
Sources, rules, fixtures, benchmark, referee and worker are hash-bound before
and after every run; complete actions, scores, timing and faults are compressed
alongside the registrations.

Balanced development used four distinct fresh boards and all sixteen corner/
priority-token combinations in both fields. Transfer tied the repaired old
Transfer at 1.859375 mean opponents outscored; the research genotype scored
1.6875. In the next eight-map, three-field round, research led at 1.6328125,
versus 1.5950521 for Transfer; that small reversal was inconclusive.
Those data are selection evidence, not a reason to claim a certain winner.

The recovery revision was frozen separately. On all 768 recorded games of the
two parent policies, both revised versions reproduced **61,440 exact focal
public-action pairs**, with no recovery triggered on ordinary accepted-action
histories. This supplements 5,120 exact pairs on additional fresh games. The
revised files then received their own real-worker follow-up, rather than
silently inheriting another file's measured hash.

## Latest fresh follow-up and uncertainty

Each corrected genome played 576 common fixtures: twelve further distinct boards,
three contrasting fields and all sixteen corner/token crossings per field/map.

| Frozen policy | Opponents outscored / 3 | Mean score | Worst focal call |
|---|---:|---:|---:|
| **Selected guarded Transfer** | **1.7300** | **2871.26** | **2.02 ms** |
| Guarded research alternative | 1.4991 | 2827.66 | 1.48 ms |

The paired advantage is +0.2309 with twelve-map clustered 95% bootstrap interval
[-0.0243,+0.4939]. Transfer led balanced development and this follow-up; the
research alternative led the preceding eight-map round. The latest interval
includes zero, so the selected file is the best measured follow-up option with
verified current-rule behavior, not proof of universal superiority. The two
policies tied in the novel-pressure subgroup. The final root file was not
changed after follow-up registration.

The earlier presence-rule 5,052-game campaign remains intact and explicitly
historical. Its scores are not pooled into the STAY-only ranking. The old root
manifest and benchmark source are archived; old tests replay their recorded
False mode and exact old policy, rather than rewriting their evidence.

## Automated release checks

**133 Python tests and six offline interface logic groups pass.** Coverage
includes all supplied examples, blocked/lost-contest STAY catches, valid moves
escaping, simultaneous Shield backfires, exact turn-10 timers, 24 complete random
differential games for EACH of the two historical/current modes, public-history
oracles, rejected-cast recovery, source/fixture evidence integrity, actual 80-turn
worker recording/replay, downloaded-folder operation without Git, request races,
durable/corrupt history and strict four-field AI views.

The final bot's direct oracle tests cover 3,840 public callbacks, plus 1,280 release
self-play calls, without input mutation, illegal output, hidden fallback or
loss of actual cooldown possibilities in ordinary accepted-action histories.
Current-rule raw outcomes and sampled scoreboards independently recompute/replay.
The original turn 34 regression also replays from its recorded actions.

The simulator exposes only public rule definitions outside the strictly limited
AI observation, so historical False matches retain accurate help text in both
views. A manifest explicitly naming the wrong Shield rule cannot recommend the
root bot in the new simulator; compatible tester controls and existing historical
matches remain available. Old records and live games are not migrated or reset.
Visual testing is optional under the user's instruction; automated checks and
actual isolated games provide the release verification.

## Reproduce

Run `python tools/check_release.py`. For a new copy of a comparison, first run
`python tools/unpack_sources.py`, then use the current root README command with
a new output path. Both historical and added source archives are verified;
changed files and consumed results are never overwritten. Optional exact parent/
recovery replay is `python -m tools.replay_policy_equivalence` after restoration.
All original datasets and source snapshots remain available without Git.

## Concurrent UltimateBot control

Main advanced to `b926add` while this correction ran, adding `ultimate.py`, its
identical tester copy and seven architecture tests. Those three files are
preserved byte-for-byte. The independently frozen source
`a8f7a74e7ed34548f092dc0acfa5402a47a6c4c2f0115359fc2e56ecfe1b9b73`
was run on the exact 576 follow-up fixtures under the STAY-only rule: 1.3446
mean opponents outscored and zero worker faults. The selected release scored
1.7300 on those fixtures. Ultimate's model tries the presence interpretation
first and picks a plausible cause, and several supplied tests explicitly use
False; neither architecture claims nor those historical cases establish current
rule correctness. It remains an experimental control, not the promoted bot.

The additional control adds 576 games / 184,320 timed callbacks, making the total
current-rule comparison evidence 6,408 games / 2,050,560 callbacks. The original
four campaign records and their 5,832-game total remain unchanged.
