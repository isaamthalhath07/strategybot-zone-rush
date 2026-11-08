# Recorded fresh-opponent experiments

PW means mean opponents outscored per game (ties count half), maximum 3.
Intervals describe independent paired game tasks. Discovery comparisons
are exploratory and have no multiple-comparison adjustment.

## train_discovery.json

Split: **train**, seed **183719**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.2057 | 2853 | +0.0000 | [+0.0000, +0.0000] |
| observe_only | 2.2057 | 2853 | +0.0000 | [+0.0000, +0.0000] |
| context_commit | 2.2057 | 2854 | +0.0000 | [+0.0000, +0.0000] |
| context_defence | 1.9974 | 2799 | -0.2083 | [-0.3240, -0.0927] |
| guarded | 2.0547 | 2817 | -0.1510 | [-0.2524, -0.0497] |
| context_both | 1.9922 | 2801 | -0.2135 | [-0.3304, -0.0967] |
| future_window | 2.1042 | 2841 | -0.1016 | [-0.2285, +0.0254] |
| dwell | 2.2057 | 2853 | +0.0000 | [+0.0000, +0.0000] |

192 tasks, 576 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## train_terminal.json

Split: **train**, seed **183733**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.1367 | 2825 | +0.0000 | [+0.0000, +0.0000] |
| terminal | 2.1367 | 2825 | +0.0000 | [+0.0000, +0.0000] |
| terminal_commit | 2.1562 | 2828 | +0.0195 | [-0.0061, +0.0451] |

256 tasks, 768 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## train_confirmation.json

Split: **train**, seed **183751**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.2480 | 2888 | +0.0000 | [+0.0000, +0.0000] |
| aligned_risk | 2.2285 | 2886 | -0.0195 | [-0.0640, +0.0249] |
| confident_risk | 2.2520 | 2889 | +0.0039 | [-0.0038, +0.0116] |
| careful_commit | 2.2480 | 2888 | +0.0000 | [+0.0000, +0.0000] |
| confident_both | 2.2520 | 2889 | +0.0039 | [-0.0038, +0.0116] |
| terminal_commit | 2.2441 | 2888 | -0.0039 | [-0.0173, +0.0095] |

256 tasks, 768 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## train_tradeoffs.json

Split: **train**, seed **183773**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.2305 | 2884 | +0.0000 | [+0.0000, +0.0000] |
| expansion | 2.2012 | 2890 | -0.0293 | [-0.0969, +0.0383] |
| consolidation | 2.2188 | 2885 | -0.0117 | [-0.0396, +0.0162] |
| raid_calibration | 2.3242 | 2920 | +0.0938 | [+0.0203, +0.1672] |
| learned_calibration | 2.3281 | 2920 | +0.0977 | [+0.0231, +0.1722] |
| shield_mix | 2.2109 | 2881 | -0.0195 | [-0.0451, +0.0061] |

256 tasks, 768 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## development.json

Split: **development**, seed **294817**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.2526 | 2834 | +0.0000 | [+0.0000, +0.0000] |
| raid_calibration | 2.2852 | 2853 | +0.0326 | [-0.0300, +0.0951] |
| learned_calibration | 2.2852 | 2854 | +0.0326 | [-0.0296, +0.0947] |

384 tasks, 1152 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

## final.json

Split: **final**, seed **739119**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.1523 | 2933 | +0.0000 | [+0.0000, +0.0000] |
| raid_calibration | 2.2275 | 2956 | +0.0752 | [+0.0393, +0.1111] |

1024 tasks, 3072 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

**Pre-registered final decision:** aggregate gain supported by the interval; inspect robustness before promotion.

### Final map subgroups (descriptive only)

| Map | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| edge | 128 | +0.1289 | [+0.0343, +0.2235] |
| flat | 128 | +0.0820 | [-0.0036, +0.1676] |
| inverted | 128 | +0.1172 | [+0.0339, +0.2004] |
| noise | 128 | +0.0547 | [-0.0340, +0.1434] |
| richcorner | 128 | -0.0078 | [-0.1120, +0.0964] |
| richhome | 128 | +0.0820 | [-0.0142, +0.1783] |
| standard | 256 | +0.0723 | [-0.0161, +0.1606] |

## balanced_confirmation.json

Split: **supplementary_final**, seed **883917**.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 1.9639 | 2878 | +0.0000 | [+0.0000, +0.0000] |
| raid_calibration | 2.0210 | 2896 | +0.0571 | [+0.0221, +0.0922] |

1024 tasks, 3072 distinct opponent parameter draws. Every variant played the same maps, seats, token starts and draws.

**Pre-registered final decision:** aggregate gain supported by the interval; inspect robustness before promotion.

### Final map subgroups (descriptive only)

| Map | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| edge | 128 | +0.0625 | [-0.0267, +0.1517] |
| flat | 128 | +0.0547 | [-0.0114, +0.1208] |
| inverted | 128 | +0.0859 | [+0.0067, +0.1652] |
| noise | 128 | +0.0312 | [-0.0414, +0.1039] |
| richcorner | 128 | -0.0430 | [-0.1555, +0.0696] |
| richhome | 128 | +0.1328 | [+0.0059, +0.2597] |
| standard | 256 | +0.0664 | [-0.0141, +0.1469] |
