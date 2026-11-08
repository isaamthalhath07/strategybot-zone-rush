# Recorded fresh-opponent experiments

PW means mean opponents outscored per game (ties count half), maximum 3.
Intervals describe independent paired game tasks. Discovery comparisons
are exploratory and have no multiple-comparison adjustment.

## discovery.json

Split: **discovery**, seed **281741**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.6763 | 3089 | +0.0000 | [+0.0000, +0.0000] |
| naive_edges | 2.6004 | 3054 | -0.0759 | [-0.1411, -0.0107] |
| position | 2.6741 | 3082 | -0.0022 | [-0.0612, +0.0567] |
| territory | 2.6473 | 3079 | -0.0290 | [-0.1047, +0.0467] |
| cautious | 2.6295 | 3075 | -0.0469 | [-0.1068, +0.0131] |

224 tasks, 672 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## development.json

Split: **development**, seed **392819**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.7042 | 3119 | +0.0000 | [+0.0000, +0.0000] |
| naive_edges | 2.6819 | 3095 | -0.0223 | [-0.0613, +0.0167] |
| position | 2.6674 | 3103 | -0.0368 | [-0.0810, +0.0073] |
| territory | 2.7165 | 3121 | +0.0123 | [-0.0372, +0.0618] |

448 tasks, 1344 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## final.json

Split: **final**, seed **683971**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.5530 | 3041 | +0.0000 | [+0.0000, +0.0000] |
| territory | 2.6083 | 3049 | +0.0552 | [+0.0141, +0.0963] |

896 tasks, 2688 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

**Pre-registered final decision:** aggregate gain supported by the interval; inspect robustness before promotion.

### Final map subgroups (descriptive only)

| Map | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| edge | 128 | +0.0156 | [-0.0665, +0.0978] |
| flat | 128 | +0.2148 | [+0.0774, +0.3523] |
| inverted | 128 | +0.0469 | [-0.0406, +0.1343] |
| noise | 128 | +0.0156 | [-0.0665, +0.0978] |
| richcorner | 128 | -0.0312 | [-0.1452, +0.0827] |
| richhome | 128 | +0.0547 | [-0.0721, +0.1814] |
| standard | 128 | +0.0703 | [-0.0442, +0.1848] |

## economic_confirmation.json

Split: **supplementary_final**, seed **729251**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.3873 | 3033 | +0.0000 | [+0.0000, +0.0000] |
| territory | 2.3850 | 3031 | -0.0022 | [-0.0622, +0.0578] |

896 tasks, 2688 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

**Pre-registered final decision:** no established gain; retain the existing submission.

### Final map subgroups (descriptive only)

| Map | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| edge | 128 | +0.1055 | [-0.0384, +0.2493] |
| flat | 128 | +0.1523 | [-0.0541, +0.3588] |
| inverted | 128 | +0.0859 | [-0.0898, +0.2617] |
| noise | 128 | -0.1172 | [-0.2464, +0.0120] |
| richcorner | 128 | -0.0430 | [-0.1927, +0.1068] |
| richhome | 128 | +0.0156 | [-0.1365, +0.1678] |
| standard | 128 | -0.2148 | [-0.3487, -0.0809] |

## attribution.json

Split: **attribution**, seed **829781**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.3873 | 3003 | +0.0000 | [+0.0000, +0.0000] |
| territory | 2.4051 | 3000 | +0.0179 | [-0.0626, +0.0983] |
| prior_only | 2.4018 | 3011 | +0.0145 | [-0.0635, +0.0926] |

448 tasks, 1344 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## Nominal opening-role subgroups: discovery.json

These roles are test construction metadata, not guaranteed actual routes. Subgroup intervals are descriptive, without multiplicity adjustment.

| Centre-opening roles | Tasks | Variant | Difference | 95% interval |
|---|---:|---|---:|---|
| 0 | 56 | naive_edges | -0.0179 | [-0.0532, +0.0175] |
| 0 | 56 | position | +0.0179 | [-0.0175, +0.0532] |
| 0 | 56 | territory | +0.0536 | [-0.1013, +0.2084] |
| 0 | 56 | cautious | -0.0357 | [-0.0853, +0.0138] |
| 1 | 56 | naive_edges | -0.0714 | [-0.2377, +0.0948] |
| 1 | 56 | position | +0.0000 | [-0.1128, +0.1128] |
| 1 | 56 | territory | -0.0357 | [-0.1689, +0.0974] |
| 1 | 56 | cautious | +0.0179 | [-0.1004, +0.1361] |
| 2 | 56 | naive_edges | -0.1518 | [-0.2802, -0.0233] |
| 2 | 56 | position | -0.0268 | [-0.1226, +0.0690] |
| 2 | 56 | territory | -0.0625 | [-0.1961, +0.0711] |
| 2 | 56 | cautious | -0.1161 | [-0.2370, +0.0049] |
| 3 | 56 | naive_edges | -0.0625 | [-0.2140, +0.0890] |
| 3 | 56 | position | +0.0000 | [-0.1819, +0.1819] |
| 3 | 56 | territory | -0.0714 | [-0.2523, +0.1095] |
| 3 | 56 | cautious | -0.0536 | [-0.2164, +0.1093] |

## Nominal opening-role subgroups: development.json

These roles are test construction metadata, not guaranteed actual routes. Subgroup intervals are descriptive, without multiplicity adjustment.

| Centre-opening roles | Tasks | Variant | Difference | 95% interval |
|---|---:|---|---:|---|
| 0 | 112 | naive_edges | -0.0179 | [-0.0532, +0.0175] |
| 0 | 112 | position | -0.0357 | [-0.0915, +0.0200] |
| 0 | 112 | territory | +0.0759 | [+0.0057, +0.1460] |
| 1 | 112 | naive_edges | -0.0357 | [-0.1187, +0.0473] |
| 1 | 112 | position | -0.0804 | [-0.1812, +0.0205] |
| 1 | 112 | territory | +0.0000 | [-0.1178, +0.1178] |
| 2 | 112 | naive_edges | +0.0000 | [-0.0833, +0.0833] |
| 2 | 112 | position | -0.0357 | [-0.1260, +0.0546] |
| 2 | 112 | territory | +0.0089 | [-0.0724, +0.0903] |
| 3 | 112 | naive_edges | -0.0357 | [-0.1327, +0.0613] |
| 3 | 112 | position | +0.0045 | [-0.0948, +0.1037] |
| 3 | 112 | territory | -0.0357 | [-0.1533, +0.0819] |

## Nominal opening-role subgroups: final.json

These roles are test construction metadata, not guaranteed actual routes. Subgroup intervals are descriptive, without multiplicity adjustment.

| Centre-opening roles | Tasks | Variant | Difference | 95% interval |
|---|---:|---|---:|---|
| 0 | 224 | territory | +0.0357 | [-0.0536, +0.1251] |
| 1 | 224 | territory | +0.1518 | [+0.0664, +0.2371] |
| 2 | 224 | territory | +0.0379 | [-0.0427, +0.1186] |
| 3 | 224 | territory | -0.0045 | [-0.0759, +0.0670] |

7840 comparison games; 2508800 checked action calls. Baseline matches the unchanged v8 submission.

History minus the static spatial prior (explanatory ablation): +0.0033, 95% interval [-0.0433, +0.0500].

**Decision: retain v8.** The original spatial final gain did not replicate in the separate economic-planner confirmation. History's additional value was not established.
