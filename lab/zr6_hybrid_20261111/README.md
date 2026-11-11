# zr6 hybrid validation

Adaptive Raider zr6 led the verified 5bc bot by **0.409 rivals outscored per game** on 20 fresh maps. Both hybrids produced small estimated gains over zr6 with intervals spanning zero. The submission is the exact [zr6 source](https://github.com/isaamthalhath07/strategybot-zone-rush/blob/77c867ffff4df39db20d08993ea05ba121441f36/bot.py).

| Comparison | Paired gain | 95% map-clustered interval |
|---|---:|---:|
| zr6 vs. 5bc | +0.409 | +0.202 to +0.602 |
| zr6 vs. zr6 with feints disabled | +0.352 | +0.216 to +0.500 |
| Cooldown continuation vs. zr6 | +0.003 | -0.017 to +0.020 |
| Cooldown continuation and route selection vs. zr6 | +0.008 | -0.038 to +0.069 |

With feints enabled, zr6 captured 910 enemy three-point squares across 640 games. The feint-disabled control captured 196 while making slightly more total raids. The switch controls both raid planning and sidestep choices. The original replay study shows how zr6 uses neighboring squares owned by the shielding defender to complete valuable captures during cooldown.

- [Replay findings and paired examples](analysis/PAIRED_FINDINGS.md)
- [Hybrid designs and source fingerprints](candidates/DESIGN.md)
- [Development comparison and diagnostics](results/development_comparison.json)
- [Frozen test protocol](results/protocol.json)
- [Map-level outcomes](results/map_outcomes.json)
- [Original evidence hashes](provenance.json)

The screen ran 3,200 full games and 3,200 fresh policy replays. Both referees agreed on every turn. Each of the five arms used the same 640 fixtures. The nomination rule required a gain of at least +0.020 over zr6. Neither hybrid qualified for the separate confirmation.

The two candidate files are standalone experimental policies. The development control differs from zr6 by the one feints setting. Map outcomes retain integer scores and paired endpoints for review. Full action tapes and the workspace-specific runtime archive are stored locally.
