# Simulator and bot repair validation

> Historical validation of the former STAY-only shield interpretation. The user subsequently clarified that Shield catches eligible rivals on the owner's land after movement, including arrivals and movement between that owner's cells. These results remain reproducible historical evidence but do not rank bots under the corrected rule. See [the replacement validation](PRESENCE_VALIDATION.md) and the updated simulator on port 8775.

Validated 2026-11-08. The playable release is **Repaired transfer planner**, selected from frozen source comparisons. Open [the updated human simulator](http://127.0.0.1:8773/). The single-file export is [release/bot.py](release/bot.py).

## What was repaired

The evolved and transfer policies now infer shields from feasible public transitions. Moving, visibly completing work, or losing a holding rules out shielding. A rival freezing while its landlord visibly upgrades is treated as a possible self-backfire rather than falsely assigning the landlord a cooldown. Ambiguous cases retain possible cooldowns; the planner cannot turn ambiguity into a certain safe raid window. Own legal actions help reconcile a SHIELD request that the server replaced with STAY. Progress is cleared on completed work and unavailable work, and blocked movement is treated as the resulting STAY.

The planning correction discounts an upgrade after an enemy raid by the estimated chance of first completing that raid. It recognizes demonstrated renewable shield defenses and can leave a three-stay raid that will repeatedly be reset. A non-imminent intruder on upgraded land no longer triggers the same premature defensive shield. These are conditional estimates and bounded job scheduling, not perfect predictions of future opponent actions.

A separately repaired forward planner fixes the home-stillness clock reset, initial income, and public shield/progress bookkeeping. It was tested but did not lead this comparison. Original root research work and historical branch snapshots were preserved; repaired playable sources are isolated under `candidates/` and the selected export is under `release/`.

The simulator now contains per-seat worker/protocol failures as STAY and retires broken workers; rejects malformed requests before changing a match; preserves a match if its replacement cannot be created; rejects corrupt history without breaking the history list; and prevents keyboard/delayed-history races from submitting the wrong action or exposing observer information in AI view. Selected local sources require exact manifest hashes and are copied into immutable per-match snapshots. Recording errors stop further turns.

## The reported freezing issue

The new upload contains a sequence of separate legal freezes. Your SHIELD on turn 61 caught nobody, causing a backfire and forced stays on 62–63. Coral then caught your upgraded B5 raid on 67, 72 and 77. Movement returned on 70, 75 and 80, but you chose STAY and retried the same raid. Two frozen turns leave only two productive stays before the defender's four-turn cooldown ends, so the next shield resets the third stay again.

All 80 transitions, observations, resolutions and final state reproduce exactly. No freeze-duration rule was changed. Standard view now shows the exact `2 → 1 → 0` countdown, distinguishes backfire from being caught, and announces when movement returns. [Detailed freeze review](analysis/a4897686/freeze_review.md).

## Checks

- **84 regression tests pass**, including exact physics parity, tracking uncertainty, public-input purity, request races, worker cleanup, durable history, source pinning and both uploaded games.
- The transferred configuration passed another **14 applicable policy regressions**, including randomized 80-turn histories and the independent B5 escape case. It uses the exact preexisting transfer weights; the corrected implementation is otherwise identical to the evolved repair.
- **63 core engine checks** and **3 visual replay checks** pass.
- **5 browser logic test groups** pass: keyboard activation, delayed history/download privacy, candidate metadata, freeze/thaw controls and limited AI view.
- Two separate **80-turn games** were driven through browser controls with the repaired evolved and selected transfer versions. Both saved exactly 80 turns and finished without bot faults. Keyboard movement, Space after a movement button, frozen-action rejection, countdown, thawing, same-match view switching, strict final results, saved history, and download availability were checked. No browser console errors or horizontal overflow appeared. [Visual evidence](validation/visual_qa.json).

## Strength comparison

The live GitHub inventory was checked across nine remote branch names; duplicate policies were grouped by exact bytes. The screen included all nine distinct standalone root/output policies available from those branches plus the current local v9 export. Repaired variants were then tested separately. No checkout or frozen opponent implementation was silently replaced.

There were **1,520 tournament games and 486,400 timed bot callbacks**, with **zero recorded faults**. Every seat used a new isolated worker for each game and only the official four-field public observation. The actual 200 ms deadline (2 seconds first turn) was enforced throughout. The initial narrow screen accidentally selected only one opponent lineup; that limitation was detected, preserved in its record, and corrected in the subsequent balanced screen. The schedule now has regression checks for opponent, seat and token balance.

The first 768-game confirmation tested six versions on eight maps, all 16 seat/token combinations per map. Four maps were new generated maps and four were rule-valid stress boards. Its highest point estimate belonged to the original transfer weights. That result became selection data: the same verified corrections were applied to those preexisting weights, without tuning, before a second test was registered. The follow-up used eight board contents disjoint from both earlier selection sets, including fresh corner/edge/uniform quadrants, and balanced all 16 seat/token combinations again.

| Final follow-up, 128 games each | Opponents outscored per game / 3 | Mean score | Worst focal callback |
|---|---:|---:|---:|
| **Repaired transfer, selected** | **2.1250** | 2787.0 | 1.22 ms |
| Repaired evolved | 2.1172 | 2796.4 | 1.32 ms |
| Original transfer | 1.9336 | 2747.9 | 1.98 ms |

Selection uses the highest pairwise point estimate, which matches the Round 1 objective, rather than raw score. The two repaired versions differ by only 0.0078; the eight-map clustered 95% bootstrap interval is [-0.2578, +0.2813]. Their ranking is inconclusive. Repaired transfer versus its original is +0.1914, interval [-0.0430, +0.4883], also inconclusive at this cluster count. Neither interval establishes a universal advantage. This is the strongest measured repaired setting in a finite fixed field, not proof of an optimal bot or an estimate of competition Elo. No new source or parameter was fitted after the follow-up.

[Machine-readable selection and uncertainty](validation/release_selection.json), [final registered fixtures and source hashes](validation/confirm_followup_registration.json), [all final game results](validation/confirm_followup_results.json), [first confirmation](validation/confirm_release_results.json), [balanced branch screen](validation/screen_balanced_results.json).

The selected file SHA-256 is `fe03b8164ed3b4ebd2a04abcdfbb6fa729bdc34dea825088f7e82bf6e5b5ab5e`. The simulator manifest, immutable match copy and standalone release use those same bytes. Bots receive no pending human choice, hidden referee fields, opponent code, filesystem or network information. The selected source imports only the standard library and copies public observations into its own bookkeeping. This remains a local implementation of the published rules; the organiser's server is authoritative.
