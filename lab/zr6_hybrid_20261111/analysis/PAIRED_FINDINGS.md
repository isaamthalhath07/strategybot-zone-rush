# Why Adaptive Raider zr6 outscored the verified 5bc bot

Across 500 paired fixtures, zr6 outscored 0.408 more rivals per game than 5bc (95% map-clustered interval 0.222 to 0.585). It placed outright first in 250 of 500 games, versus 156 of 500 for 5bc. The largest visible difference was earlier investment in three-point squares followed by raids that took nearby upgraded squares while their defender's Shield was on cooldown. The comparison changes the whole bot, so it estimates their overall difference on these fixtures. The tactic counts below describe the resulting games.

## Score and territory

| Mean per game | zr6 | 5bc | Difference |
|---|---:|---:|---:|
| Final score | 2,599.180 | 2,570.392 | +28.788 |
| Three-point-square income | 1,358.352 | 1,107.162 | +251.190 |
| Other square income | 1,131.356 | 1,427.070 | −295.714 |
| Raid bonuses | 109.472 | 36.160 | +73.312 |
| Combined score of three rivals | 7,382.058 | 7,566.320 | −184.262 |

The income and bonus differences reconcile exactly to the final-score difference. On average the three opponents earned 212.342 fewer income points and 28.080 more raid-bonus points per game under zr6. The focal bot's average margin over an individual rival improved by 90.209 points. In 35 matched fixtures zr6 outscored more rivals even while its own raw score fell. Field E is another example of why raw points miss the objective. Its mean final score fell 18.68, while rivals outscored increased by 0.135.

By turn 20 zr6 owned 2.502 three-point squares and had upgraded 2.244 per game, versus 2.228 and 1.878 for 5bc. It had 4.642 fewer score points at that point. The median first claim and upgrade were turns 7 and 10 for zr6, versus 8 and 11 for 5bc, among games with the event. Two of the 25 maps had no three-point squares. On the remaining 23 maps, zr6 made a neutral three-point claim in 460/460 games and 5bc in 459/460. Nearly every neutral three-point claim with twenty remaining turns held for the next twenty turns (1,626/1,629 versus 1,443/1,444).

| Turns | zr6 three-point income per game | 5bc | zr6 upgraded three-point raids | 5bc |
|---|---:|---:|---:|---:|
| 1–20 | 116.580 | 94.002 | 0 | 0 |
| 21–40 | 359.520 | 319.620 | 30 | 2 |
| 41–60 | 410.772 | 345.330 | 230 | 13 |
| 61–80 | 471.480 | 348.210 | 487 | 101 |

zr6 scored 567,303 income from three-point squares in the central 4×4 across its 500 games, versus 430,011 for 5bc. It finished with 4.264 three-point squares per game versus 2.942. Its first upgraded three-point raid came at median turn 60 among 411 games with a raid, versus turn 73 among 99. It held 248 of 260 three-point captures with a twenty-turn observation window continuously for that period, versus 15 of 15 for 5bc. The two retention groups differ in timing and size. Across all 500 games the bots made 1,760 and 956 raids of any value, including 747 and 116 on upgraded three-point squares.

## The two-stay juke usually changes targets

A physical escape here means the bot successfully moved off an upgraded rival square while that rival cast Shield and the mover remained unfrozen. The opponent can still catch a different player. The four-turn capture counts only use escapes with all four cooldown turns on tape.

| Outcome after two banked stays | zr6 | 5bc |
|---|---:|---:|
| Physical escapes | 695 | 77 |
| Stepped onto another cell of the same defender | 660 | 28 |
| Defender backfired | 616 | 61 |
| Escapes with all four cooldown turns observable | 642 | 58 |
| Window includes a capture of a different square from that defender | 557 | 17 |
| Window includes a capture of a different three-point square from that defender | 497 | 7 |
| Captured the landing square during the window | 555 | 13 |
| Captured landing square with consecutive stays, without leaving it | 531 | 13 |
| Captured upgraded three-point landing square this way | 472 | 7 |
| Immediate return and three fresh stays captured the original square | 24 | 18 |

All phases combined, zr6 had 738 physical escapes and 27 immediate original-square completions. The 5bc counts were 105 and 19. There were 502 distinct captures of a different three-point square from the shielding defender in zr6's full cooldown windows versus 15 for 5bc. Distinct here means one event per game, turn and square. This captures the main visible mechanism missed by a metric that only looks for returns to the bait square.

The branch code explains the path selection. zr6 estimates Shield probabilities by progress context and learns them from encounters involving any player. It compares staying with sidestepping, prefers a capturable adjacent square owned by the same defender, and reroutes after the new public board arrives. A successful move escapes even across two of that defender's squares. When the landing square is upgraded, three consecutive stays can claim it before the defender's next Shield becomes legal. The defender can still physically contest the route and another opponent can seize exposed cells. The recorded follow-up alone cannot establish what would have happened had the attacker stayed.

## Shield timing and freeze cost

zr6 cast 923 Shields and backfired 143 times (15.5%). 5bc cast 869 and backfired 222 times (25.5%). zr6 spent 956 frozen turns versus 1,523. This includes freezes by opponents and backfires. zr6 caught 603 opponents on upgraded tiles versus 366.

When Shield was available and the most urgent non-home intruder was one stay short of an immediate upgraded capture threat, zr6 cast on 187/410 opportunities (45.6%) versus 27/234 (11.5%). When at least one eligible intruder could take a cell that turn, zr6 cast on 736/2,020 (36.4%) versus 803/1,284 (62.5%). These situations occurred at different rates and on different boards. The comparison supports earlier and more selective Shield timing as observed behavior. It cannot assign the lower freeze count or the rank gain to one defense change.

## Two paired trajectories

**Early central claim.** Map index 18, field B, seat 4, pair 6f29ebc38d46. All four seats took identical actions through turn 13. From C5 on turn 14, zr6 moved east to neutral D5, a central three-point cell. It claimed D5 on turn 15 and upgraded it on turn 18. 5bc instead went west to B5, claimed that two-point square, then claimed the edge three-point square A5 on turn 17. zr6 finished with 2,828 points and outscored two rivals, versus 2,880 points and one rival for 5bc. Even a case with lower final score can reflect stronger relative play.

**Two stays, adjacent pivot, upgraded capture.** Map index 3, field E, seat 1, pair 5619e5af0200. All four seats took identical actions through turn 62. On turn 63 zr6 went from D8 to E8 while 5bc went to D7. zr6 claimed E8, moved to rival seat 3's upgraded E7, and stayed there on turns 66–67. On turn 68 seat 3 cast Shield and zr6 moved north onto that rival's upgraded three-point E6. The defender backfired. zr6 stayed on E6 on turns 69–71, took it at level 1, and earned a 48-point raid bonus. In the 5bc trajectory, seat 4 caught 5bc twice at D7, on turns 66 and 72. zr6 outscored two rivals with 2,828 points versus one with 2,713 for 5bc. The games diverged at turn 63, so their turn-68 positions and opponents' actions were already different.

## Implications for the hybrid

Keep the opening valuation of early three-point income and the late search for upgraded raid targets. Evaluate the juke and its landing job together. The important opportunity is a nearby enemy-owned landing square the attacker can finish during cooldown, especially when the raid denies a rival's recurring income. A same-square return remains a valid option, but would omit most of the successful zr6 paths in this panel. Preserve alternative routes and discount land that can be contested or recaptured. Compare a hybrid with exact zr6 under new matched fixtures to establish any improvement. The results here do not isolate the hazard planner, Shield model, destination preference or early Shield choice.

The analysis reads the 1,000 admitted originals from one map generator and five fixed opponent fields. It uses their 25 map clusters as the scope of the published interval. No new actors or referee steps ran. The tape digest and the phase, timing, defense, escape and example details are in the paired evidence.

- [Matched benchmark statistics](../results/initial_comparison.json)
- [Detailed paired tape evidence](paired_tape_evidence.json)
- [Pinned zr6 source, sidestep and raid decisions](https://github.com/isaamthalhath07/strategybot-zone-rush/blob/77c867ffff4df39db20d08993ea05ba121441f36/bot.py#L629-L669)
- [Pinned zr6 source, Shield and raid expected values](https://github.com/isaamthalhath07/strategybot-zone-rush/blob/77c867ffff4df39db20d08993ea05ba121441f36/bot.py#L847-L947)
