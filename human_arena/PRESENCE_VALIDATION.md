# Corrected Shield rule: implementation and validation

The simulator now follows the rule clarified by the user on 2026-11-08: **after movement, Shield catches every eligible rival on the shielder's territory, including arrivals and moves between that owner's cells**. Already-frozen rivals remain ineligible. Moving completely off that owner's land escapes. Using your own Shield does not grant immunity to another owner's Shield; both active shields still resolve.

[Play the updated simulator](http://127.0.0.1:8775/). The selected policy is **Transfer planner - updated Shield rule**. Its [single-file export](release/bot.py) has SHA-256 `aef27c1c5d6c1dadccdbe51fabc2e53ec32c10d592a9ed917bd9b49ee4fca42c`.

## Exact turn-34 regression

In uploaded game `44e7eb1d4c604285ab1af22ba0b3b7dc`, Blue used SHIELD while Red moved WEST from Blue's D4 to Blue's C4. Replaying the recorded actions under the corrected rule preserves the first 33 turns and changes turn 34 to:

- Red arrives on C4, is caught, loses progress and freezes for the next two turns.
- Blue's Shield succeeds and Blue remains unfrozen.
- Blue's shield cooldown becomes four; nobody captures Blue's cells that turn.

This was checked through the actual interface using an isolated, clearly labelled scripted replay of those recorded actions. The displayed next board has Red frozen on C4 and Blue's movement controls enabled. That scripted replay tests physics and presentation, not bot strength. The original uploaded JSON and its historical rule flags were not edited.

[Interactive before/after replay](analysis/rule_clarification/turn34_replay.html), [exact state/event comparison](analysis/rule_clarification/turn34_comparison.json).

## What changed

`HumanGame` explicitly sets `catch_requires_stay=False` for new matches. The existing referee already supports this interpretation, so its pinned source and historical provenance remain unchanged. Recordings save the complete actual rules and their hash; new records use rules SHA `d2c5758f8697d4f04c9250bb73a9e750db30e941f87509a2d414657b751cd1c6`. Historical replay tests explicitly retain the old rule where needed.

The bot's public-history solver now attributes freezes using rivals' positions after movement and ownership before captures. It includes moving victims and mutually shielding rivals, retains genuinely ambiguous cooldowns, and counts movement within one owner's land as continued exposure. Escape and bait choices must leave that owner's entire territory. The selected candidate retains the existing weights and the prior task/defense pricing; it does not add unvalidated route penalties.

The broader candidate initially added new entry-risk pricing and defensive forecasts. It passed correctness checks but lost strength in the first comparison. A smaller version preserved the corrected tracking and escape geometry while retaining the prior scoring. The smaller version led development, then led a separately registered follow-up; no changes were fitted after that final run.

The separately tested forward planner also has corrected embedded world physics and shield inference. It remains selectable but was not the leading adapted version. Original branch snapshots and previous release sources remain preserved. The previous standalone export was archived by its hash before replacing the active export.

The user interface explains the rule for the actual server/match version. New matches have their own `validated_presence_catalog.json`; older running servers continue reading the unchanged legacy catalog. This prevents silently pairing a new-rule policy recommendation with an old-rule server. Existing matches on older tabs are preserved; use the new simulator for corrected rules.

## Verification

**125 integrated regression tests pass.** They cover moving between owned cells, arrivals, exits, mutual shields, already-frozen exclusion, work reset, full-land protection, exact turn 34, versioned catalogs, history hashes, process isolation, public-input immutability and tracker reconciliation. The new forward model additionally agrees with the two reference engines across 24 randomized 80-turn action sequences. The smaller policy passed another 13 applicable variant checks and two full public-input self-play games with exact progress/score/cooldown assertions.

**Six browser logic groups pass**, including keyboard behavior, delayed-history privacy and versioned rule explanations. Two independent 80-turn visual games completed under the corrected rules, including the selected candidate. Both saved exactly 80 turns, without bot faults or browser console errors. Switching to AI view preserved the match, retained only the four public observation fields and hid scores, results, history and counters. The scripted turn-34 scene also passed in the real interface. [Visual evidence](validation/presence/visual_qa.json).

## Strength evidence under the corrected rule

The new comparison contains **1,136 games and 363,520 timed callbacks**, with **zero recorded faults**. Actual isolated worker processes enforce the 200 ms turn limit and first-turn two-second limit. Every bot receives only the four documented public observation fields. No pending human action, referee object, opponent source or private counter is supplied to a playing policy.

First, the distinct branch/root exports were screened under the corrected physics. The first balanced confirmation compared the three adapted implementations and the previous release, using both a legacy opponent lineup and a lineup of the three adapted policies. It revealed the strategic regression described above; that test is now selection data. An ablation screen selected the smaller candidate. The final follow-up used eight distinct board contents excluded from the earlier corrected-rule selection sets, with every one of the 16 corner/priority-token combinations balanced per map.

| Final follow-up, 128 games per version | Opponents outscored / 3 | Mean score | Worst focal callback |
|---|---:|---:|---:|
| **Selected smaller rule-corrected Transfer** | **1.7539** | 2767.4 | 1.34 ms |
| Previous release under corrected physics | 1.7227 | 2764.2 | 2.04 ms |
| Broader rule-corrected Transfer experiment | 1.4961 | 2729.6 | 0.99 ms |

The selected version's gain over the broader experiment is +0.2578, with eight-map clustered bootstrap interval [+0.1445, +0.3750]. Its +0.0313 over the previous release has interval [-0.0234, +0.0938], so that small strength difference is inconclusive. Selection is supported by verified rule correctness and the highest measured adapted-policy result; these finite games do not prove a universal strongest bot. Scores from the old STAY-only model are not pooled into this ranking.

[Selection and uncertainty](validation/presence/release_selection.json), [final registered sources/rules/fixtures](validation/presence/confirm_followup_presence_registration.json), [all final results](validation/presence/confirm_followup_presence_results.json), [first corrected-rule comparison](validation/presence/confirm_presence_results.json).

The official public wording had been ambiguous; this update adopts the explicit user clarification rather than claiming that the earlier wording explicitly excluded moving rivals. Previous validation reports are marked historical. The organiser's actual competition server remains authoritative.
