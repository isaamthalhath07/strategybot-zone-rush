The new search did not demonstrate an improvement in this frozen causal experiment. Across sixteen selected close-margin TRAIN positions, it changed eight decisions: two improved the eventual pairwise result, three worsened it, and eleven of all sixteen left that result unchanged. Mean change was **-0.03125 pairwise points** on the official 0..3 scale. The descriptive within-field interval was **[-0.21875, +0.15625]**. This is too little selected data to establish a general strength difference in either direction.

The complete plan and exact sources were committed and pushed as `816a30a101b1280d753b9e8d040b84f37cccbeeb` before any teacher recommendation or alternative outcome was measured. Selection used only the public prefix and a fixed score/income projection. All sixteen cases completed without replacement, retry, tuning or omission. Opponents were rebuilt with their real controllers and RNG and responded to changed boards. Their recorded future moves were never substituted after an intervention.

| Case | Rival field | Turn | Original | Search | Final pairwise change | Best legal one-step headroom |
| --- | --- | --- | --- | --- | ---: | ---: |
| 00 | economic | 30 | STAY | EAST | -1 | 0 |
| 01 | independent | 30 | WEST | WEST | 0 | 1 |
| 02 | erratic | 30 | STAY | STAY | 0 | 0 |
| 03 | pressure | 30 | NORTH | WEST | 0 | 0 |
| 04 | economic | 50 | STAY | STAY | 0 | 0 |
| 05 | independent | 50 | STAY | NORTH | 0 | 0 |
| 06 | erratic | 50 | STAY | STAY | 0 | 0 |
| 07 | pressure | 50 | SOUTH | STAY | 1 | 1 |
| 08 | economic | 65 | STAY | STAY | 0 | 0 |
| 09 | independent | 65 | STAY | SOUTH | -1 | 0 |
| 10 | erratic | 65 | STAY | STAY | 0 | 0 |
| 11 | pressure | 65 | STAY | EAST | 0 | 0 |
| 12 | economic | 75 | SHIELD | SHIELD | 0 | 0 |
| 13 | independent | 75 | STAY | SHIELD | -0.5 | 0 |
| 14 | erratic | 75 | STAY | STAY | 0 | 0 |
| 15 | pressure | 75 | STAY | WEST | 1 | 1 |

All legal root actions were tested, including an explicit repetition of the original action. Every unchanged baseline and explicit original-action branch reproduced the complete original 80-turn action tape and final scores. There were **107 full branch replays, 34,240 regenerated actor callbacks and 8,560 continuation turns checked by both referees**. These are diagnostic replays and alternatives to consumed games, not new primary matches. The search separately checked 9,216 hypothetical turns in both referees. Separate independent receipts distinguish the callback checks recorded by the frozen runner from independent action-only physical replay.

There was room for a better one-step choice in three cases. Search found the improvements in cases 07 and 15, missed case 01, and introduced losses in cases 00, 09 and 13 where the original action already achieved the best tested rank. Hindsight headroom averaged +0.1875 points; it is an evaluator diagnostic for these realized responding opponents, not an available public oracle or a globally optimal strategy.

Case 13 is a concrete sequencing failure at turn 75. The original policy stayed on a neutral base-2 cell, then shielded on turn 76. The recommended intervention shielded immediately, then stayed for the remaining five turns. The focal final score fell from 2,597 to 2,595 while the relevant rival remained at 2,595: a win became a tie. This root had exactly six turns left, and search reached the true terminal state. A truncated horizon alone cannot explain this error. The search's own future decisions differ from the original policy used after the real intervention, and its hypothetical opponents also differ from the realized controllers. This experiment does not separate their causal contributions from finite sampling.

The main architectural concern is therefore decision alignment. The search values future control by its tree plus an economic fallback rollout, while this causal test executes one suggested action and returns control to the original bot. Its four persistent rival styles also retain no explicit target or route memory. Better next-observation likelihood from the earlier predictor pilot does not establish accurate long-term goals or better decisions. More simulations could estimate a misspecified continuation more precisely without repairing this mismatch.

A useful next controlled comparison is a baseline-aligned root evaluator: reconstruct the bot's own memory from the public prefix, force each candidate root action, then let that same bot continue in every sampled future. Compare it with the current teacher under a preregistered matched physics budget on new disjoint TRAIN positions. That redesign changes the future-control target and search allocation together; it cannot be described as isolating a single rollout factor. A pure fallback-policy change is a different experiment. Fresh complete-match architecture confirmation is still required before choosing a production bot.

Offline teacher duration ranged from 0.442 to 1.228 seconds, with median 0.649 seconds, excluding process import. Every measured call exceeded the regular 200 ms game budget. No online qualification, promotion, new primary-match credit or completed per-game BMCTS audit follows. The released standalone bot remains unchanged.

Exact evidence is in [the sealed result](results.json), [the full compressed raw inputs, trees and branches](raw_results.zip), [the archive hash manifest](raw_archive_manifest.json), [the summary](summary.json), and the separate independent reviews in this folder. The previously published preregistration and frozen source archive remain unchanged.
