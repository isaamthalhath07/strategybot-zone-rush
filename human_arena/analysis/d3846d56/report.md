# Strategy review: game d3846d56

**The main weakness was poor reasoning about opponents' conditional responses, amplified by a definite cooldown-inference bug and an optimistic route-value calculation. It was not simply failure to visit the centre.**

The human won 2,378 to 2,179, 1,924 and 1,615. The strongest AI lost by 199; the weakest by 763. This review covers the uploaded complete match, not the earlier unrecorded games.

## Evidence and verification

All 80 physical transitions, all 320 seat observations, and the final snapshot reproduce exactly through the fingerprint-matched local referee. The exact recorded evolved policy reproduces **all 240 AI actions**, allowing inspection of its inferred memory and ranked candidate jobs. Turn and score estimates match the recorded truth throughout; the specific cooldown errors below do not imply that all of its memory is broken. There were no recorded AI faults; the slowest recorded AI callback was 0.773 ms. The loss was strategic, not a timeout or crash.

Source: `origin/research/evolution-2026-11-07`, commit `0796039f42f0113d7c4f51b2f8e1409835f2c519`, `outputs/bot.py`, SHA-256 `1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca`. Input/source/referee/rule hashes and exact replay checks are in [summary.json](summary.json). The recorder's observer data was used for post-game verification, never supplied as extra input to a playing policy.

[Open the annotated replay](replay.html). It shows every board, score and income trajectory, the selected AI's actual job ranking, and estimated versus recorded shield cooldowns. Try bookmarks 42, 54, 55 and 57. The replay contains hindsight observer information and is separate from the live game.

## What won the game

| Player | Final score | Central-cell income | Other ownership income | Raid bonuses | End income/turn |
|---|---:|---:|---:|---:|---:|
| You, Blue/1 | **2,378** | **840** | 1,538 | 0 | **50** |
| Coral/2 | 1,924 | 417 | 1,491 | 16 | 33 |
| Mint/3 | 2,179 | 417 | **1,682** | **80** | 44 |
| Gold/4 | 1,615 | 0 | 1,599 | 16 | 32 |

You captured D4 on turn 7 and upgraded it on 10, then captured D5 on 12 and upgraded it on 15. Coral and Mint captured E4/E5 on turn 10 and upgraded both on 13. The bots therefore secured **half the four central three-point squares**, not none.

Your two central squares produced 840 points. Mint's central square produced 417. Mint actually earned 144 more noncentral income and 80 more raid points than you; those recovered 224 of your 423-point central-income advantage, leaving your exact **199-point winning margin**. This is a stronger explanation than “the bots wandered aimlessly around the sides.”

You also converted your holdings reliably: all 14 final cells were upgraded. Your one shield, on turn 57, caught both Coral and Gold. At that moment your current square was already upgraded, so a STAY there offered no additional work completion.

## 1. Definite bug: a backfire was attributed to the wrong player

Turn 54 gives a particularly clear causal chain:

1. Coral uses SHIELD while standing on your C2. Its shield catches nobody and backfires.
2. You STAY and visibly upgrade C3. That upgrade proves you did **not** SHIELD.
3. On turns 55–57, all three AI copies nevertheless believe your shield cooldown is **4, 3, 2**. The recorded truth is **0, 0, 0**.
4. Gold continues its D4 raid under this fictitious protection. Your real shield catches it on turn 57.

The source treats a new freeze on rival land as evidence that the landlord shielded, but does not constrain that inference with the landlord's visible work. It also fails to use Coral's knowledge of its own SHIELD consistently: Coral believes its own cooldown is zero on turns 55–58, when it is actually 4, 3, 2, 1.

This is avoidable uncertainty. The observed C3 upgrade rules out a human shield. Coral's new freeze must be its own backfire, which establishes Coral's real cooldown instead.

**A useful move was missed because of the same error.** At turn 55, Gold can move EAST from D4 to empty E4, then STAY on turns 56–58. Coral's cooldown prevents a shield through turn 58; no rival can contest the first arrival, and occupancy closes the square afterward. This guarantees that target's capture and its 48-point raid bonus plus new three-point income under the current public facts. It does not guarantee retention of every other cell, a final score, or victory.

An offline public-information correction selects exactly that EAST move. With only Gold corrected, all AI opponents recomputing from the changed board, and your recorded action sequence retained, Gold improves **1,615 → 1,822** and moves fourth → third. The first changed decision is turn 55. Your actions remain legal in this comparison. You still win. This is a one-game diagnostic, not evidence of a universally stronger bot.

## 2. Definite modeling flaw: a risky raid receives a nearly risk-free follow-up reward

On turn 42, Gold has just served the freeze from its failed E4 raid. It can retry E4 or leave for useful work. The reproduced decision ranking is:

| Gold's first job at T42 | First-job value | Follow-up contribution | Total heuristic value |
|---|---:|---:|---:|
| Retry upgraded E4 raid | 8.77 | **49.67** | **58.44** |
| Go to neutral C2 | **13.79** | 30.01 | 43.81 |

These are the policy's heuristic units, not earned points. The raid itself is risk-penalized. The imagined upgrade **after successfully capturing that same cell** is not conditioned on capture success and does not properly inherit the risk-induced delay. The continuation bonus overwhelms the first-job warning.

There is an additional timing inconsistency: risk enlarges the modeled effort denominator, but route feasibility and follow-up income still use nominal travel-plus-work time. The planner effectively prices a slow/risky raid and then schedules its reward as if it finished promptly.

Removing only the post-raid upgrade boost, while keeping the actual observed prefix, changes Gold's turn-42 action from STAY to NORTH toward C2. This confirms the ranking mechanism. In a full replay where only Gold uses that ablation, it earns 1,858 rather than 1,615, but remains last. That replay diverges as early as turn 24 and one of your later scripted moves becomes illegal and is replaced by STAY; it must not be treated as a prediction of an adapting human's game. No diagnostic variant has been shipped.

## 3. Persistent failure: repeated commitment into a renewable shield lock

Gold is caught on E4 at turns **39 and 44**, on E5 at **50**, and on your D4 at **57**. It serves eight forced frozen turns. From turns **37–62**, it completes no claim, upgrade or raid, and its income stays at **24**. That is a 26-turn economic dry spell, not 26 identical idle actions: some turns are movement or discarded partial raid progress.

The timing is exploitable. After a catch, the attacker freezes for two turns. When it can work again, the defender has only two cooldown turns remaining. A fresh upgraded-cell raid needs three STAYs, so a committed defender is ready again on the completion turn. That is what happens on E4 at 42–44.

The bot learns an average shield frequency. It does not model the conditional response “wait until the takeover is imminent, then shield.” Its feint escape is also restricted to zero own raid progress. That prevents the feint override from rescuing a raid at precisely the later point when the defender's shield returns.

The correct repair is not “never raid upgraded cells.” A real cooldown can create a safe capture, as E4 on turn 55 demonstrates. It is to model readiness, completion time, commitment and a credible abort/feint branch together.

## 4. Your suspicion about future plans is partly correct

The configured search depth is two of the AI's **own economic jobs**, not two rounds of joint play. It does not assign each rival a likely next target, simulate their routes, or update future ownership according to those targets. It considers current occupied cells, nearest-rival distance, contest risk and learned defensive behavior, which is substantially less than forecasting an opponent's plan.

The learning tables mostly concern raiders already on AI-owned land while it can shield. They do not learn that you tend to finish upgrades on your own land, then move to the next valuable neutral square. A neutral capture receives own-income value, with no explicit credit for preventing an expected rival claim.

There was a plausible early intent window: before turn 10, your two post-claim STAYs on D4 made a next-turn upgrade likely. Gold at D7 could move NORTH on 10, NORTH on 11, and challenge neutral D5; turn-11 priority would beat your actual arrival. That is a legal contingent alternative, not proof it was best. You could leave D4 earlier, and a naive longer centre-rush opening earns Gold **14 fewer points by turn 10** than its actual opening. The future territory tradeoff must be evaluated, not assumed.

The retention-distance heuristic can discourage contested opening targets. It does **not** explain the late raid trap: from turn 37, the remaining horizon is already shorter than the retention cap, so that cap is inactive.

## 5. Coral's shield timing and contest handling lose tempo

Coral's shields on 39/44 and Mint's on 50 cannot all be called mistakes. In particular, 44 and 50 stop an imminent upgraded three-point takeover. Sacrificing a partial upgrade elsewhere can be justified to retain six income/turn and deny a 48-point raid bonus.

Coral's **54** shield is different: it backfires while Coral could instead capture your level-one C2. Holding the other recorded actions fixed, STAY earns 16 raid points plus two income immediately: **+18** that turn; a continued fixed-request replay gives Coral +24 by the end. The human's simultaneous action was not knowable, so this is realized regret, not proof that STAY dominates every response.

On **75**, Coral shields a newly arrived raider on upgraded E2 before a capture is possible. Mint leaves for D2, so the shield backfires. Mint then captures upgraded D2 on 78 while Coral is still on cooldown. This is a successful bait by Mint and a failure of Coral's timing/option-value model. Waiting on 75 and shielding on 78 improves Coral's margin against Mint by 48 points under the recorded continuation, but cannot be promised against different responses.

Coral also loses movement contests on 49 and 51, causing a short unproductive detour. There are only two such AI contest losses, no ordinary occupied-cell blocks, and no immediate consecutive movement reversals. This match does not support a claim of widespread pacing or broken movement.

## What is not established

- Mint played several effective raids and never froze. Its 199-point loss does not prove an individual fatal blunder. Its successful turn-75 feint is evidence that part of the tactical model works.
- The endgame was not the decisive failure. Exhaustive searches over the final two, three and four turns found no AI own-score improvement with other recorded requests fixed. Six-turn hindsight gains reach 44/16/30 points, with no placement improvement.
- No alternative here proves a higher win rate against unknown opponents. One game, one map and a fixed human script cannot establish that. The full-game baseline reproduces exactly, but a changed human would adapt.
- A rule error, hidden board, crash or deadline miss did not cause this result. The recorded policy and local referee were verified; equivalence to the unavailable official server is a separate question.

## Fix priority and fair validation

1. **Repair shield attribution first.** Use known own actions and visible captures/upgrades as hard constraints. Preserve uncertainty when multiple shield/backfire explanations remain. A fabricated cooldown must not be treated as a guaranteed attack window.
2. **Make continuation rewards conditional.** Price the probability and time of capture before valuing an upgrade or next job. Apply the same delay assumptions to horizon feasibility and income.
3. **Model conditional defensive responses.** Forecast shield readiness on each proposed STAY and include retreat/feint options after partial work. Recognize repeated defended-cell failure.
4. **Add limited opponent intent.** Infer target/upgrade commitment distributions from public history and score competitive neutral claims, rather than giving every centre a fixed bonus. Use expected pairwise placement value, not automatic leader-chasing or a fictitious coalition.
5. **Revalidate beyond this file.** Pair each narrow change against a frozen original across new maps, seats, human openings, patient defenders, baiters and farmers. Include nonregression cases where staying outside is genuinely best. Enforce the 200 ms/2 s budgets. Do not use future human requests as policy inputs or tune on this same match and call it held out.

## Reproducible evidence

- [Verified game summary](summary.json), [timeline](timeline.json), [per-decision beliefs and values](decisions.json).
- [Independent behavior review](behavior_review.md), [intent review](intent_review.md), [bounded counterfactuals](counterfactuals.md).
- [Offline model ablations](model_probes.json), with a fixed-human-script caveat and complete resulting trajectories.
- Reproduction: run `analyze.py`, `behavior_review.py`, `counterfactuals.py`, `model_probes.py`, then `build_viewer.py` from this folder or the project root as appropriate. No live game or production bot was changed.
