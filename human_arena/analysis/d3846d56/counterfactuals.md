# Transcript counterfactual diagnostics

All 80 recorded turns and observations replay exactly through the fingerprint-matched vendored referee. The policy source hash is verified against its pinned Git blob; this script does not execute or change the policy.

These are post-game diagnostics. One-turn results hold other recorded requests fixed. Short exhaustive searches also hold subsequent requests fixed, so rivals do not react to the altered board. Static ownership projections assume remaining land never changes. None of these numbers is a guaranteed strategic improvement against adapting opponents.

## Shield decisions

| Turn | AI seat | Actual outcome | STAY immediate score difference | STAY frozen-ownership projection difference |
|---|---|---|---:|---:|
| 39 | 2 | caught [4] | +0 | +0 |
| 44 | 2 | caught [4] | -4 | -148 |
| 50 | 3 | caught [4] | -6 | -186 |
| 54 | 2 | backfire | +18 | +70 |
| 75 | 2 | backfire | +0 | +0 |

T44 and T50 protect upgraded 3-point cells when the raider already has two of three stays. Giving up partial work on a 2-point own cell can be rational when it prevents the loss of 6 income and a 48-point opposing raid bonus. T39 is less urgent: the raider still needs two stays.

T54 is the clearest missed realized raid: seat 2 shields while standing on the human's level-one 2-point cell; STAY would have taken it if the other recorded requests remain unchanged. This requires hindsight about the human not shielding. T75 differs: the potential raider had just arrived on an upgraded cell and could not capture it that turn. A public-state, future-intent-blind check finds WEST and SOUTH preserve current income and mobility in every enumerated rival request. Shielding still has a possible rival-tempo benefit, so waiting is an option-value improvement, not a proof of dominance.

## T55–T57: a safer exit from the human's center

At T55, seat 4 could move EAST from D4 to E4 (zero-based [3,3]→[3,4]) and stay three turns. This is more than an oracle response to the later human shield. The public board already proves seat 2 backfired at T54: seat 2 newly freezes on the human's C2, while the human visibly upgrades C3 and therefore could not have shielded. Seat 2's four-turn cooldown then covers T55–T58. E4 is its empty upgraded 3-point cell; arrival is uncontested and cannot be caught, and subsequent occupancy blocks entry. Three stays T56–T58 capture it before the owner can shield again. The 48 bonus and 3-point new gross income from that target are rule-guaranteed under the current public facts, although future retention and final score are not.

This opportunity depends on correctly attributing the observed freeze. A model that invents a human cooldown can wrongly treat staying on human-owned D4 as safe, while missing the cooldown that actually exists on seat 2. The exact policy-belief defect is established by the separate decision replay, not by this counterfactual script.

| Start | Seat-4 action path | Through turn | Score difference with recorded rival requests |
|---|---|---|---:|
| 55 | EAST, STAY, STAY, STAY | 58 | +51 |
| 55 | EAST, STAY, STAY, STAY, STAY, STAY | 60 | +57 |
| 56 | EAST, STAY, STAY, STAY | 59 | +51 |
| 57 | EAST, STAY, STAY, STAY | 60 | +51 |

The T56 exit has less inherent protection: three new stays would finish at T59, when seat 2 could normally shield again. Its success in the recorded continuation depends on later events. At T57, leaving D4 avoids the human's actual shield, but learning that exact request in advance would be hindsight.

## Final 2–6 turns, fixed-request exhaustive search

| Start | Turns left | AI seat | Recorded final score | Best own score | Gain | Best pairwise wins gain | States |
|---|---|---|---:|---:|---:|---:|---:|
| 79 | 2 | 2 | 1924 | 1924 | +0 | +0.0 | 24 |
| 79 | 2 | 3 | 2179 | 2179 | +0 | +0.0 | 37 |
| 79 | 2 | 4 | 1615 | 1615 | +0 | +0.0 | 27 |
| 78 | 3 | 2 | 1924 | 1924 | +0 | +0.0 | 71 |
| 78 | 3 | 3 | 2179 | 2179 | +0 | +0.0 | 144 |
| 78 | 3 | 4 | 1615 | 1615 | +0 | +0.0 | 95 |
| 77 | 4 | 2 | 1924 | 1924 | +0 | +0.0 | 42 |
| 77 | 4 | 3 | 2179 | 2179 | +0 | +0.0 | 407 |
| 77 | 4 | 4 | 1615 | 1615 | +0 | +0.0 | 308 |
| 76 | 5 | 2 | 1924 | 1924 | +0 | +0.0 | 43 |
| 76 | 5 | 3 | 2179 | 2192 | +13 | +0.0 | 922 |
| 76 | 5 | 4 | 1615 | 1640 | +25 | +0.0 | 849 |
| 75 | 6 | 2 | 1924 | 1968 | +44 | +0.0 | 1925 |
| 75 | 6 | 3 | 2179 | 2195 | +16 | +0.0 | 1563 |
| 75 | 6 | 4 | 1615 | 1645 | +30 | +0.0 | 2226 |

The full action sequences, endpoint score vectors, per-first-action best static values, and exhaustive flags are in counterfactuals.json. A last-turn action that merely leaves an upgrade unfinished is not automatically a bug: movement also yields no capture on arrival. Check the one-turn alternatives and earlier scheduling separately.

## Movement and central territory

There are exactly two AI movement contest losses (seat 2, T49 and T51), both to the human; no AI occupied-cell blocked-move events occur. The human was ahead in token order in both contests. The rival's move was not known in advance, so these are costly contested choices rather than proof of an illegal-move bug.

Central comparisons below use current public geometry and a simple undisturbed final-score-per-action calculation. They are intentionally optimistic about raids: enemy shields, changing occupancy and later retakes are omitted. A high central cell value alone does not establish the best route. Nearby upgrades and lower-travel claims can have better rates; an enemy upgraded center can be impossible to raid efficiently against a ready defender.

| Turn | Seat | Move | Center job | Center rate | Best outside rate | Center/outside |
|---|---|---|---|---:|---:|---:|
| 60 | 4 | WEST [3, 3]→[3, 2] | [3, 3], owner 1, level 2, 0+3 turns | 35.00 | 17.00 | 2.06 |
| 48 | 2 | NORTH [2, 3]→[1, 3] | [3, 3], owner 1, level 2, 1+3 turns | 34.50 | 20.67 | 1.67 |
| 52 | 2 | NORTH [2, 3]→[1, 3] | [3, 3], owner 1, level 2, 1+3 turns | 31.50 | 23.33 | 1.35 |
| 24 | 4 | EAST [6, 5]→[6, 6] | [4, 4], owner 3, level 2, 3+3 turns | 34.00 | 31.00 | 1.10 |
| 61 | 4 | WEST [3, 2]→[3, 1] | [3, 3], owner 1, level 2, 1+3 turns | 24.75 | 22.67 | 1.09 |
| 59 | 3 | NORTH [1, 6]→[0, 6] | [3, 4], owner 2, level 2, 4+3 turns | 13.71 | 14.50 | 0.95 |
| 64 | 2 | NORTH [1, 2]→[0, 2] | [3, 3], owner 1, level 2, 3+3 turns | 14.00 | 15.00 | 0.93 |
| 14 | 2 | NORTH [3, 4]→[2, 4] | [3, 3], owner 1, level 2, 1+3 turns | 60.00 | 66.00 | 0.91 |
| 62 | 4 | WEST [3, 1]→[3, 0] | [3, 3], owner 1, level 2, 2+3 turns | 18.60 | 22.00 | 0.85 |
| 40 | 3 | NORTH [3, 6]→[2, 6] | [4, 3], owner 1, level 2, 4+3 turns | 21.86 | 27.00 | 0.81 |
| 54 | 3 | EAST [1, 5]→[1, 6] | [3, 3], owner 1, level 2, 4+3 turns | 15.86 | 20.00 | 0.79 |
| 19 | 2 | EAST [2, 4]→[2, 5] | [4, 4], owner 3, level 2, 2+3 turns | 44.40 | 61.00 | 0.73 |
| 19 | 3 | EAST [5, 4]→[5, 5] | [3, 4], owner 2, level 2, 2+3 turns | 44.40 | 61.00 | 0.73 |
| 44 | 3 | NORTH [2, 6]→[1, 6] | [4, 3], owner 1, level 2, 5+3 turns | 17.25 | 25.00 | 0.69 |
| 53 | 2 | WEST [1, 3]→[1, 2] | [3, 3], owner 1, level 2, 2+3 turns | 24.00 | 35.00 | 0.69 |

## Intent-blind T75 comparison

```json
{
  "turn": 75,
  "seat": 2,
  "alternatives": {
    "EAST": {
      "scenarios": 150,
      "minimum_own_income": 36,
      "maximum_own_freeze": 0,
      "possible_end_positions": [
        [
          0,
          3
        ]
      ],
      "maximum_total_rival_freeze_including_self_backfires": 6
    },
    "SOUTH": {
      "scenarios": 150,
      "minimum_own_income": 36,
      "maximum_own_freeze": 0,
      "possible_end_positions": [
        [
          1,
          2
        ]
      ],
      "maximum_total_rival_freeze_including_self_backfires": 6
    },
    "WEST": {
      "scenarios": 150,
      "minimum_own_income": 36,
      "maximum_own_freeze": 0,
      "possible_end_positions": [
        [
          0,
          1
        ]
      ],
      "maximum_total_rival_freeze_including_self_backfires": 6
    },
    "STAY": {
      "scenarios": 150,
      "minimum_own_income": 36,
      "maximum_own_freeze": 0,
      "possible_end_positions": [
        [
          0,
          2
        ]
      ],
      "maximum_total_rival_freeze_including_self_backfires": 6
    },
    "SHIELD": {
      "scenarios": 150,
      "minimum_own_income": 36,
      "maximum_own_freeze": 2,
      "possible_end_positions": [
        [
          0,
          2
        ]
      ],
      "maximum_total_rival_freeze_including_self_backfires": 6
    }
  },
  "interpretation": "WEST or SOUTH preserves all 36 current income under every enumerated rival request, cannot be caught on arrival, and leaves shield ready. SHIELD can instead deny rival tempo if it catches; this is not dominance or a guarantee of a better reactive-game outcome."
}
```

No live app, source policy, weights, or recorded game was modified. Source observations and hidden referee counters are used for the explicit hindsight diagnostics only; the T75 safety comparison is separated and uses the visible just-arrived fact rather than future actions.
