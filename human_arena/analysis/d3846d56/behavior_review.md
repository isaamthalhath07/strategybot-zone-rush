# Independent match behavior review

Verified all 80 physical transitions and 320 public observations against the hash-pinned local referee. All 240 AI actions reproduce from the exact recorded policy.

| Seat | Score | Recurring income | Raid bonus | End income | Cells / upgraded | Frozen turns |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 2378 | 2378 | 0 | 50 | 14 / 14 | 0 |
| 2 | 1924 | 1908 | 16 | 33 | 11 / 8 | 6 |
| 3 | 2179 | 2099 | 80 | 44 | 15 / 12 | 0 |
| 4 | 1615 | 1599 | 16 | 32 | 13 / 9 | 8 |

## Persistent observed weaknesses

1. **Seat 4 remained in a shield/raid trap.** It was caught on E4 at turns 39 and 44, E5 at turn 50, and D4 at turn 57. Eight subsequent turns were forced STAYs. It completed no capture or upgrade during turns 37–62, while recurring income remained 24. After a catch, a four-turn shield cooldown minus two frozen turns leaves only two safe active STAYs, insufficient for a three-STAY upgraded-cell raid before the defender can shield again. This does not make raids impossible against every opponent: the defender can choose another action. It does make persistent commitment exploitable by a defender willing to repeat.

2. **The policy falsely inferred a human shield at turn 54.** Seat 2 actually shielded and backfired on the human's C2; the human stayed and upgraded C3. At turns 55–57 all three AI copies inferred human cooldowns 4, 3, 2, while the true cooldown was zero. The upgrade is visible evidence that the human could not have shielded at turn 54. This avoidable state-reconstruction error fed overconfident attacks into the real human SHIELD at turn 57. Seat 2 also missed its own real cooldown following its backfire.

3. **Seat 2 spent shields before a raid could complete, with competing scoring work available.** Its turn-54 shield missed seat 4 as it left E4, while seat 2 could capture the ordinary human C2 with STAY. Its turn-75 shield also missed as seat 3 moved from E2 to D2; the cooldown then covered the turn-78 upgraded D2 capture. These are failures on this realized path, not proofs that every shield was irrational under uncertainty.

4. **Contest handling cost seat 2 tempo.** At turn 49 it lost C2 to the human by token priority; at turn 51 it lost C3 to the human's ownership priority. The intervening D2–D3–D2 return at turns 50–52 completed no work. This is a short failed-contest detour, not evidence of pervasive perpetual oscillation.

5. **The human converted safe recurring income more consistently.** The human finished with all 14 owned cells upgraded and 50 income/turn. Seat 4 had 13 cells but only 9 upgraded and 32 income/turn. Income growth, rather than an AI execution fault or exceptional raid bounty, explains the bulk of the score gap.

## Important strengths and distinctions

Seat 3 was not trapped or frozen at all. Its turn-75 move from E2 to D2 successfully escaped seat 2's simultaneous SHIELD, then captured upgraded D2 on turn 78 during the cooldown. Its three raids earned 80 points. It still lost by 199 because recurring income was 279 behind the human, partly offset by those bonuses. This match does not establish that each of seat 3's choices was a mistake. Its successful feint also isolates the problematic progress-sensitive commitment in seat 4: feinting is allowed when progress is zero, but disabled after progress has been banked.

Seat 2's shields at turns 39 and 44 actually caught seat 4 and protected a valuable upgraded holding. Those are different from its empty shields at turns 54 and 75. A blanket instruction to stop shielding would discard a real defensive strength. The failure is in conditional timing, opportunity cost, observation attribution, and the response to a defender who repeatedly shields.

## What this match does not establish

A blanket 'rush the center earlier' prescription is unsupported. Seat 4 led the human 39–25 at turn 10 under its actual opening. A legal six-move direct D5 rush followed by claim and upgrade scores only 25 by turn 10 with other requests fixed, versus its actual 39. It contests a useful future cell, but sacrifices early income; the rest of that different game requires a policy-level comparison. There were no ordinary occupied-cell blocked moves and no immediate consecutive movement reversals in the AI traces. Empty late STAYs are not automatically errors when no scoring action can finish before turn 80.

## Bounded conditional counterfactuals

All following comparisons hold other realized requests fixed, enforcing legality under the modified state. They use hindsight and do not forecast adaptive opponents or prove a stronger deployable policy.

- **seat2 capture instead of premature shield54**, turns 54–80: score differences [human, seat 2, seat 3, seat 4] = `[-12, 24, 0, 0]`.
- **seat2 wait75 shield completion78**, turns 75–80: score differences [human, seat 2, seat 3, seat 4] = `[0, 10, -38, 0]`.
- **seat4 feint44 then capture E3 47**, turns 44–47: score differences [human, seat 2, seat 3, seat 4] = `[0, -6, 0, 34]`.
- **seat4 naive center rush opening**, turns 1–10: score differences [human, seat 2, seat 3, seat 4] = `[0, 0, 0, -14]`.

Raw per-seat counts, event coordinates, freeze turns, cooldown mismatches, milestone states and legal counterfactual event traces are preserved in behavior_review.json. Exact full-game and remembered-belief verification is local to the recorded referee/policy versions, not official-server validation.
