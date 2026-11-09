# Complete admitted GEN1 and GEN2 review

**The fixed goal extension has not demonstrated a strength benefit.** GEN1 Goal−f5 is−0.0200195 pairwise points, unadjusted95% [−0.0786133,0.0400391], descriptive Bonferroni 28[−0.1103516,0.0791016]. It could be meaningfully helpful or harmful within that uncertainty. This is neither a positive result nor equivalence. Goal beating e8 does not credit the extension: its unchanged f5 control also beats e8, with a larger point effect.

Only the root-authorized complete [GEN1 report](../.cache/deadline/campaign_20261109_10h_001/train_001/report.json) and [GEN2 report](../.cache/deadline/campaign_20261109_10h_001/train_002/report.json), plus already frozen source semantics, were read. GEN3 and incomplete architecture results were not read. No runtime, key, game, callback, GPU or additional strength evaluation was used.

## Provenance and interpretation

Each generation has 16 fresh disjoint maps, 8 policies, 64 complete field/seat/token conditions per policy/map, 8,192 original matches and 2,621,440 fresh replay callbacks, with both referees admitted by root. The original callbacks add the same count. Root reports full wall times 579.1542seconds for GEN1 and 542.3294seconds for GEN2. Root verified owner MACs and raw registration/evidence bindings; this review does not repeat that cryptographic admission or actor/physics execution. It independently checks all 56 reported mean and field-delta identities and the complete pair inventories.

- GEN1: reportSHA `cb20b98f532c86679228d4d8c651cb09ec0ce2869e5c2843d05df0eba18268a1`; acceptance `5d076852dc8dcee748dfefca08d845938ade0bba0ffcbb6d4606acdb68179005`; registration `ad59cfdc4d6be49361ac6bfcec2c4814795803185c849d72591a310c7cdd76df`.
- GEN2: reportSHA `b615c867a6c2c308ca09191b60826df5e99c552745a69b9c099bb4f064643da4`; acceptance `ea5f0c6c8d32e0694c61181a87f87397b11f0a7c7bc8d92cb24b49aafa4d9bfd`; registration `f8bb8147f4e3131c394ef4f284aada52d93f8fcb69851c1aa6ff094ebaa9766b`.

TRAIN arms face fresh independent rival parameter/seed instances; comparisons share maps/cells, not identical realized lineups. Deterministic planners do not acquire action randomness from an unused seed. Each report uses20,000 shared whole-map bootstrap draws with the fixed seed plus generation. Sixteen map clusters provide broad, approximate uncertainty; 1,024 games per arm do not create1,024 independent map draws. Field intervals are exploratory, and neither adjusted interval family has an exact finite-sample coverage guarantee. Source-family metadata does not itself grant runtime qualification; root admission is separate.

## GEN1 goal/control package contrast

The exact Goal source is `441596f94a1c2793e8f9c4b02c380160b4fa9985cc0cf50457bbbdfdbc73d514`; f5 is `f5e870cd8bb56024c579d1251943c656daf62d2652c5eba44aee530ba1160405`. Their twelve numeric defaults match. The extension changes persistent target scores and their fixed hazard/likelihood calculation while preserving f5 mechanics. It is a structural-package test, not a one-factor test of persistence alone.

| Goal−f5 | Point delta | Unadjusted95% interval |
|---|---:|---|
| economic | -0.017578 | [-0.169922, 0.148438] |
| independent | -0.091797 | [-0.220703, 0.050781] |
| erratic | 0.044922 | [-0.048828, 0.132812] |
| pressure | -0.015625 | [-0.082031, 0.050781] |

The largest negative point component is independent (racer/blocker/raider), partly offset by erratic. All four field intervals include zero. A hypothesis is that retained goal mass reacts too slowly to changing plans, or that ignoring stationary observations discards useful evidence; an opposite hypothesis is that it smooths noisy movement. These are unmeasured mechanisms, not conclusions from the field table. The report contains no event-level calibration or activation trace that separates them from lineup noise. Do not change hazard 0.2, moved factor 4, field weighting or the control after seeing this result.

Goal−e8 is+0.090332, adjusted[0.009277,0.169434]; f5−e8 is+0.110352, adjusted[0.001953,0.229980]. Therefore the goal/e8 result is compatible with the inherited Blocker architecture supplying the advantage, while the added package contributes no established gain. The favorable comparison to a weaker reference cannot replace the declared same-generation structural control.

Bchild remains the GEN1 point leader. Its gap to original B is+0.017578, adjusted[−0.115234,0.134277], and to f5+0.025391, adjusted[−0.115723,0.146973]. That does not resolve the best Blocker source. Five of 28 GEN1 overall intervals exclude zero after adjustment: original B>Echild1, Goal>e8, f5>Echild1, Bchild>Echild1 and f5>e8. Eleven exclude zero unadjusted. These are concrete source comparisons within this generation, not universal family rankings.

## GEN1 arm profiles

| Arm | Source prefix | Overall | Economic | Independent | Erratic | Pressure |
|---|---|---:|---:|---:|---:|---:|
| Bchild | `fcc57d1ea666` | 2.381348 | 2.242188 | 1.978516 | 2.587891 | 2.716797 |
| B | `1bb70109a75e` | 2.363770 | 2.197266 | 1.929688 | 2.593750 | 2.734375 |
| f5 | `f5e870cd8bb5` | 2.355957 | 2.208984 | 2.035156 | 2.525391 | 2.654297 |
| Goal | `441596f94a1c` | 2.335938 | 2.191406 | 1.943359 | 2.570312 | 2.638672 |
| F | `f95dc9fc2266` | 2.331055 | 2.132812 | 1.962891 | 2.570312 | 2.658203 |
| Fchild1 | `24b527d0117f` | 2.319336 | 2.083984 | 2.021484 | 2.519531 | 2.652344 |
| e8 | `e8b3682d8b39` | 2.245605 | 2.072266 | 1.839844 | 2.515625 | 2.554688 |
| Echild1 | `b591ba7fb0e4` | 2.240723 | 2.021484 | 1.902344 | 2.527344 | 2.511719 |

Echild1 changes e8 cash_weight 1.25275→1.30305, raid_late 1.65061→2.075748 and upgrade_open 1.46008→1.76269. It is−0.004883 versus e8, adjusted[−0.135742,0.128418]: no numeric improvement is established. Fchild1 changes Feint KEEP 0.8→0.795577, slightly increasing old-target retention; its delta to F is−0.011719, adjusted[−0.090332,0.053223]. Neither result identifies a beneficial coefficient direction. The source-specific changes differ from GEN0 children, so their raw means cannot be a cross-generation mutation trend.

## Every fixed GEN1 contrast

A−B orientation is source-SHA lexical. B=original Blocker, F=original Feint; Bchild is retained fcc57d, Echild1=b591ba, Fchild1=24b527. Values are rounded; original reports preserve exact endpoints.

| A−B | Delta | Unadjusted95% | Descriptive Bonferroni 28 |
|---|---:|---|---|
| B−Fchild1 | 0.044434 | [-0.008301, 0.091797] | [-0.046875, 0.116211] |
| B−Goal | 0.027832 | [-0.026367, 0.081055] | [-0.060547, 0.110352] |
| B−Echild1 | 0.123047 | [0.056641, 0.188965] | [0.020996, 0.222656] |
| B−e8 | 0.118164 | [0.039062, 0.190918] | [-0.020020, 0.229492] |
| B−f5 | 0.007812 | [-0.048340, 0.064941] | [-0.081543, 0.104492] |
| B−F | 0.032715 | [-0.009766, 0.076172] | [-0.035156, 0.101074] |
| B−Bchild | -0.017578 | [-0.092773, 0.061035] | [-0.134277, 0.115234] |
| Fchild1−Goal | -0.016602 | [-0.068359, 0.035156] | [-0.097656, 0.065430] |
| Fchild1−Echild1 | 0.078613 | [0.011230, 0.139648] | [-0.031738, 0.171387] |
| Fchild1−e8 | 0.073730 | [-0.002930, 0.147461] | [-0.053711, 0.183594] |
| Fchild1−f5 | -0.036621 | [-0.089355, 0.017578] | [-0.118164, 0.047363] |
| Fchild1−F | -0.011719 | [-0.058105, 0.031250] | [-0.090332, 0.053223] |
| Fchild1−Bchild | -0.062012 | [-0.137695, 0.013184] | [-0.182129, 0.063965] |
| Goal−Echild1 | 0.095215 | [0.028320, 0.161621] | [-0.013184, 0.199219] |
| Goal−e8 | 0.090332 | [0.040527, 0.140625] | [0.009277, 0.169434] |
| Goal−f5 | -0.020020 | [-0.078613, 0.040039] | [-0.110352, 0.079102] |
| Goal−F | 0.004883 | [-0.049316, 0.057129] | [-0.080566, 0.085449] |
| Goal−Bchild | -0.045410 | [-0.103516, 0.010742] | [-0.135742, 0.041504] |
| Echild1−e8 | -0.004883 | [-0.083984, 0.080078] | [-0.135742, 0.128418] |
| Echild1−f5 | -0.115234 | [-0.171387, -0.062500] | [-0.205078, -0.035645] |
| Echild1−F | -0.090332 | [-0.155762, -0.026367] | [-0.194824, 0.007812] |
| Echild1−Bchild | -0.140625 | [-0.230957, -0.055176] | [-0.282715, -0.006348] |
| e8−f5 | -0.110352 | [-0.187500, -0.039551] | [-0.229980, -0.001953] |
| e8−F | -0.085449 | [-0.159180, -0.015137] | [-0.202637, 0.022461] |
| e8−Bchild | -0.135742 | [-0.217773, -0.051270] | [-0.260254, 0.004883] |
| f5−F | 0.024902 | [-0.024414, 0.072754] | [-0.054199, 0.099121] |
| f5−Bchild | -0.025391 | [-0.105957, 0.059082] | [-0.146973, 0.115723] |
| F−Bchild | -0.050293 | [-0.111328, 0.012207] | [-0.142090, 0.053711] |

## GEN2: separate current-generation evidence

GEN2 has no Goal arm. Its omission follows the frozen elite/family-parent rule after GEN1; it is not a new trial showing harm. Do not infer its counterfactual GEN2 score or compare its older raw mean against newer sources.

| Arm | Source prefix | Overall | Economic | Independent | Erratic | Pressure |
|---|---|---:|---:|---:|---:|---:|
| Bchild | `fcc57d1ea666` | 2.398926 | 2.308594 | 1.964844 | 2.628906 | 2.693359 |
| B | `1bb70109a75e` | 2.391602 | 2.269531 | 2.015625 | 2.585938 | 2.695312 |
| f5 | `f5e870cd8bb5` | 2.385254 | 2.292969 | 1.908203 | 2.615234 | 2.724609 |
| Bchild2 | `d9de1638ee55` | 2.384277 | 2.261719 | 1.927734 | 2.593750 | 2.753906 |
| F | `f95dc9fc2266` | 2.343750 | 2.251953 | 1.906250 | 2.589844 | 2.626953 |
| Fchild2 | `629fd3625e2d` | 2.323242 | 2.164062 | 1.878906 | 2.613281 | 2.636719 |
| Echild2 | `6f9c7cd4a44f` | 2.248047 | 2.007812 | 1.898438 | 2.511719 | 2.574219 |
| e8 | `e8b3682d8b39` | 2.226562 | 2.015625 | 1.867188 | 2.476562 | 2.546875 |

The four concrete Blocker-family arms (original B, f5, retained Bchild and Bchild2) each beat both current e8-family arms under this generation's descriptive Bonferroni 28 overall intervals:8 positive source comparisons. Eleven intervals exclude zero unadjusted. This is substantive evidence for those sources over those e8 variants on this fresh panel. It is not proof every Blocker genotype is better, does not measure unseen rival algorithms, and cannot be projected into an absolute-strength time trend.

Bchild is again the point leader, but Bchild−original B is only+0.007324, adjusted[−0.080078,0.080566]; Bchild−f5 is+0.013672, adjusted[−0.057617,0.093750]. No best Blocker source is resolved. A repeated point rank is not confirmation of its two numeric changes.

Bchild2 (`d9de1638...`) inherits the retained Bchild structure/genes and lowers STAY0 from 0.8 to 0.706719. At identical public evidence, that lowers the prior chance of a newly arrived level1 raider staying, which can reduce the benefit of Shield defence. It is−0.014648 versus its parent, adjusted[−0.095215,0.074707]. Its pressure gain is offset by negative point deltas elsewhere. Without event traces, fewer actual Shields or a causal defence explanation has not been shown.

Echild2 (`6f9c7cd4...`) lowers e8 shield_weight 1.30296→1.144003. Its+0.021484 parent contrast has adjusted interval[−0.060059,0.102539]. Fchild2 (`629fd362...`) lowers Feint CLAIM_THR 0.35→0.272155, weakening the threat discount on bare neutral claims; its−0.020508 parent contrast has adjusted interval[−0.109375,0.055176]. Neither sparse proposal has an established improvement over its own parent.

Independent remains the lowest point field for these sources. Gen2 pressure has the highest score for Bchild2, but this does not justify selecting a pressure-only policy or adding the evaluator's hidden field label to actor inputs. These are exploratory strata.

## Every fixed GEN2 contrast

Bchild2=d9de1638, Echild2=6f9c7cd4, Fchild2=629fd362. The table is within GEN2 only.

| A−B | Delta | Unadjusted95% | Descriptive Bonferroni 28 |
|---|---:|---|---|
| B−Fchild2 | 0.068359 | [-0.000488, 0.146973] | [-0.033203, 0.203613] |
| B−Echild2 | 0.143555 | [0.069824, 0.222656] | [0.025879, 0.270996] |
| B−Bchild2 | 0.007324 | [-0.027344, 0.043457] | [-0.044922, 0.066406] |
| B−e8 | 0.165039 | [0.076660, 0.260254] | [0.028809, 0.320312] |
| B−f5 | 0.006348 | [-0.043457, 0.054199] | [-0.073242, 0.083008] |
| B−F | 0.047852 | [-0.014648, 0.111816] | [-0.053223, 0.150879] |
| B−Bchild | -0.007324 | [-0.056641, 0.045898] | [-0.080566, 0.080078] |
| Fchild2−Echild2 | 0.075195 | [-0.016113, 0.162109] | [-0.069336, 0.212402] |
| Fchild2−Bchild2 | -0.061035 | [-0.125977, 0.000000] | [-0.164062, 0.033203] |
| Fchild2−e8 | 0.096680 | [-0.010254, 0.205566] | [-0.067383, 0.263672] |
| Fchild2−f5 | -0.062012 | [-0.136719, 0.008301] | [-0.183105, 0.046875] |
| Fchild2−F | -0.020508 | [-0.074219, 0.029297] | [-0.109375, 0.055176] |
| Fchild2−Bchild | -0.075684 | [-0.145508, -0.009766] | [-0.189453, 0.021973] |
| Echild2−Bchild2 | -0.136230 | [-0.216797, -0.059570] | [-0.272461, -0.010742] |
| Echild2−e8 | 0.021484 | [-0.030273, 0.073242] | [-0.060059, 0.102539] |
| Echild2−f5 | -0.137207 | [-0.209473, -0.066895] | [-0.253906, -0.029297] |
| Echild2−F | -0.095703 | [-0.172363, -0.017578] | [-0.213379, 0.033691] |
| Echild2−Bchild | -0.150879 | [-0.223145, -0.083496] | [-0.269531, -0.045410] |
| Bchild2−e8 | 0.157715 | [0.072266, 0.253418] | [0.025391, 0.313965] |
| Bchild2−f5 | -0.000977 | [-0.036133, 0.033691] | [-0.054688, 0.052734] |
| Bchild2−F | 0.040527 | [-0.012207, 0.088379] | [-0.051270, 0.113281] |
| Bchild2−Bchild | -0.014648 | [-0.066895, 0.040039] | [-0.095215, 0.074707] |
| e8−f5 | -0.158691 | [-0.246582, -0.077148] | [-0.301758, -0.031738] |
| e8−F | -0.117188 | [-0.206055, -0.028320] | [-0.256836, 0.019531] |
| e8−Bchild | -0.172363 | [-0.248047, -0.103027] | [-0.295898, -0.064453] |
| f5−F | 0.041504 | [-0.024902, 0.104004] | [-0.066895, 0.140137] |
| f5−Bchild | -0.013672 | [-0.064453, 0.034180] | [-0.093750, 0.057617] |
| F−Bchild | -0.055176 | [-0.122070, 0.014160] | [-0.157227, 0.058105] |

## Strategy and overfitting implications

Current authorized evidence supports exploring the Blocker portfolio, but does not demonstrate that the new goal architecture improves f5 or that the leading numeric Blocker improves original B. Correct public memory, more search or more callbacks do not automatically imply stronger play. The correct outcome of a failed-to-resolve structural proposal can be to retain the existing stronger references under the fixed rule.

The old and new public-memory rules remain a correctness distinction independent of a tiny rank difference. The target model remains heuristic: persistent scores are not a posterior over actual hidden plans, and the full callbacks/referees validate execution rather than plan identification. A proposal can have valid information boundaries and still be strategically unhelpful.

Continue only the frozen whole-generation parent/elite recipe and the declared DEV/final process. Do not fit a new goal hazard, merge favorable numeric genes into f5, test only successful fields, rescue a source using partial GEN3 scores, or weaken the promotion rule. Those would be new adaptive experiments, not this result. These reports are consumed TRAIN evidence with approximate finite-map uncertainty. They grant no original-primary credit, completed per-game BMCTS credit or promotion. No incomplete architecture result or future generation has been used.
