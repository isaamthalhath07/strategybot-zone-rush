# Forward-planning experiments

PW is opponents outscored per game, ties half, maximum 3. It is not actual competition Elo.
Discovery intervals are exploratory. Final aggregate intervals concern the registered synthetic distributions.

## discovery.json

Split: discovery; seed: 481763; actual clock budgets: False.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.1161 | 2996 | +0.0000 | [+0.0000, +0.0000] |
| prior24 | 0.7321 | 2497 | -1.3839 | [-1.6172, -1.1507] |
| future24 | 0.7411 | 2482 | -1.3750 | [-1.5898, -1.1602] |
| careful24 | 1.6607 | 2827 | -0.4554 | [-0.6881, -0.2226] |
| future36 | 0.9509 | 2611 | -1.1652 | [-1.3962, -0.9342] |
| placement24 | 1.4152 | 2707 | -0.7009 | [-0.9509, -0.4509] |

## corrected_discovery.json

Split: discovery; seed: 481787; actual clock budgets: False.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.2455 | 2994 | +0.0000 | [+0.0000, +0.0000] |
| one_job | 2.6518 | 3071 | +0.4062 | [+0.2284, +0.5841] |
| committed | 2.5848 | 3071 | +0.3393 | [+0.1568, +0.5218] |
| guarded | 2.4464 | 3039 | +0.2009 | [+0.0213, +0.3804] |
| prior_guarded | 2.4955 | 3074 | +0.2500 | [+0.0962, +0.4038] |

## development.json

Split: development; seed: 692731; actual clock budgets: False.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.1384 | 2977 | +0.0000 | [+0.0000, +0.0000] |
| one_job | 2.4196 | 3027 | +0.2812 | [+0.1496, +0.4129] |
| committed | 2.4330 | 3035 | +0.2946 | [+0.1614, +0.4278] |
| prior_one_job | 2.3638 | 3022 | +0.2254 | [+0.0901, +0.3608] |
| prior_guarded | 2.3549 | 3031 | +0.2165 | [+0.0856, +0.3474] |

## final.json

Split: final; seed: 893741; actual clock budgets: False.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.3611 | 2977 | +0.0000 | [+0.0000, +0.0000] |
| one_job | 2.5000 | 3004 | +0.1389 | [+0.0727, +0.2050] |

### Map subgroups (descriptive, not multiplicity-adjusted)

| Group | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| corridors | 96 | -0.0156 | [-0.2333, +0.2021] |
| edge | 96 | +0.0312 | [-0.1770, +0.2395] |
| flat | 96 | +0.5990 | [+0.3971, +0.8008] |
| inverted | 96 | +0.0417 | [-0.1153, +0.1987] |
| noise | 96 | +0.1510 | [-0.0457, +0.3478] |
| pockets | 96 | +0.1146 | [-0.1046, +0.3337] |
| richcorner | 96 | +0.2240 | [+0.0550, +0.3930] |
| richhome | 96 | -0.0260 | [-0.2240, +0.1719] |
| standard | 96 | +0.1302 | [-0.0571, +0.3175] |

### Seat (zero-based in data) subgroups (descriptive, not multiplicity-adjusted)

| Group | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| 0 | 216 | +0.1968 | [+0.0624, +0.3311] |
| 1 | 216 | +0.0579 | [-0.0781, +0.1938] |
| 2 | 216 | +0.2222 | [+0.0950, +0.3495] |
| 3 | 216 | +0.0787 | [-0.0523, +0.2097] |

## native_confirmation.json

Split: native_confirmation; seed: 934871; actual clock budgets: True.

| Variant | PW/3 | Mean score | Difference | 95% interval |
|---|---:|---:|---:|---|
| baseline | 2.4509 | 3053 | +0.0000 | [+0.0000, +0.0000] |
| one_job | 2.7054 | 3128 | +0.2545 | [+0.1771, +0.3318] |

### Map subgroups (descriptive, not multiplicity-adjusted)

| Group | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| edge | 64 | +0.2188 | [+0.0242, +0.4133] |
| flat | 64 | +0.3203 | [+0.0473, +0.5934] |
| inverted | 64 | +0.2891 | [+0.0580, +0.5201] |
| noise | 64 | +0.2500 | [+0.0528, +0.4472] |
| richcorner | 64 | +0.2344 | [+0.0288, +0.4400] |
| richhome | 64 | +0.2812 | [+0.1529, +0.4096] |
| standard | 64 | +0.1875 | [+0.0063, +0.3687] |

### Seat (zero-based in data) subgroups (descriptive, not multiplicity-adjusted)

| Group | Tasks | Difference | 95% interval |
|---|---:|---:|---|
| 0 | 112 | +0.2768 | [+0.1079, +0.4456] |
| 1 | 112 | +0.2411 | [+0.0873, +0.3949] |
| 2 | 112 | +0.2768 | [+0.1098, +0.4438] |
| 3 | 112 | +0.2232 | [+0.0959, +0.3506] |

## Ownership prediction (separate from policy improvement)

56 fixed-baseline games; five-class Brier loss, lower is better. Forecasts see only current public history.

| Turns ahead | Persistence | Raw futures | 50% persistence shrinkage |
|---|---:|---:|---:|
| 4 | 0.0991 | 0.0482 | 0.0504 |
| 8 | 0.2006 | 0.1189 | 0.1149 |
| 16 | 0.4006 | 0.2331 | 0.2365 |

4976 comparison games; 1592320 checked action calls. Prediction and correctness games are additional.

All original failures are retained. Source hashes refer to this frozen code; future revisions must not reuse consumed final sets as tuning data.
