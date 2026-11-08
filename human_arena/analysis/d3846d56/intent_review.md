# Opponent-intent review: match d3846d56

Reviewed the uploaded 80-turn transcript as data and the exact selected evolved policy at `human_arena/bot_snapshots/0796039f42f0113d7c4f51b2f8e1409835f2c519/outputs/bot.py`, SHA-256 `1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca`. No game, policy or interface was changed. The human, seat 1, won 2,378 points against 1,924 / 2,179 / 1,615.

## What the actual match establishes

The bots did not all ignore the centre. The four base-3 squares were split as follows:

| Player | Square | Claimed | Upgraded | Actual income through turn 80 |
|---|---|---:|---:|---:|
| Human | D4 | 7 | 10 | 435 |
| Human | D5 | 12 | 15 | 405 |
| AI 2 | E4 | 10 | 13 | 417 |
| AI 3 | E5 | 10 | 13 | 417 |

The human received 840 points from two central squares. AI 2 and AI 3 received 834 combined from the other two. The important imbalance is that one player held two, two rivals held one each, and AI 4 held none. This is not evidence that an edge-only policy defeated a centre-only policy.

The human subsequently developed a connected western group of valuable base-2 squares. The first current-score lead occurred after turn 42: 718 against 716 / 711 / 630, with income 35 against 30 / 29 / 24. This followed many turns of development, rather than an immediate win from arriving centrally.

AI 4's conspicuous failure was its later raid cycle. Its last productive ownership improvement before the cycle was the F4 upgrade on turn 36. It made no claim, completed raid or upgrade during turns 37–62 inclusive. It was shielded on E4 on turns 39 and 44, on E5 on turn 50, and on the human's D4 on turn 57. Those freezes forced eight subsequent stays. Its next productive claim was A4 on turn 63. Moving toward the centre therefore happened; repeated unsuccessful commitments to defended holdings were the problem in that phase.

## When the human's plan was observable

The first several moves were a staircase toward D4, with no peripheral claims. By the observation before turn 5, the human was at C3, two moves from D4. This was evidence of a central opening, although not proof of an exact next action.

Before turn 7 the human occupied neutral D4. Before turn 8, the claim was visible. Before turn 9, one post-capture stay was visible; before turn 10, two post-capture stays were visible. Given the published three-stay upgrade rule, another stay would complete the upgrade. A controller can infer that from public observations without reading the transcript's private progress counter.

After the turn-10 upgrade, D5 was the only adjacent neutral base-3 square. E4 was occupied by AI 2, while C4 and D3 were only base 2. D5 was a reasonable next-target hypothesis, not a guaranteed human action. The human moved there on turn 11, claimed on turn 12 and upgraded on turn 15.

A concrete public-information intervention window existed before turn 10. AI 4 occupied D7. Moving north to D6 on turn 10 and north to D5 on turn 11 would have contested the human's actual turn-11 entry. Turn 11's token was held by seat 3, so the priority order 3→4→1→2 would favor AI 4 over the human on this neutral square. Token timing can be inferred from prior priority observations; it need not be obtained from hidden referee state. AI 4 instead claimed D7 on turn 10 and upgraded it on turn 13.

This is a testable alternative, not a proof that the intervention wins the game. A human encountering a blocked entry would adapt, and the other bots could change their plans. Replaying the human's entire recorded future after forcing this intervention is only a fixed-action diagnostic.

## What the selected policy forecasts

The selected configuration has depth 2 (`bot.py:73`) and breadth 7 (`bot.py:68`). These mean two of its own economic jobs, with seven leading first jobs considered. They do not mean two turns of simultaneous four-player search.

At `bot.py:282–286`, opponent positions become occupied squares and a nearest-rival Manhattan-distance field. At `bot.py:288–293`, estimated scores plus at most 18 turns of current income determine a modest denial coefficient. At `bot.py:345–364`, it chooses its own first job and an attractive next job. It does not branch over rivals' next targets, forecast their next upgrades, reserve their likely routes, or recompute future board ownership from their decisions.

There is real opponent awareness, but it is narrower than general plan prediction:

- `_observe`, especially lines 155–170, learns whether an intruder stays on the bot's land and how often a defender shields. It does not learn a player's general claim-then-upgrade habit from that player staying on their own territory.
- `exposure` at lines 294–295 and raid penalties at 325–332 model an average defensive response. They are not a conditional model of a defender waiting for a raid's decisive stay.
- The shielding logic at lines 413–427 uses observed intruder persistence when defending its own land. That is useful tactical anticipation, but does not supply an offensive model of the other player's next economic target.

The human's upgrade pattern was therefore observable and useful, but the policy has no general mechanism for converting it into a prediction that D5 will be the next contested neutral objective.

## Specific model blind spots

### Neutral preemption receives no denial credit

The neutral-claim reward is simply `v * life` at line 322. Denial appears only in the reward for taking an already rival-owned square at line 324. Occupying D5 before the human can claim and upgrade it therefore receives its own economic value but no explicit credit for preventing the predicted human development. A planned future rival claim and an unclaimed square nobody intends to visit are treated alike except for current-distance pressure.

### Post-raid development is valued as if the raid succeeds

The first raid's reward and effort are penalized for defensive risk at lines 325–332. But the continuation at lines 360–364 adds the next own upgrade on the captured square without applying the raid's success probability or accounting for a failed raid's freeze and progress reset. The route multiplier at lines 376–379 then adds that continuation to the penalized first-job rate.

The root agent's exact replay instrumentation illustrates this on turn 42 for AI 4: E4's raid first-job rate was 8.7697, below neutral C2's 13.7913. E4 nevertheless won the composite comparison, 58.4442 against 43.8052, because its presumed post-capture upgrade supplied a next-job rate of 83.3532 and an additive continuation of 49.6745. These figures come from instrumented original decisions, not a claim that a different route is guaranteed to win.

This is a more concrete explanation for the failed commitment than saying the bot cannot see the human or never values the centre. Risk can suppress the initial raid while an unconditional, never-realized upgrade keeps the same target attractive.

### Persistent raiding can be blocked repeatedly

A shield resets the three-stay upgraded-cell raid, freezes the attacker for two turns and then leaves a four-turn cooldown. Two forced frozen turns followed by three new work stays allow a defender to recharge before the next capture attempt. A persistent attacker therefore cannot assume that one shield merely imposes a finite delay before eventual success. The transcript's E4 cycle demonstrates this renewal problem. A soft average penalty lacks an explicit model of that conditional repeated response.

### Later job rewards are only approximate

Secondary jobs reuse `reward2` constructed from the current position and current clock. The feasibility test includes the first job's cost, but their income reward is not generally recomputed at the delayed completion time (`bot.py:347–359`). `route_delay = 0.02` is an empirical discount, not an exact economic simulation. This can favor an appealing cluster without correctly valuing when its income becomes available.

## Which centre avoidance is defensible

The human reached D4 along a shortest six-move route. Once that race was clearly visible, no rival could simply teleport into the square before the turn-7 claim. Occupancy then prevented entry while the human completed the upgrade. Farming another reachable square was often a sensible immediate response.

The income-retention heuristic at line 313 is `40.67114 + min(5, nearest_rival_distance) * 3.52153`. A square one move from a rival receives at most about 44.19 modeled income turns, against about 58.28 at distance five or more. Early in the game this deliberately favors less contested holdings. It does not forbid the centre: at equal work cost, a base-3 square with a 44.19-turn lifetime still has greater income reward than a base-2 square with a 58.28-turn lifetime.

That retention cap does not explain the late raid cycle. Valid reachable target cells are not occupied by a rival, so their nearest-rival distance is at least one. From turn 37, at most 44 turns remain, and all feasible income lifetimes are already below the minimum 44.19-turn cap. The cap is then inactive. Later choices must be explained by the remaining clock, raid-risk and upgrade weighting, continuation scoring, and inferred state.

## Fair quantitative tests

1. **Forecast test, using only public history:** freeze a predictor before each decision and record probabilities for the human's next move, upgrade completion and next neutral target. Score those predictions against later observations. Compare current-distance heuristics with a public-history model of an ongoing upgrade. Do not let the predictor read the next logged action, hidden progress or future board.
2. **Causal branch test:** compare the original policy with a public-intent-aware variant on fresh, paired maps and seats, including responsive central farmers, peripheral farmers, defenders and baiters. Measure pairwise results, not just the number of central squares owned. The turn-10 D5 intervention is a useful illustrative branch, but a fixed continuation of this one human transcript is insufficient validation.
3. **Continuation-risk ablation:** condition or remove the presumed post-raid upgrade value, then test against the unchanged original policy and unfamiliar opponents. This targets a demonstrated scoring mechanism. It does not justify shipping a modified policy before held-out confirmation.

The supported conclusion is that the bot sees the complete board, values central holdings, and has tactical opponent statistics, but does not explicitly forecast rival economic plans. In this match, profitable human consolidation and concrete failures in the bots' defensive-risk/continuation reasoning matter more than a simple centre-versus-edge rule. One human win cannot establish a universally best opening or a globally weak policy.
