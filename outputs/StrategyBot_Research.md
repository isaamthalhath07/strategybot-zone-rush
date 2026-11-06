Historical baseline report. The later evolutionary comparison and current recommendation are in Evolution_Comparison.md. This report describes the preserved bot_before_evolution.py and its original test kit.

StrategyBot research and tested bot

Prepared on 6 November 2026 and updated after the organiser answers relayed in this chat. The accompanying `bot.py` is the selected single-file Python implementation with additional memory-recovery fixes. Its strategy weights were frozen before the audit. The evidence package contains the local referee, candidate programs, experiments, results and tests.

**The organiser answers confirm the main rules profile.** Frozen STAY turns give no capture or upgrade progress. A bot may remember earlier observations and must reconcile them with actual outcomes after blocked, illegal or substituted actions. The organisers supply no game history. They offer a server-compatibility check against the template, with official gameplay testing reserved for the final hardware stage. Use the updated `bot.py` as the competition candidate. The alternate frozen-progress profile is retained as a historical counterfactual experiment.

After the organiser clarification, two recovery bugs were corrected. A requested SHIELD that the server substitutes with STAY now earns the progress actually observed. A reversible opening in which all bots leave and return home preserves the turn count. The updated source passes eight recovery regressions. Across 40 full games with 765 injected own/rival action substitutions, all 3,200 turn and score observations and 2,387 actionable progress checks matched the referee. The older version had failed three of those tests, including 64 progress mismatches. The strategy weights were preserved. A complete replay of the original 3,200 audit fixtures produced 3200 matching final scoreboards, territory counts and rank outcomes, with zero bot faults. These fixtures had already been used in the original audit, and this replay checks regression after the memory fixes. The original source and evidence remain in the test kit as bot_audited.py and pre_clarification_* records. Server compatibility is still to be checked by the organisers.

**A universal guaranteed outright win is impossible under these rules.** Four teams can independently implement the same proposed strategy. In every resulting game, at most one seat can finish strictly first. Summing the four first-place indicators and averaging over seats gives at most 25% outright wins. Dividing first-place credit among tied leaders gives exactly 25% average credit across four identical copies. This argument includes randomized programs and programs that condition on their seat. It rules out a universal guarantee across all seats and opponent fields. It does not restrict how often a better program can beat a particular weaker field.

“All opponents are rational and use AI” does not specify their programs, risk preferences, tournament objectives or beliefs about the other opponents. Those choices affect the best response. A numerical probability of winning the actual event requires information about that field and the organisers' maps. The measurable result here is performance against an explicitly specified local population.

The most defensible practical method is an iterative population of competing programs. Start with several economic and tactical approaches, test each across maps and seats, create opponents that exploit the leading bot, and retain a candidate that performs well against those responses. Freeze the final candidate before an independent audit. This research followed that process using hand-written algorithms, parameter search and adversarial revisions.

The public repository was inspected at commit `b7e9f1e3c6ddad498e083218304cbe1f6eb1454f`, dated 5 November 2026. It exposed a starter and README. The referee engine, official map generator and actual entrants were unavailable. The local experiments use an independently implemented interpretation of the supplied rulebook, including the confirmed frozen-turn rule and permitted memory. The organisers' referee and later announcements determine official play. [Official starter and interface documentation](https://github.com/RedPokerJoker123/StrategyBot/tree/b7e9f1e3c6ddad498e083218304cbe1f6eb1454f).

**The selected program achieved the following results.**

| Measure | All 3,200 games | 2,880 new-random-map games | 95% map-block interval for new random maps |
| --- | --- | --- | --- |
| Pairwise credit | 67.32% | 67.99% | 65.17% to 70.96% |
| Outright first | 39.81% | 40.73% | 36.49% to 45.21% |
| Fractional first | 39.84% | 40.75% | 36.51% to 45.24% |

The bot won 1,274 games outright. Its 9,600 comparisons comprised 6,461 wins, 3 draws and 3,136 losses. It finished strictly last in 285 games. No participant incurred a bot error or time-limit fallback. Across 256,000 calls, the selected program averaged 0.132 ms and peaked at 33.534 ms on this computer, against the 200 ms turn limit.

The 400-game selection panel gave the cautious adaptive planner 77.33% pairwise credit, 55.75% outright firsts and 82.25% score-based top-two finishes. Its weakest selection lineup still yielded 66.25% pairwise credit. Selection results influenced the choice of program. The independent final audit below faced a harder field that included other finalists.

| Candidate | Games | Pairwise credit | Outright first | Weakest lineup credit |
| --- | --- | --- | --- | --- |
| Adaptive cautious (selected) | 400 | 77.33% | 55.75% | 66.25% |
| Adaptive with higher raid weight | 400 | 76.08% | 56.25% | 63.33% |
| Adaptive, feints disabled | 400 | 75.67% | 54.75% | 63.33% |
| Four-job beam search | 400 | 72.54% | 52.75% | 59.58% |
| Adaptive fortification | 400 | 72.12% | 50.50% | 56.25% |
| Ten-action beam search | 400 | 68.00% | 49.50% | 60.42% |
| Tuned original planner | 400 | 67.50% | 42.50% | 50.00% |
| Cautious original planner | 400 | 63.29% | 36.25% | 55.42% |
| Upgrade-heavy original planner | 400 | 63.17% | 38.50% | 54.17% |
| Low-raid original planner | 400 | 60.92% | 37.00% | 43.75% |
| Fortress policy | 400 | 56.71% | 29.50% | 40.00% |
| Shield-baiting policy | 400 | 51.21% | 25.00% | 22.50% |
| Initial planner | 400 | 50.67% | 32.00% | 25.00% |

Each selection row uses the candidate's designated seat in the same 400 fixtures. When the same program also appeared in opponent seats, those games were included and only its designated seat contributed to that row. This matters for homogeneous lineups and repeated policies. The initial 4,100-game search evaluated 41 parameter configurations. The main selection compared 13 candidates, with two further action-search configurations evaluated separately. The complete records preserve results for weaker and discarded approaches.

The final audit contained 3,200 games. It used 36 new random boards, comprising 12 centre-weighted, 12 irregular and 12 perimeter-heavy boards, plus four fixed boards comprising the rulebook illustration and flat boards valued 1, 2 and 3. Every board faced five opponent lineups in all four candidate seats and all four initial priority-token positions. Opponent order was reproducibly shuffled. The irregular and perimeter-heavy maps deliberately stress assumptions about where valuable cells occur. Their frequency in this suite is a research choice. The official map distribution remains unknown.

| Map group | Games | Pairwise credit | Outright first |
| --- | --- | --- | --- |
| Centre-weighted random | 960 | 70.30% | 44.06% |
| Perimeter-heavy random | 960 | 66.81% | 38.75% |
| Fixed rulebook illustration | 80 | 63.75% | 38.75% |
| Three fixed flat boards | 240 | 60.49% | 29.17% |
| Irregular random | 960 | 66.86% | 39.38% |

| Opponent lineup | Games | Pairwise credit | Outright first |
| --- | --- | --- | --- |
| Fortress + lure + initial planner | 640 | 71.82% | 40.78% |
| Three shield-baiting policies | 640 | 81.30% | 62.81% |
| Action beam + job beam + tuned planner | 640 | 59.06% | 31.41% |
| Three copies of tuned adaptive rival | 640 | 56.46% | 27.66% |
| Adaptive + job beam + lure | 640 | 67.94% | 36.41% |

| Candidate seat | Games | Pairwise credit | Outright first |
| --- | --- | --- | --- |
| 1 | 800 | 70.75% | 42.12% |
| 2 | 800 | 69.19% | 43.12% |
| 3 | 800 | 66.25% | 37.38% |
| 4 | 800 | 63.08% | 36.62% |

| Initial token holder | Games | Pairwise credit | Outright first |
| --- | --- | --- | --- |
| 1 | 800 | 65.90% | 38.75% |
| 2 | 800 | 67.58% | 40.50% |
| 3 | 800 | 67.25% | 39.00% |
| 4 | 800 | 68.54% | 41.00% |

Applying the Round 2 territory tiebreak gives 67.33% pairwise credit and 39.84% strict firsts before seeding. Cell count resolved 2 of the 3 tied pairwise score comparisons. The test kit preserves every breakdown and a second bootstrap that resamples shared seed IDs across generators.

“Pairwise credit” is `(number of rivals beaten + half the number tied) / 3`. An outright first requires exceeding all three scores. Fractional first divides a tie for the highest score among its leaders. Score-based top-two counts fewer than two rivals having a higher score. The last measure omits Round 2's cell-count and Round 1 seeding tiebreakers. The analysis also reports cell-count sensitivity where applicable.

Map, seat and priority rotations produce correlated outcomes. Three comparisons within a game are also correlated. Confidence intervals, where shown, resample entire random-map blocks within each family. Repeating the fixed illustration or a flat board does not create an independent map. These intervals describe the stated synthetic sampling scheme. They provide no calibrated probability of winning the real tournament.

**The rules reward accumulated income and control over time.** A cell's value depends on when it starts paying and how long it survives. For example, capturing a 3-point cell on turn 10 and keeping it at level 1 through turn 80 earns `3 × 71 = 213` points. Capturing it on turn 60 earns 63. A last-turn level-1 raid on a 3-point cell still pays 24 bonus points plus 3 income. Its effect on the former owner's score can also change the ordering.

Let `H` be the number of scoring turns left, including this turn, `d` the travel time and `s` the additional stays needed. If the job succeeds, it completes after `d + s` actions and has `g = H - d - s + 1` paying turns. Jobs with `g <= 0` cannot finish in time. Subject to uninterrupted ownership afterward, the immediate economic gains are as follows.

| Job | Additional stays on arrival | Our gain after completion |
| --- | --- | --- |
| Capture a neutral cell worth `v` | 1 | `v × g` |
| Raid a rival's level-1 cell | 1 | `v × g + 8v` |
| Raid a rival's level-2 cell | 3 | `v × g + 16v` |
| Upgrade our level-1 cell | 3, less valid existing progress | `v × g` additional income |

In a raid, the former owner also loses `L × v × g` relative to keeping its level-`L` cell. A direct score-margin objective against that owner values the swing as `(1 + L) × v × g + 8vL`. These expressions assume the ownership counterfactual holds and omit travel alternatives, later recaptures, shielding and the other two rivals. They give a starting point for evaluating a job. The implemented planner discounts retention, charges for exposure and compares alternative routes.

An available neutral 3-point cell one move away takes two actions to capture. Upgrading the current owned 3-point cell takes three stays before existing progress. The capture starts paying earlier, while the upgrade may protect an important holding by making later theft require three stays. Conversely, upgrading the current 3-point cell can outperform spending several actions collecting distant 1-point cells. A rigid rule to expand forever or upgrade everything misses these cases.

The selected bot evaluates every reachable capture or upgrade, then considers a second job for the leading first jobs. It recomputes after every actual turn. Its route search respects currently occupied cells and checks `legal_actions`. Its capture targets exclude rival homes. Future occupancy and retention are approximations. The program estimates the value of denial using projected score gaps, giving more weight to rivals whose ordering is likely to matter. That is an economic proxy for placement.

The frozen weights are `UPGRADE_WEIGHT = 2.25`, `RAID_WEIGHT = 0.99`, `DEFENSE_WEIGHT = 1.0`, `ROUTE_WEIGHT = 0.5` and `RISK_WEIGHT = 4.0`. These values were selected empirically. The upgrade multiplier captures benefits and modelling errors beyond immediate income. The risk multiplier charges more for exposed raids. They are tuning constants, without a mathematical optimality certificate.

**Shields create a simultaneous tactical decision.** Entering a rival's cell is safe from that owner's shield for the arrival turn, because arrival does not count as staying. On a later stay, a shield can reset the raid and freeze the attacker for two subsequent turns. A departure evades that catch. A blocked departure counts as staying and can still be caught. A shield that catches only already-frozen rivals backfires. One shield can catch several eligible rivals on the owner's holdings.

Under the confirmed rule, frozen turns give no capture or upgrade progress. A defender can interrupt a level-2 raid at turn `t`, deny progress on `t+1` and `t+2`, allow progress on `t+3` and `t+4`, and shield again on `t+5` before the third stay completes. A patient attacker can remain stuck in that cycle. The owner's shield costs development too, so both players must consider their other alternatives. The separate freeze-progress sensitivity run is a historical counterfactual and does not represent the confirmed competition rule.

An attacker can instead depart when a shield is likely. If the owner catches nobody, the owner freezes and has four turns of cooldown. A productive move to another nearby target can exploit that window. Repeatedly retreating without gaining anything can also waste the attacker's game. The selected bot learns observed defensive reactions and only considers a feint when a nearby alternative has sufficient value.

The defender has the complementary problem. Always shielding the moment an intruder appears invites a retreat. Always allowing the first stay loses level-1 holdings. The bot tracks each invader's observed persistence, including retreats during shield opportunities. It delays some defensive reactions on upgraded land while watching the raid's inferred progress, and compares expected protection and disruption with its own lost development and backfire cost.

A local two-choice approximation explains why mixed strategies can matter. Suppose an attacker chooses stay or escape, and a defender chooses shield or develop. If a successful unshielded stay is worth `A` to the attacker and a caught stay costs `F`, with escape normalized to zero, attacker indifference requires shield probability `A / (A + F)`. Both values depend on the board, remaining turns and alternatives. This calculation illustrates the interaction. The delivered program uses learned likelihoods and deterministic value comparisons. Its behaviour can still be predicted and countered by a sufficiently informed opponent.

The delivered bot also contains a narrow final-turn improvement. If its planned action is STAY, it knows the game is on turn 80, that stay cannot complete its own capture or upgrade, and a rival threatens an ordinary owned cell, it can shield. A backfire has no later scoring turn to consume. Replacing STAY preserves its location and movement contests. Its own stay would add no score, while protecting holdings can only preserve its income and deny rivals' capture income or raid bonuses. Thus SHIELD weakly improves its score margins in this situation. The argument requires correctly known progress and turn under the main freeze interpretation. Tests corroborated it on 32 constructed positions covering 4,533 simultaneous action profiles, with zero worsened score margins. Under the alternative frozen-progress interpretation, the main bot's progress estimate can be wrong, so that guarantee is conditional too. The replacement does not solve the full final-turn game or establish a large increase in tournament wins.

**The actual interface constrains what the program can know.** The README specifies an 8 × 8 list of rows. The starter's shorter comment calls the board a list of cells. The implementation accepts the documented two-dimensional representation and also tolerates a flat 64-cell list. Only `board`, `bot_id`, `is_priority_token` and `legal_actions` are used as state attributes. Each cell supplies occupant, owner, upgraded status, home status, base points and the occupant's frozen status.

Turn number, scores, partial progress, rival legal actions and rival cooldown timers are absent from the documented observation. The bot reconstructs its turn counter, score history and own progress using module memory. It infers rival shield use from observable freezes and ownership changes. A rival's shield can be ambiguous when several effects coincide, so the inferred cooldown is a model. It observes only whether it personally has priority, so the current path model treats some other priority relations conservatively.

The organisers confirmed that the program may retain information between turns, with recovery from failed or blocked actions left to the team. The updated bot reads actual positions, ownership, upgrades, frozen status and shield availability to reconcile its history. It uses a complete 80-turn boundary or irreversible board evidence to recognize a new starting board. Simply returning to the four original positions during an opening preserves the current game clock. Exact remaining-turn decisions still require continuous observations from the start. A lost interpreter before history is committed, a missing callback, or an early reset to an indistinguishable board cannot always be reconstructed from the documented fields. A fresh midgame import retains legal fallback decisions and suppresses the exact final-turn override until the start is known. The main tournament measurements use permitted persistent memory isolated for each bot and game.

| Matched execution condition | Games | Pairwise credit | Outright first |
| --- | --- | --- | --- |
| Persistent memory | 16 | 77.08% | 9/16 |
| Fresh module every call | 16 | 50.00% | 5/16 |
| Main freeze model, sensitivity subset | 160 | 65.21% | 38.75% |
| Frozen stays accrue progress, same subset | 160 | 45.31% | 17.50% |

These are two separate matched experiments. The 16-game lifecycle comparison uses the same fixtures on each side. The 160-game rule sensitivity uses every twentieth final-audit fixture. It fixes the initial token to seat 1, covers four fixed lineup/seat combinations and omits the fifth lineup. The freeze comparison used the original audited source and establishes dependence within that restricted coverage. The organiser answer has since confirmed the no-progress rule. The alternate-progress results remain historical experiments.

The delivered source passed standard-library, signature, documented-field, legal-action and input-purity checks. Across 44 validation games, there were zero exceptions, illegal returns, input mutations or deadline misses. On the persistent samples, all reconstructed own turn and score vectors matched the referee, with 1,786 actionable progress checks. The fresh-module sample included 1,280 module reloads and peaked at 6.288 ms including import and action.

The local referee passes 23 regression tests. The terminal rule passes its 4,533-profile check. The independent holdout audit verified all 40 board values, distinct fixtures, source hashes and absence of random-map overlap with development.

Before the clarification, six configurations were screened under the counterfactual rule that frozen stays earn progress. A separate profile was then compared with the original main bot on six new random maps, five lineups, all seats and all initial tokens. In 480 fixtures each, that profile earned 63.40% pairwise credit and 41.25% outright wins, against 48.26% and 23.12% for the original main bot. Those opponents were not independently retuned for the counterfactual. Both profiles and raw results are retained for provenance. The confirmed rules select the updated main bot.py.

The referee tests cover moves into initially occupied cells, swaps, contested entries, owner preference, every token rotation, neutral captures, both raid levels, capture-time income, upgrade progress, immutable homes, progress resets, shield arrival/departure timing, blocked departures, multiple catches, frozen-rival backfires, two frozen turns and four full cooldown turns. They include 2,000 random legal turns for invariants. A local referee passing tests still needs comparison with the official server.

**Tournament stage changes what success means.** Round 1 compares each bot with all three rivals. With equal scores it awards half credit. Maximizing expected pairwise standing is therefore the primary selection objective here. A large point margin over the last-place rival can be less useful than crossing one nearby rival's score. Elo updates also depend on ratings and scheduling, which the organisers have not specified in enough detail to reproduce an official leaderboard.

Pool games award 3, 2, 1 and 0 points, with cell count breaking equal game scores before shared pool places. Semi-finals advance the top two. The final decides prizes by finishing place. An exact semi-final policy should sometimes trade first-place upside for a higher chance of finishing second. A final policy aimed at first prize may accept greater risk when it is behind. The supplied program was chosen for Round 1 pairwise performance and can play the shared rules in Round 2. It has no stage-information input and no verified separate stage-optimal policy.

Hardware introduces an additional failure model. A fault attributed to the team can create three frozen turns per hand placement. Battery condition, mechanical assembly, calibration and consistent cell transitions therefore affect results. The kit and measured movement-failure probabilities were unavailable, so no calibrated hardware-risk term was invented. Before the on-campus lock, the useful next experiment is measured complete 80-turn robot games, including turns, long routes, low battery and shield/freeze signals. Any preference for fewer physical moves should be based on those measurements and retested with the same software audit.

**A guaranteed score is possible for a deliberately conservative policy.** Stay at home for turns 1 to 3, move to the better orthogonally adjacent cell on turn 4, then stay there through turn 80. The nearby cell is captured before another corner can reach it. Occupancy prevents any rival entering it afterward. The home is also permanently protected. If the home is worth `h` and the selected neighbour is worth `v`, the total is exactly `158h + 149v`, hence at least 307 points in an ordinary software game. The neighbouring cell pays on turns 5 to 80 and upgrades on turn 8. Eighty pursuit tests matched this formula. This guarantee assumes successful callbacks and the ordinary start, with no additional hardware penalties. It belongs to the conservative parking policy in the test kit. The selected competitive bot pursues a different empirical objective.

**The strongest continuing research method is a population of counter-strategies.** Policy-Space Response Oracles trains or constructs responses against a mixture of existing policies, expands the population and recomputes its strategy assessment. Its purpose here is to expose narrow strengths and recurring weaknesses. The original framework explicitly studies overfitting to training opponents and uses empirical game analysis. This study uses a finite code population and approximate responses. It did not run a complete equilibrium solver. [Lanctot and colleagues, 2017](https://papers.nips.cc/paper_files/paper/2017/file/3323fe11e9595c09af38fe67567a9394-Paper.pdf).

Code-Space Response Oracles applies this idea to programs generated and refined by language models. It supports the practical workflow of producing interpretable policies, measuring them and giving the next response generator concrete failures. Its reported experiments are repeated rock-paper-scissors and Leduc poker. Its results establish a research approach, without predicting a Zone Rush percentage. [Hennes and colleagues, 2026](https://arxiv.org/abs/2603.10098).

Simultaneous-move search must keep current choices hidden from the other players during evaluation. Ordinary sequential search can give one simulated player information it lacks in the real game. Research on simultaneous MCTS compares regret matching and outcome sampling with UCT and explains why mixing actions matters. This work informs the tactical models and future improvements. Its two-player equilibrium results do not establish a four-player guarantee here. [Lanctot, Lisý and Winands, 2014](https://mlanctot.info/files/papers/wcg13-smmcts.pdf).

Multiplayer equilibrium also presents an equilibrium-selection problem. The Pluribus research explains why the familiar two-player zero-sum safety properties and CFR convergence claims do not automatically extend to multiplayer play. It combines offline self-play and online search and establishes strength empirically. This is a reason to keep testing against independent counter-strategies and to avoid equating “uses CFR” with a guaranteed win. [Brown and Sandholm, 2019](https://noambrown.github.io/papers/19-Science-Superhuman.pdf).

A complete next cycle starts with the server-compatibility check the organisers offered, using the updated `bot.py`. Official gameplay testing is reserved for the hardware stage, so local simulations remain the available method for comparing strategies beforehand. If official transition logs later become available, compare them with the local edge cases. New opponent designs should include responses to predictable routes, pressure on the leader, delayed shields, coordinated-looking behaviour arising from independent incentives, and changes of strategy during a match. No communication or agreement between competing teams is needed or permitted. Evaluate responses against the whole archive so that defeating one counter does not reintroduce an older failure.

Use separate development, selection and final audit sets after any new change. Increase the diversity of randomly generated legal maps and independent opponent authors before increasing repeated copies of the same fixture. Candidate randomization, deeper simultaneous search, learned value functions or reinforcement learning become useful when they beat the frozen baseline on that process. They require their own measured performance and runtime. The single-file and standard-library submission constraints allow offline training followed by a compact exported policy, but that architecture was not trained or verified in this study.

Literal testing of every possible strategy is infeasible. Even restricting each bot to its own disjoint home-and-neighbour pair permits at least `2^320`, about `2.14 × 10^96`, legal joint action histories over 80 turns. Different histories can merge into the same state, and symbolic arguments can eliminate classes of strategies. The count explains why a finite experiment suite must be described by its coverage and assumptions. This work provides an executable contender and a reproducible way to challenge it, with the remaining official validation clearly identified.

The rulebook gives the software deadline as Wednesday, 11 November 2026 at 11:59 pm UAE time and the campus round as Saturday, 14 November 2026. Keep the submission named `bot.py`, preserve `act(state)`, use only the standard library, and return an action from the supplied legal list within 200 ms, or 2 seconds on the first turn. Submit the team's name and its repository link through the official submission form. Request the offered compatibility check using this file and follow the organisers' latest upload instructions. The test kit's other programs are for local evaluation. The competition entry remains one file in the team's own repository.
