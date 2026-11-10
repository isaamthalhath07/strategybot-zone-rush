# Zone Rush: every bot in the repository's history, ranked

Generated 2026-11-10. 595 distinct playable `act(state)` sources (by SHA-256) from all 60 commits on all 13 branches, plus bot sources stored inside zip archives committed in history. 35,616 games / 11.4 M timed callbacks on the repo's pinned referee (`simulator/vendor_harness`), current confirmed rules (STAY-only Shield), one isolated process per seat, 200 ms per turn enforced.

Metric: **opponents outscored per game (0-3)**, ties count half. 1.5 is break-even in a field of equals.

## 1. Finals: distinct policies (seed-only clones merged)

Each file played 576 fresh games: 12 new maps x 6 opponent line-ups x 8 seat/priority-token crossings. League = 2,000 games among the 20 finalist files (13 of them are Blocker/Racer/Feint code, so it mostly measures play against that family).

| # | Policy | Files | Fixed-field score (95% CI) | 1st place | League | Faults |
|---|---|---:|---|---:|---:|---:|
| 1 | Racer | 5 | **2.357** [2.27, 2.44] | 54% | 1.615 | 0 |
| 2 | Blocker + public-memory patch (strategy_candidates/) | 1 | **2.327** [2.23, 2.42] | 54% | 1.559 | 0 |
| 3 | Blocker | 5 | **2.318** [2.23, 2.41] | 53% | 1.530 | 0 |
| 4 | Feint | 1 | **2.221** [2.11, 2.32] | 48% | 1.629 | 0 |
| 5 | novel_d_shieldmaster (PR10 novel-d) | 1 | **2.158** [2.04, 2.28] | 44% | 1.315 | 0 |
| 6 | main-bot CONFIG variant fa9d68 (evolution league) | 1 | **2.146** [1.99, 2.28] | 40% | 1.480 | 0 |
| 7 | Zenith | 1 | **2.128** [2.05, 2.21] | 42% | 1.289 | 0 |
| 8 | main-bot CONFIG variant mutation_01 (evolution league) | 1 | **2.068** [1.95, 2.15] | 35% | 1.570 | 0 |
| 9 | main-bot CONFIG variant mutation_03 (evolution league) | 1 | **2.064** [1.95, 2.17] | 34% | 1.496 | 0 |
| 10 | hx_steady persona (zenith/lab/humanlike) | 1 | **2.037** [1.95, 2.11] | 35% | 1.407 | 0 |
| 11 | CURRENT main bot.py (guarded Transfer, STAY-only) | 1 | **1.994** [1.89, 2.09] | 33% | 1.335 | 0 |
| 12 | UltimateBot | 1 | **1.993** [1.91, 2.06] | 34% | 1.194 | 0 |

Per line-up (fixed-field score):

| Policy | house | alt_arch | independent | llm_pasted | shield_bait | racers |
|---|---:|---:|---:|---:|---:|---:|
| Racer | 1.79 | 2.06 | 2.75 | 2.80 | 2.33 | 2.42 |
| Blocker + public-memory patch (strategy_candidates/) | 1.68 | 1.99 | 2.75 | 2.72 | 2.44 | 2.39 |
| Blocker | 1.70 | 1.93 | 2.75 | 2.72 | 2.43 | 2.39 |
| Feint | 1.57 | 1.72 | 2.70 | 2.75 | 2.27 | 2.32 |
| novel_d_shieldmaster (PR10 novel-d) | 1.42 | 1.44 | 2.60 | 2.66 | 2.38 | 2.46 |
| main-bot CONFIG variant fa9d68 (evolution league) | 1.75 | 2.06 | 2.21 | 2.22 | 2.61 | 2.02 |
| Zenith | 1.31 | 1.80 | 2.26 | 2.40 | 2.58 | 2.42 |
| main-bot CONFIG variant mutation_01 (evolution league) | 1.42 | 1.65 | 2.19 | 2.39 | 2.58 | 2.19 |
| main-bot CONFIG variant mutation_03 (evolution league) | 1.54 | 1.81 | 2.19 | 2.24 | 2.45 | 2.16 |
| hx_steady persona (zenith/lab/humanlike) | 1.41 | 1.44 | 2.29 | 2.44 | 2.19 | 2.46 |
| CURRENT main bot.py (guarded Transfer, STAY-only) | 1.21 | 1.57 | 2.24 | 2.29 | 2.51 | 2.15 |
| UltimateBot | 1.17 | 1.40 | 2.25 | 2.40 | 2.35 | 2.40 |

Line-ups: **house** = current main bot.py, Blocker, Apex; **alt_arch** = UltimateBot, Fusion, Zenith; **independent** = opp_raider_03, opp_adaptive_02, opp_farmer_04; **llm_pasted** = opp_planner_gpt1, opp_opportunist_gemini1, opp_greedy_gpt1; **shield_bait** = opp_shield_03, opp_bait_01, Feint; **racers** = Racer, opp_planner_gemini1, opp_raider_gpt1.

## 2. Finals: all 20 files

| Rank | SHA-256 (12) | Bot | Fixed-field (95% CI) | League (95% CI) | Max ms | Where |
|---:|---|---|---|---|---:|---|
| 1 | `709a5c02398f` | Racer seed-only clone (seat 4 reseeded) | 2.352 [2.26, 2.44] | 1.762 [1.66, 1.86] | 13 | archive: evidence/…/6a52734787d5e9567c5ba155 |
| 2 | `2a2563b3aaf4` | Racer seed-only clone (seat 2 reseeded) | 2.360 [2.27, 2.45] | 1.617 [1.51, 1.73] | 23 | archive: evidence/…/81b8d045c641731e84896e42 |
| 3 | `5db015ae27ed` | Racer seed-only clone (seat 3 reseeded) | 2.360 [2.28, 2.44] | 1.577 [1.47, 1.69] | 44 | archive: evidence/…/38f32b0260415d625c245820 |
| 4 | `d9d800393d95` | Blocker seed-only clone (seat 3 reseeded) | 2.336 [2.24, 2.42] | 1.599 [1.49, 1.71] | 13 | archive: evidence/…/85de8d708dc60fe05db9b85c |
| 5 | `a35c2c481164` | Racer (novel-b) | 2.359 [2.27, 2.45] | 1.574 [1.47, 1.68] | 21 | tester_bots/racer.py @ 36275b7 |
| 6 | `88496d239f5d` | Blocker seed-only clone (seat 4 reseeded) | 2.322 [2.23, 2.41] | 1.595 [1.48, 1.71] | 21 | archive: evidence/…/a2fe750349a9bd2f3bcb01cf |
| 7 | `047ed5d8391e` | Racer seed-only clone (seat 2 reseeded) | 2.357 [2.27, 2.45] | 1.544 [1.44, 1.65] | 23 | archive: evidence/…/fb3ed1dc2c8d66588aaa302b |
| 8 | `f5e870cd8bb5` | Blocker + public-memory patch (strategy_candidates/) | 2.327 [2.23, 2.42] | 1.559 [1.46, 1.67] | 17 | strategy_candidates/blocker_public_memory.py @ 7c0fe92 |
| 9 | `1bb70109a75e` | Blocker (novel-b) | 2.322 [2.23, 2.42] | 1.550 [1.43, 1.67] | 29 | tester_bots/blocker.py @ 36275b7 |
| 10 | `f95dc9fc2266` | Feint (novel-b) | 2.221 [2.11, 2.32] | 1.629 [1.52, 1.74] | 18 | confirmation_campaign/evidence/architectures_v2/feint_original.py @ 36275b7 |
| 11 | `191059b37141` | Blocker seed-only clone (seat 1 reseeded) | 2.308 [2.22, 2.39] | 1.538 [1.43, 1.65] | 28 | archive: evidence/…/332f38a76d36586855a808a9 |
| 12 | `b9e2f84869a4` | Blocker seed-only clone (seat 1 reseeded) | 2.301 [2.21, 2.39] | 1.370 [1.27, 1.48] | 15 | archive: evidence/…/423c052840c68eded42ad061 |
| 13 | `def6a8585f26` | main-bot CONFIG variant mutation_01 (evolution league) | 2.068 [1.95, 2.15] | 1.570 [1.47, 1.68] | 10 | archive: evidence/…/mutation_01.py |
| 14 | `8e84ff655452` | main-bot CONFIG variant fa9d68 (evolution league) | 2.146 [1.99, 2.28] | 1.480 [1.37, 1.58] | 10 | archive: evidence/…/fa9d68b71887396739904cd1 |
| 15 | `4737b8184da3` | main-bot CONFIG variant mutation_03 (evolution league) | 2.064 [1.95, 2.17] | 1.496 [1.39, 1.60] | 13 | archive: evidence/…/mutation_03.py |
| 16 | `d75575389253` | novel_d_shieldmaster (PR10 novel-d) | 2.158 [2.04, 2.28] | 1.315 [1.20, 1.43] | 7 | archive: validation/…/d75575389253.py |
| 17 | `18c0316f3250` | hx_steady persona (zenith/lab/humanlike) | 2.037 [1.95, 2.11] | 1.407 [1.29, 1.52] | 13 | zenith/lab/humanlike/hx_steady.py @ c3dfbfd |
| 18 | `5f1bb9f70aac` | Zenith | 2.128 [2.05, 2.21] | 1.289 [1.18, 1.39] | 107 | zenith/zenith_bot.py @ c3dfbfd |
| 19 | `e8b3682d8b39` | CURRENT main bot.py (guarded Transfer, STAY-only) | 1.994 [1.89, 2.09] | 1.335 [1.23, 1.44] | 12 | bot.py @ a89feac (2026-11-08) … 15 commits; root bot.py at head of: main |
| 20 | `a8f7a74e7ed3` | UltimateBot | 1.993 [1.91, 2.06] | 1.194 [1.08, 1.30] | 9 | tester_bots/ultimate.py, ultimate.py @ b926add |

Files 1-12 are one code base (Blocker/Racer/Feint). Eight of them are byte-for-byte Racer or Blocker with a different random seed for one seat; their spread shows the noise level.

## 3. Sensitivity: superseded 'presence' Shield reading (`catch_requires_stay=False`)

192 games each (6 maps x 4 line-ups x 8 crossings). Not the confirmed rule; shown only to see whether the order depends on it.

| Bot | Score (95% CI) | Faults |
|---|---|---:|
| Racer (novel-b) | 2.242 [2.10, 2.37] | 0 |
| Blocker (novel-b) | 2.195 [2.05, 2.36] | 0 |
| Feint (novel-b) | 2.177 [2.08, 2.27] | 0 |
| main-bot CONFIG variant fa9d68 (evolution league) | 2.146 [2.03, 2.24] | 0 |
| root bot.py [presence_guarded] | 2.125 [1.95, 2.30] | 0 |
| CURRENT main bot.py (guarded Transfer, STAY-only) | 2.083 [1.93, 2.23] | 0 |
| main-bot CONFIG variant mutation_01 (evolution league) | 2.052 [1.90, 2.20] | 0 |
| novel_d_shieldmaster (PR10 novel-d) | 2.026 [1.72, 2.36] | 0 |
| UltimateBot | 1.932 [1.80, 2.08] | 0 |
| Zenith | 1.875 [1.80, 1.95] | 0 |

## 4. Every root `bot.py` ever committed

| Commit | Date | Rank / 595 | Screening score (games) | Architecture | Commit subject |
|---|---|---:|---|---|---|
| `668be6b` | 2026-11-06 | 97 | 1.7708 (48) | mybot beam planner (v3-v7) | StrategyBot / Zone Rush competition bot |
| `223358b` | 2026-11-06 | 110 | 1.7500 (48) | mybot beam planner (v3-v7) | Strategy sweep, GPU self-play track, and ship v6 |
| `c7cbaa9` | 2026-11-06 | 122 | 1.6250 (48) | mybot beam planner (v3-v7) | Test against an independent opponent field and ship v7 |
| `5fae6ab` | 2026-11-07 | 121 | 1.6458 (48) | mybot beam planner (v6-v9) | Harden the opponent field, fix eight bugs, put measurement on a sound footing |
| `0796039` | 2026-11-07 | 84 | 1.7812 (48) | Transfer / evolved economic planner | Add validated evolved StrategyBot and reproducible research package |
| `961e729` | 2026-11-07 | 73 | 1.7917 (48) | mybot beam planner (v6-v9) | Ship v7, and record that its headline gain was measured on a biased field |
| `d31fff2` | 2026-11-07 | 78 | 1.7812 (48) | Fusion (econ + beam fallback) | Review all four branches on one field and ship a fused failsafe bot |
| `6aaa644` | 2026-11-07 | 66 | 1.8125 (48) | mybot beam planner (v6-v9) | Codex rules audit, planner corrections, independent challengers, visual harness |
| `6b69844` | 2026-11-07 | 60 | 1.8681 (144) | mybot beam planner (v6-v9) | Validate fresh-opponent features and ship confirmed raid recalibration |
| `ed708f3` | 2026-11-08 | 81 | 1.7812 (48) | Fusion (econ + beam fallback) | Guard bot.py against two rule readings the server could differ on |
| `13cd215` | 2026-11-08 | 83 | 1.7812 (48) | Fusion (econ + beam fallback) | Merge main into PR #11 and preserve frozen research provenance |
| `36275b7` | 2026-11-08 | 28 | 2.0139 (144) | presence guarded | Consolidate validated champion, six testers and portable simulator |
| `a89feac` | 2026-11-08 | 19 | 2.0139 (144) | guarded Transfer (current main family) | Apply clarified STAY-only Shields and validate resilient champion |

## 5. Root `bot.py` at each branch head

| Branch | Head | Date | bot.py SHA | Rank / 595 | Screening score |
|---|---|---|---|---:|---:|
| `v7-independent-field` | `c7cbaa9` | 2026-11-06 | `31965e1412c6` | 122 | 1.6250 |
| `research/evolution-2026-11-07` | `0796039` | 2026-11-07 | `1dca0c916af4` | 84 | 1.7812 |
| `hardened-field-and-fixes` | `961e729` | 2026-11-07 | `aa49608fe334` | 73 | 1.7917 |
| `visual-harness` | `6d7b7fd` | 2026-11-07 | `beec3a70b4e6` | 110 | 1.7500 |
| `claude/eager-cannon-vq1vca` | `641b9ac` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `claude/inspiring-hypatia-6r82j1` | `641b9ac` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `opponents-field` | `641b9ac` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `sim-focus` | `641b9ac` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `claude/amazing-fermat-yiicr8` | `a5b462f` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `combined` | `b792340` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `manifest-update` | `9677b0e` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `opponents-fixed` | `c65e838` | 2026-11-08 | `b2de2f334e88` | 81 | 1.7812 |
| `main` | `bf6dc95` | 2026-11-09 | `e8b3682d8b39` | 19 | 2.0139 |

## 6. Full ranking (all 595)

Finalists are ordered by the mean of fixed-field and league score; everything below by screening score within the stage it reached (R3 = 144 games, R2 = 48, R1 = 16). Lower tiers have wide error bars (about +/-0.15 at 144 games, +/-0.25 at 48, +/-0.4 at 16).

| Rank | SHA-256 (12) | Bot | Family | Architecture | Stage | Screening score | Games | Faults | Where |
|---:|---|---|---|---|---|---:|---:|---:|---|
| 1 | `709a5c02398f` | Racer seed-only clone (seat 4 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2569 | 144 | 0 | archive: evidence/…/6a52734787d5e9567c5ba155 |
| 2 | `2a2563b3aaf4` | Racer seed-only clone (seat 2 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2500 | 144 | 0 | archive: evidence/…/81b8d045c641731e84896e42 |
| 3 | `5db015ae27ed` | Racer seed-only clone (seat 3 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2917 | 144 | 0 | archive: evidence/…/38f32b0260415d625c245820 |
| 4 | `d9d800393d95` | Blocker seed-only clone (seat 3 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2292 | 144 | 0 | archive: evidence/…/85de8d708dc60fe05db9b85c |
| 5 | `a35c2c481164` | Racer (novel-b) | novel-b | novel-b core (Blocker/Racer/Feint) | finals | 2.2639 | 144 | 0 | tester_bots/racer.py @ 36275b7 |
| 6 | `88496d239f5d` | Blocker seed-only clone (seat 4 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2153 | 144 | 0 | archive: evidence/…/a2fe750349a9bd2f3bcb01cf |
| 7 | `047ed5d8391e` | Racer seed-only clone (seat 2 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2431 | 144 | 0 | archive: evidence/…/fb3ed1dc2c8d66588aaa302b |
| 8 | `f5e870cd8bb5` | Blocker + public-memory patch (strategy_candidates/) | own-lineage | novel-b core (Blocker/Racer/Feint) | finals | 2.2083 | 144 | 0 | strategy_candidates/blocker_public_memory.py @ 7c0fe92 |
| 9 | `1bb70109a75e` | Blocker (novel-b) | novel-b | novel-b core (Blocker/Racer/Feint) | finals | 2.2153 | 144 | 0 | tester_bots/blocker.py @ 36275b7 |
| 10 | `f95dc9fc2266` | Feint (novel-b) | novel-b | novel-b core (Blocker/Racer/Feint) | finals | 2.2083 | 144 | 0 | confirmation_campaign/evidence/architectures_v2/feint_original.py @ 36275b7 |
| 11 | `191059b37141` | Blocker seed-only clone (seat 1 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2083 | 144 | 0 | archive: evidence/…/332f38a76d36586855a808a9 |
| 12 | `b9e2f84869a4` | Blocker seed-only clone (seat 1 reseeded) | evolved-genome | novel-b core (Blocker/Racer/Feint) | finals | 2.2083 | 144 | 0 | archive: evidence/…/423c052840c68eded42ad061 |
| 13 | `def6a8585f26` | main-bot CONFIG variant mutation_01 (evolution league) | evolved-genome | guarded Transfer (current main family) | finals | 2.1146 | 144 | 0 | archive: evidence/…/mutation_01.py |
| 14 | `8e84ff655452` | main-bot CONFIG variant fa9d68 (evolution league) | evolved-genome | guarded Transfer (current main family) | finals | 2.1458 | 144 | 0 | archive: evidence/…/fa9d68b71887396739904cd1 |
| 15 | `4737b8184da3` | main-bot CONFIG variant mutation_03 (evolution league) | evolved-genome | guarded Transfer (current main family) | finals | 2.0729 | 144 | 0 | archive: evidence/…/mutation_03.py |
| 16 | `d75575389253` | novel_d_shieldmaster (PR10 novel-d) | novel-d | novel-d | finals | 2.2292 | 144 | 0 | archive: validation/…/d75575389253.py |
| 17 | `18c0316f3250` | hx_steady persona (zenith/lab/humanlike) | own-lineage | other #53 | finals | 2.0521 | 144 | 0 | zenith/lab/humanlike/hx_steady.py @ c3dfbfd |
| 18 | `5f1bb9f70aac` | Zenith | own-lineage | Apex/Zenith exact-copy predictor | finals | 2.1528 | 144 | 0 | zenith/zenith_bot.py @ c3dfbfd |
| 19 | `e8b3682d8b39` | CURRENT main bot.py (guarded Transfer, STAY-only) | evolved-genome | guarded Transfer (current main family) | finals | 2.0139 | 144 | 0 | bot.py @ a89feac (2026-11-08) … 15 commits; root bot.py at head of: main |
| 20 | `a8f7a74e7ed3` | UltimateBot | own-lineage | other #32 | finals | 1.8403 | 144 | 0 | tester_bots/ultimate.py, ultimate.py @ b926add |
| 21 | `581791066105` | 7125545dbc07a83c6071f8369e3c1f854c328fbdbb393e247c1729619eb2fbe2.py | evolved-genome | guarded Transfer (current main family) | R3 | 2.0486 | 144 | 0 | archive: evidence/…/7125545dbc07a83c6071f836 |
| 22 | `aef27c1c5d6c` | human_arena/release/bot.py | own-lineage | presence Transfer | R3 | 2.0417 | 144 | 0 | human_arena/candidates/transfer_presence_core.py, human_arena/release/bot.py @ 9df9497 |
| 23 | `1edc9d0c2693` | mutation_02 | evolved-genome | guarded Transfer (current main family) | R3 | 2.0417 | 144 | 0 | archive: evidence/…/mutation_02.py |
| 24 | `8768c232dfa2` | discovery_finalist | evolved-genome | guarded Transfer (current main family) | R3 | 2.0382 | 144 | 0 | archive: evidence/…/discovery_finalist.py |
| 25 | `dd26262ba90b` | stay_guarded | archived-variant | guarded Transfer (current main family) | R3 | 2.0278 | 144 | 0 | archive: official/…/stay_guarded.py |
| 26 | `2444d1714498` | 87d682c02be96f4a3e7dbb4d79dc62ca7351d9b2fbf75494cfba411d5554de00.py | evolved-genome | guarded Transfer (current main family) | R3 | 2.0174 | 144 | 0 | archive: evidence/…/87d682c02be96f4a3e7dbb4d |
| 27 | `c54bc17924ba` | f3534dbfd7c25813bb60d9352ccc7668bfef19810988c274b278dd0cca0a0fea.py | evolved-genome | guarded Transfer (current main family) | R3 | 2.0139 | 144 | 0 | archive: evidence/…/f3534dbfd7c25813bb60d935 |
| 28 | `fc00af81fdf7` | root bot.py [presence_guarded] | own-lineage | presence guarded | R3 | 2.0139 | 144 | 0 | bot.py @ 36275b7 (2026-11-08) … 3 commits |
| 29 | `905ec235d18a` | offspring_03.py | evolved-genome | guarded Transfer (current main family) | R3 | 2.0104 | 144 | 0 | archive: evidence/…/offspring_03.py |
| 30 | `26736ce075cb` | evolution/availability_candidates/arrival_and_availability.py | own-lineage | guarded Transfer (current main family) | R3 | 2.0069 | 144 | 0 | evolution/availability_candidates/arrival_and_availability.py @ 3ee22b2 |
| 31 | `9b70ead68aef` | evolution/availability_candidates/availability_only.py | own-lineage | guarded Transfer (current main family) | R3 | 2.0069 | 144 | 0 | evolution/availability_candidates/availability_only.py @ 3ee22b2 |
| 32 | `fe03b8164ed3` | Transfer (previous release) | own-lineage | presence Transfer | R3 | 2.0000 | 144 | 0 | human_arena/candidates/transfer_fixed.py, human_arena/release/archive/fe03b8164ed3b4ebd2a04abcdfbb6fa729bdc34d |
| 33 | `0ae328cd6849` | mutation_04 | evolved-genome | guarded Transfer (current main family) | R3 | 2.0000 | 144 | 0 | archive: evidence/…/mutation_04.py |
| 34 | `80b1095ceea4` | offspring_02.py | evolved-genome | guarded Transfer (current main family) | R3 | 2.0000 | 144 | 0 | archive: evidence/…/offspring_02.py |
| 35 | `50d82d7ac581` | Defense-tuned Transfer (50d, evolved from main bot) | evolved-genome | guarded Transfer (current main family) | R3 | 1.9931 | 144 | 0 | archive: 2026-11-09-runtime-checks/…/50d82d7ac58162e9cf651136 |
| 36 | `5c79f7aad73d` | mutation_06 | evolved-genome | guarded Transfer (current main family) | R3 | 1.9931 | 144 | 0 | archive: evidence/…/mutation_06.py |
| 37 | `801e12ab6063` | evolution/mathematical_candidates/arrival_lifetime.py | own-lineage | guarded Transfer (current main family) | R3 | 1.9861 | 144 | 0 | evolution/mathematical_candidates/arrival_lifetime.py @ 482ef54 |
| 38 | `747b732ef32a` | evolution/mathematical_candidates/baseline_depth2.py | own-lineage | guarded Transfer (current main family) | R3 | 1.9826 | 144 | 0 | evolution/mathematical_candidates/baseline_depth2.py @ 482ef54 |
| 39 | `78e6919475de` | novel_c_bloomer | novel-c | novel-c | R3 | 1.9792 | 144 | 0 | archive: validation/…/78e6919475de.py |
| 40 | `48a3b05a88b2` | 509bfc28b8f535a4ef1cb9b657a87158e0563e02a7d5fa3871357d734d0011e5.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.9757 | 144 | 0 | archive: evidence/…/509bfc28b8f535a4ef1cb9b6 |
| 41 | `3a64f9d476a1` | evolution/mathematical_candidates/arrival_lifetime_depth2.py | own-lineage | guarded Transfer (current main family) | R3 | 1.9757 | 144 | 0 | evolution/mathematical_candidates/arrival_lifetime_depth2.py @ 482ef54 |
| 42 | `2f2e047f4532` | bcde2db5b35775249054b4bda0e8c1aeb33e723c140375e98afb05e9d42f0b53.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.9722 | 144 | 0 | archive: evidence/…/bcde2db5b35775249054b4bd |
| 43 | `2ffec027ad86` | 4c9bfe331cb0c3822d48a301a7ab8f664e2de691e51bb02c621c8dde40695ace.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.9688 | 144 | 0 | archive: evidence/…/4c9bfe331cb0c3822d48a301 |
| 44 | `279d42800a00` | offspring_07.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.9688 | 144 | 0 | archive: evidence/…/offspring_07.py |
| 45 | `aaafdc0ea897` | bot_transfer_candidate.py | archived-variant | Transfer / evolved economic planner | R3 | 1.9514 | 144 | 0 | archive: outputs/…/bot_transfer_candidate.p |
| 46 | `5c9fc5cf6b0e` | novel_c_voronoi | novel-c | novel-c | R3 | 1.9479 | 144 | 0 | archive: validation/…/5c9fc5cf6b0e.py |
| 47 | `93be90676285` | d6b0712e7a313d814471de7f9e1fe41ea28541cf01707bb2db4e39621a10d34a.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.9444 | 144 | 0 | archive: evidence/…/d6b0712e7a313d814471de7f |
| 48 | `5457b5fdf4ca` | Transfer (original) | own-lineage | Transfer / evolved economic planner | R3 | 1.9375 | 144 | 0 | crossfield/bots/evolved_transfer.py, human_arena/candidates/branch_5457b5fdf4ca.py, outputs/bot_transfer_candi |
| 49 | `641c909b7ef1` | Apex (counter-player) | own-lineage | Apex/Zenith exact-copy predictor | R3 | 1.9306 | 144 | 0 | apex/apex_bot.py, tester_bots/apex.py @ 92abafb |
| 50 | `35f76a6d091d` | mutation_07 | evolved-genome | guarded Transfer (current main family) | R3 | 1.9306 | 144 | 0 | archive: evidence/…/mutation_07.py |
| 51 | `6f2ac1487cd0` | Guarded research alternative | own-lineage | guarded Transfer (current main family) | R3 | 1.9097 | 144 | 0 | tester_bots/research_alternative.py @ a89feac |
| 52 | `1a718fd8b514` | human_arena/candidates/research_fixed.py | own-lineage | presence Transfer | R3 | 1.9097 | 144 | 0 | human_arena/candidates/research_fixed.py @ 9df9497 |
| 53 | `d8255047f77a` | presence_legacy_pricing | archived-variant | presence guarded | R3 | 1.8958 | 144 | 0 | archive: validation/…/presence_legacy_pricing. |
| 54 | `a5967c136bea` | stay_guarded_research | archived-variant | guarded Transfer (current main family) | R3 | 1.8889 | 144 | 0 | archive: official/…/stay_guarded_research.py |
| 55 | `03470e6151e5` | human_arena/candidates/transfer_presence.py | own-lineage | presence Transfer | R3 | 1.8854 | 144 | 0 | human_arena/candidates/transfer_presence.py @ 9df9497 |
| 56 | `ae807b1789e4` | af7f93db2cd4e2b81be8cf545e01a515816bf9c20150bf16d154507793c4979b.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.8854 | 144 | 0 | archive: evidence/…/af7f93db2cd4e2b81be8cf54 |
| 57 | `67e5e048ab10` | cb4ad645b2358d5e61ba68c2a3960c8842a9673923214c64d22157d85c0f6498.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.8854 | 144 | 0 | archive: evidence/…/cb4ad645b2358d5e61ba68c2 |
| 58 | `5a859ef134f1` | research_archive | evolved-genome | guarded Transfer (current main family) | R3 | 1.8819 | 144 | 0 | archive: evidence/…/research_archive.py |
| 59 | `8c0a5e14a664` | 7bad0473a439168a784f273c7ce215a49c00037fda867a2826303b9c83dcff4c.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.8819 | 144 | 0 | archive: evidence/…/7bad0473a439168a784f273c |
| 60 | `cb30b5ae32f7` | root bot.py | own-lineage | mybot beam planner (v6-v9) | R3 | 1.8681 | 144 | 0 | bot.py @ 6b69844 (2026-11-07) … 4 commits |
| 61 | `6e27ae1ba18b` | zenith/lab/humanlike/hx_cdsnipe.py | own-lineage | other #50 | R3 | 1.8611 | 144 | 0 | zenith/lab/humanlike/hx_cdsnipe.py @ c3dfbfd |
| 62 | `87064c997148` | offspring_06.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.8472 | 144 | 0 | archive: evidence/…/offspring_06.py |
| 63 | `b02fa600a52b` | b02fa600a52b1d746f38568ca07428b89f833149d05cd52fcbe66a47f69fc2ec.py | archived-variant | generated 'Player' opponent | R3 | 1.8333 | 144 | 0 | archive: architectures_v2/…/b02fa600a52b1d746f38568c |
| 64 | `4cbe78f5d941` | db22f46555cd5e4f03831c2254753e674ea4dd1aaf4ab02795012b99d0c58bd7.py | evolved-genome | guarded Transfer (current main family) | R3 | 1.8160 | 144 | 0 | archive: evidence/…/db22f46555cd5e4f03831c22 |
| 65 | `3c449e70ae24` | offspring_05.py | evolved-genome | guarded Transfer (current main family) | R2 | 1.8229 | 48 | 0 | archive: evidence/…/offspring_05.py |
| 66 | `cefe2fa7bce1` | root bot.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.8125 | 48 | 0 | bot.py @ 6aaa644 (2026-11-07) … 2 commits |
| 67 | `07ccfe799139` | cbf75bfc7b7087b84a695c2c6e9d65b43b217a0b2a6f6a30df0953ce6014fa38.py | evolved-genome | guarded Transfer (current main family) | R2 | 1.8125 | 48 | 0 | archive: evidence/…/cbf75bfc7b7087b84a695c2c |
| 68 | `6500bf5f5572` | offspring_04.py | evolved-genome | guarded Transfer (current main family) | R2 | 1.8125 | 48 | 0 | archive: evidence/…/offspring_04.py |
| 69 | `bc45f38be7c9` | root mybot.py (dev source) | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7917 | 48 | 0 | mybot.py @ 223358b (2026-11-06) … 3 commits |
| 70 | `96b43862335f` | mybot.py | archived-variant | mybot beam planner (v6-v9) | R2 | 1.7917 | 48 | 0 | archive: outputs/…/mybot.py |
| 71 | `ef5d88a22a3d` | root mybot.py (dev source) | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7917 | 48 | 0 | mybot.py @ 668be6b (2026-11-06) |
| 72 | `3927b1a0ccb6` | 3927b1a0ccb6e6288803160ba6511c28cf89119aaca6df720617675cc66f02f4.py | archived-variant | other #24 | R2 | 1.7917 | 48 | 0 | archive: architectures_v2/…/3927b1a0ccb6e6288803160b |
| 73 | `aa49608fe334` | root bot.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7917 | 48 | 0 | bot.py @ 961e729 (2026-11-07) … 15 commits; root bot.py at head of: hardened-field-and-fixes |
| 74 | `f7b40080a522` | f7b40080a522.py | archived-variant | PR10 v9 forecast planner | R2 | 1.7917 | 48 | 0 | archive: validation/…/f7b40080a522.py |
| 75 | `b958ac3dcdd1` | root mybot.py (dev source) | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7917 | 48 | 0 | mybot.py @ c7cbaa9 (2026-11-06) |
| 76 | `a40334b3209c` | pr10_novel_v9 | archived-variant | PR10 v9 forecast planner | R2 | 1.7917 | 48 | 0 | archive: validation/…/pr10_novel_v9.py |
| 77 | `72ee6ee5b05d` | mybot.py | archived-variant | mybot beam planner (v3-v7) | R2 | 1.7917 | 48 | 0 | archive: outputs/…/mybot.py |
| 78 | `22292913578c` | root bot.py | own-lineage | Fusion (econ + beam fallback) | R2 | 1.7812 | 48 | 0 | bot.py @ d31fff2 (2026-11-07) … 4 commits |
| 79 | `66ed85892834` | fusion.py | own-lineage | fusion source | R2 | 1.7812 | 48 | 0 | fusion.py @ d31fff2 |
| 80 | `437cf7ee6631` | fusion.py | own-lineage | fusion source | R2 | 1.7812 | 48 | 0 | fusion.py @ ed708f3 |
| 81 | `b2de2f334e88` | root bot.py | own-lineage | Fusion (econ + beam fallback) | R2 | 1.7812 | 48 | 0 | bot.py @ ed708f3 (2026-11-08) … 7 commits; root bot.py at head of: claude/amazing-fermat-yiicr8, claude/eager- |
| 82 | `fe71fcc6a821` | evolved_reference.py | archived-variant | Transfer / evolved economic planner | R2 | 1.7812 | 48 | 0 | archive: outputs/…/evolved_reference.py |
| 83 | `720e5a3daf7b` | Fusion (fused economic planner) | own-lineage | Fusion (econ + beam fallback) | R2 | 1.7812 | 48 | 0 | bot.py @ 13cd215 (2026-11-08) … 2 commits |
| 84 | `1dca0c916af4` | root bot.py | own-lineage | Transfer / evolved economic planner | R2 | 1.7812 | 48 | 0 | bot.py @ 0796039 (2026-11-07); root bot.py at head of: research/evolution-2026-11-07 |
| 85 | `7546b589da81` | root mybot.py (dev source) | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | mybot.py @ 13cd215 (2026-11-08) … 2 commits |
| 86 | `86180a765ed7` | root mybot.py (dev source) | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | mybot.py @ 5fae6ab (2026-11-07) … 16 commits |
| 87 | `707a3856b372` | audit/ablation_progress.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_progress.py @ 6aaa644 |
| 88 | `95da830e6f29` | human_arena/candidates/forward_fixed.py | own-lineage | futurelab forward-sim | R2 | 1.7708 | 48 | 0 | human_arena/candidates/forward_fixed.py @ 9df9497 |
| 89 | `a5098d62e1c2` | audit/ablation_frame.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_frame.py @ 6aaa644 |
| 90 | `f7ec724c1473` | root mybot.py (dev source) | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | mybot.py @ 6aaa644 (2026-11-07) … 6 commits |
| 91 | `64b90e9c676b` | 64b90e9c676b1a28cb001e7e836339646ca62bd226732b0abeb2e2062a97bc8f.py | archived-variant | PR10 v9 forecast planner | R2 | 1.7708 | 48 | 0 | archive: architectures_v2/…/64b90e9c676b1a28cb001e7e |
| 92 | `d2bef4e077e9` | futurelab/submission/bot.py | own-lineage | futurelab forward-sim | R2 | 1.7708 | 48 | 0 | futurelab/submission/bot.py, human_arena/candidates/forward_original.py, human_arena/candidates/root_v9.py @ 0 |
| 93 | `3b6c88228780` | zenith/lab/humanlike/hx_sniper.py | own-lineage | other #52 | R2 | 1.7708 | 48 | 0 | zenith/lab/humanlike/hx_sniper.py @ c3dfbfd |
| 94 | `ee98dcfe0ef9` | root mybot.py (dev source) | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | mybot.py @ d31fff2 (2026-11-07) … 11 commits |
| 95 | `59e3f210b3e7` | audit/ablation_priority.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_priority.py @ 6aaa644 |
| 96 | `ab877f76399d` | root mybot.py (dev source) | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | mybot.py @ a59cb1d (2026-11-07) |
| 97 | `97d571b0ce5c` | root bot.py | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7708 | 48 | 0 | bot.py @ 668be6b (2026-11-06) |
| 98 | `c137e917334d` | audit/ablation_income.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_income.py @ 6aaa644 |
| 99 | `c5baa1169b8e` | c5baa1169b8e4b2e4b4436c0bcae8f00c13ea3be5a006785a4db93767c89c1e5.py | archived-variant | PR10 v9 forecast planner | R2 | 1.7708 | 48 | 0 | archive: architectures_v2/…/c5baa1169b8e4b2e4b4436c0 |
| 100 | `2beb1c803986` | audit/ablation_workgain.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_workgain.py @ 6aaa644 |
| 101 | `8746e19a96c6` | audit/ablation_defence.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7708 | 48 | 0 | audit/ablation_defence.py @ 6aaa644 |
| 102 | `6517c92b65e4` | human_arena/candidates/transfer_presence_noentry.py | own-lineage | presence Transfer | R2 | 1.7708 | 48 | 0 | human_arena/candidates/transfer_presence_noentry.py @ 9df9497 |
| 103 | `dd39989caef8` | action_beam.py | archived-variant | other #28 | R2 | 1.7604 | 48 | 0 | archive: outputs/…/action_beam.py |
| 104 | `f995547a68e7` | crossfield/research/action_beam.py | own-lineage | other #28 | R2 | 1.7604 | 48 | 0 | crossfield/research/action_beam.py @ d31fff2 |
| 105 | `942948a119bf` | user_corrected.py | archived-variant | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | archive: outputs/…/user_corrected.py |
| 106 | `6ebdfb1d64c8` | bot.py | archived-variant | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | archive: outputs/…/bot.py |
| 107 | `cd0f4ede2caa` | user_recovery.py | archived-variant | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | archive: outputs/…/user_recovery.py |
| 108 | `8ae6c29de483` | audit/ablation_idle.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.7500 | 48 | 0 | audit/ablation_idle.py @ 6aaa644 |
| 109 | `e11eea58b1c2` | user_family.py | archived-variant | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | archive: outputs/…/user_family.py |
| 110 | `beec3a70b4e6` | root bot.py | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | bot.py @ 223358b (2026-11-06) … 3 commits; root bot.py at head of: visual-harness |
| 111 | `dfc547464ff2` | crossfield/research/user_family.py | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | crossfield/research/user_family.py @ d31fff2 |
| 112 | `6abf403ab207` | user_development_002.py | archived-variant | mybot beam planner (v6-v9) | R2 | 1.7500 | 48 | 0 | archive: outputs/…/user_development_002.py |
| 113 | `871082906a3d` | 871082906a3dfbcf03d7464f47ce40a9b9dc741b4f4f8a369e9d2039f8fe6a18.py | archived-variant | generated 'Player' opponent | R2 | 1.7500 | 48 | 0 | archive: architectures_v2/…/871082906a3dfbcf03d7464f |
| 114 | `f6b4385da8e0` | outputs/bot_user_corrected.py | own-lineage | mybot beam planner (v3-v7) | R2 | 1.7500 | 48 | 0 | human_arena/candidates/branch_f6b4385da8e0.py, outputs/bot_user_corrected.py @ 0796039 |
| 115 | `ec0c2d6afb24` | zenith/lab/humanlike/hx_mixed.py | own-lineage | other #51 | R2 | 1.7500 | 48 | 0 | zenith/lab/humanlike/hx_mixed.py @ c3dfbfd |
| 116 | `ae1594276aff` | human_arena/candidates/research_correctness.py | own-lineage | presence Transfer | R2 | 1.7188 | 48 | 0 | human_arena/candidates/research_correctness.py @ 9df9497 |
| 117 | `c09b3363418e` | novel_c_portfolio | novel-c | novel-c | R2 | 1.7083 | 48 | 0 | archive: validation/…/c09b3363418e.py |
| 118 | `825a695c56bf` | novel_d_antileader | novel-d | novel-d | R2 | 1.6875 | 48 | 0 | archive: validation/…/825a695c56bf.py |
| 119 | `34831f175665` | 34831f1756657707447b46e2690da739e6f6b41faeb4707c4928160fe6eeed54.py | archived-variant | generated 'Player' opponent | R2 | 1.6667 | 48 | 0 | archive: architectures_v2/…/34831f1756657707447b46e2 |
| 120 | `7793268599f4` | 7793268599f429615bcee6b2b5c01207fd57c085e5d26c46ee6244ff697e9951.py | archived-variant | generated 'Player' opponent | R2 | 1.6458 | 48 | 0 | archive: architectures_v2/…/7793268599f429615bcee6b2 |
| 121 | `6b9c0dd20ad9` | root bot.py | own-lineage | mybot beam planner (v6-v9) | R2 | 1.6458 | 48 | 0 | bot.py @ 5fae6ab (2026-11-07) … 2 commits |
| 122 | `31965e1412c6` | root bot.py | own-lineage | mybot beam planner (v3-v7) | R2 | 1.6250 | 48 | 0 | bot.py @ c7cbaa9 (2026-11-06); root bot.py at head of: v7-independent-field |
| 123 | `a7443c0cab8b` | beam.py | archived-variant | other #42 | R2 | 1.6250 | 48 | 0 | archive: outputs/…/beam.py |
| 124 | `506ac60b6a7b` | 506ac60b6a7b3406f60c214f403e7618923040476f6310997f09226f796aafc9.py | archived-variant | generated 'Player' opponent | R2 | 1.6250 | 48 | 0 | archive: architectures_v2/…/506ac60b6a7b3406f60c214f |
| 125 | `68094583daf8` | human_arena/candidates/forward_presence.py | own-lineage | futurelab forward-sim | R2 | 1.6042 | 48 | 0 | human_arena/candidates/forward_presence.py @ 9df9497 |
| 126 | `9f03b1bbb4e5` | pr10_presence_forecast | archived-variant | PR10 v9 forecast planner | R2 | 1.6042 | 48 | 0 | archive: validation/…/pr10_presence_forecast.p |
| 127 | `0ae0b109d85b` | novel_0ae0b109d85b | novel-opponent | generated 'Player' opponent | R2 | 1.6042 | 48 | 0 | archive: architectures_v2/…/0ae0b109d85bc986a47703fc |
| 128 | `bec1daf8bb0c` | human_arena/candidates/research_presence.py | own-lineage | presence Transfer | R2 | 1.5938 | 48 | 0 | human_arena/candidates/research_presence.py @ 9df9497 |
| 129 | `7de1792bb1be` | 7de1792bb1beadd8acc3b97f7290966253cc3689b7db611c21fe129b7258bc6e.py | archived-variant | generated 'Player' opponent | R2 | 1.5833 | 48 | 0 | archive: architectures_v2/…/7de1792bb1beadd8acc3b97f |
| 130 | `0cd7e175e625` | 0cd7e175e6251baec478a74abd9fd5eed3ef5421b6d8467bafcda571f8864bf9.py | archived-variant | generated 'Player' opponent | R2 | 1.5833 | 48 | 0 | archive: architectures_v2/…/0cd7e175e6251baec478a74a |
| 131 | `51af74779331` | zenith/lab/humanlike/hx_bait.py | own-lineage | other #49 | R2 | 1.5625 | 48 | 0 | zenith/lab/humanlike/hx_bait.py @ c3dfbfd |
| 132 | `b59fc9333499` | b59fc933349956f61fbb0f2cf2741dbbd9cd0dd88e56670c29fd39a947889439.py | archived-variant | generated 'Player' opponent | R2 | 1.5625 | 48 | 0 | archive: architectures_v2/…/b59fc933349956f61fbb0f2c |
| 133 | `c14f37ef30b1` | c14f37ef30b14647063b967970f88b5e87d41ae5db3ddf1e6f84ec4e245b7516.py | archived-variant | generated 'Player' opponent | R2 | 1.5625 | 48 | 0 | archive: architectures_v2/…/c14f37ef30b14647063b9679 |
| 134 | `11d51e76737c` | tactical.py | archived-variant | other #27 | R2 | 1.5208 | 48 | 0 | archive: outputs/…/tactical.py |
| 135 | `97df8781064e` | 97df8781064edacff0d31e9182f86a09e9db331d33a8711071e25822544e05ca.py | archived-variant | generated 'Player' opponent | R2 | 1.5208 | 48 | 0 | archive: architectures_v2/…/97df8781064edacff0d31e91 |
| 136 | `27c2b068fb86` | crossfield/research/adversary.py | own-lineage | other #44 | R2 | 1.5208 | 48 | 0 | crossfield/research/adversary.py @ 0796039 |
| 137 | `2388ad499944` | crossfield/research/tactical.py | own-lineage | other #27 | R2 | 1.5208 | 48 | 0 | crossfield/research/tactical.py @ d31fff2 |
| 138 | `b6fa23cc5ee7` | b6fa23cc5ee71eeb1359623e6cf855944cedc36e85cb0afd672dbdee57f15e0f.py | archived-variant | generated 'Player' opponent | R2 | 1.5208 | 48 | 0 | archive: architectures_v2/…/b6fa23cc5ee71eeb1359623e |
| 139 | `ff7bba59cb54` | economic.py | archived-variant | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | archive: outputs/…/economic.py |
| 140 | `34bdf1bab1bb` | crossfield/research/economic.py | own-lineage | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | crossfield/research/economic.py @ d31fff2 |
| 141 | `0043b4985ad8` | novel_0043b4985ad8 | novel-opponent | generated 'Player' opponent | R2 | 1.4792 | 48 | 0 | archive: architectures_v2/…/0043b4985ad87db40953474b |
| 142 | `a03097e1ac56` | bot_audited.py | archived-variant | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | archive: outputs/…/bot_audited.py |
| 143 | `981a4f906ea8` | bot_recovery.py | archived-variant | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | archive: outputs/…/bot_recovery.py |
| 144 | `111a2261c2d9` | 111a2261c2d94cc739c5aea2cc358f3505fd93b0a6765325a9a76f4f86a3278b.py | archived-variant | generated 'Player' opponent | R2 | 1.4792 | 48 | 0 | archive: architectures_v2/…/111a2261c2d94cc739c5aea2 |
| 145 | `8aa7cffb6edd` | novel_8aa7cffb6edd | novel-opponent | generated 'Player' opponent | R2 | 1.4792 | 48 | 0 | archive: architectures_v2/…/8aa7cffb6edd2ce663b1934d |
| 146 | `630bfa2034a7` | incumbent.py | archived-variant | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | archive: outputs/…/incumbent.py |
| 147 | `bbff919db34a` | outputs/bot_before_evolution.py | own-lineage | Transfer / evolved economic planner | R2 | 1.4792 | 48 | 0 | crossfield/research/incumbent.py, human_arena/candidates/branch_bbff919db34a.py, outputs/bot_before_evolution. |
| 148 | `21ad42099805` | 21ad420998051815407a9c697cef9fb68684fb3e054800b759810597e8b3df7c.py | archived-variant | generated 'Player' opponent | R2 | 1.4583 | 48 | 0 | archive: architectures_v2/…/21ad420998051815407a9c69 |
| 149 | `f158838067bd` | f158838067bdd9a42dcc27fbf43c7290edaefd8b374fe73dd65b3583be3565ac.py | archived-variant | generated 'Player' opponent | R2 | 1.4583 | 48 | 0 | archive: architectures_v2/…/f158838067bdd9a42dcc27fb |
| 150 | `f97b990798c2` | novel_f97b990798c2 | novel-opponent | generated 'Player' opponent | R2 | 1.4375 | 48 | 0 | archive: architectures_v2/…/f97b990798c25c4ba398debc |
| 151 | `92f38af1a559` | Evolved league genome 92f38a | evolved-genome | guarded Transfer (current main family) | R2 | 1.4375 | 48 | 0 | archive: evidence/…/c5b5f1bcad3a4750f41d9fa2 |
| 152 | `3d8b48404f35` | 3d8b48404f354fbcc3c0c66f8825b2adb667ed958f2ac8b13c46321872174fd7.py | archived-variant | generated 'Player' opponent | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/3d8b48404f354fbcc3c0c66f |
| 153 | `a8e848b6ff71` | novel_a8e848b6ff71 | novel-opponent | generated 'Player' opponent | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/a8e848b6ff71b4c596d99d90 |
| 154 | `84043e975773` | 84043e97577386dfd7c2c8905819e6f78685a7e21a76b9f72fb36635c7b88a82.py | archived-variant | other #10 | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/84043e97577386dfd7c2c890 |
| 155 | `4afed62b2742` | 4afed62b2742d83822d03ba5de7b2e26b19d2a36e1e6eb4ec076ae701132c657.py | archived-variant | generated 'Player' opponent | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/4afed62b2742d83822d03ba5 |
| 156 | `8681c7a36c68` | novel_8681c7a36c68 | novel-opponent | generated 'Player' opponent | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/8681c7a36c68fdff64099f95 |
| 157 | `5440ec2b2b1b` | novel_5440ec2b2b1b | novel-opponent | generated 'Player' opponent | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/5440ec2b2b1b00e5efb4ae08 |
| 158 | `edee7e6993e1` | edee7e6993e1198af189402d99770338d73ade8dc42c9a950f76de2ca49e80ce.py | archived-variant | other #10 | R2 | 1.4167 | 48 | 0 | archive: architectures_v2/…/edee7e6993e1198af189402d |
| 159 | `a7f802535916` | novel_a7f802535916 | novel-opponent | generated 'Player' opponent | R2 | 1.4062 | 48 | 0 | archive: architectures_v2/…/a7f802535916e06b25d4c65c |
| 160 | `fdb41d502267` | planner_beam.py | archived-variant | other #15 | R2 | 1.3958 | 48 | 0 | archive: outputs/…/planner_beam.py |
| 161 | `d0163fa3982f` | d0163fa3982f6817e410617d3831f8bd8e5a72c9acc13552727cfbcea6d1ada3.py | archived-variant | generated 'Player' opponent | R2 | 1.3958 | 48 | 0 | archive: architectures_v2/…/d0163fa3982f6817e410617d |
| 162 | `5d887fd38c8f` | 5d887fd38c8f631d6993d153b68f265316626b9f11472bcea0d148e1f85d185f.py | archived-variant | generated 'Player' opponent | R2 | 1.3958 | 48 | 0 | archive: architectures_v2/…/5d887fd38c8f631d6993d153 |
| 163 | `7773ed52b9b8` | 7773ed52b9b89f3f6159c88b866debbdd46d786932ea0ace72b30df03457e9b0.py | archived-variant | other #9 | R2 | 1.3958 | 48 | 0 | archive: architectures_v2/…/7773ed52b9b89f3f6159c88b |
| 164 | `f00d152aebaa` | f00d152aebaa49a4747960cedd53d900d6344316511cd425b55960b11f55d3bb.py | archived-variant | generated 'Player' opponent | R2 | 1.3958 | 48 | 0 | archive: architectures_v2/…/f00d152aebaa49a4747960ce |
| 165 | `e7f4fd616c15` | crossfield/research/planner_beam.py | own-lineage | other #15 | R2 | 1.3958 | 48 | 0 | crossfield/research/planner_beam.py @ d31fff2 |
| 166 | `7f68ea184445` | novel_7f68ea184445 | novel-opponent | generated 'Player' opponent | R2 | 1.3958 | 48 | 0 | archive: architectures_v2/…/7f68ea1844450cf0bd88e616 |
| 167 | `f0c36af99230` | f0c36af99230851a8858fcfb9bce97208a81427de38fd6dee2610f06668bf717.py | archived-variant | other #9 | R2 | 1.3750 | 48 | 0 | archive: architectures_v2/…/f0c36af99230851a8858fcfb |
| 168 | `d80c53269044` | novel_d80c53269044 | novel-opponent | generated 'Player' opponent | R2 | 1.3750 | 48 | 0 | archive: architectures_v2/…/d80c53269044faeb9006e69e |
| 169 | `9203f00255d5` | crossfield/research/challengers.py | own-lineage | other #35 | R2 | 1.3750 | 48 | 0 | crossfield/research/challengers.py @ 0796039 |
| 170 | `47551115a012` | 47551115a0122cb36466b7068d016595f3e2dcc4d0739f3d0b7616e600f2c396.py | archived-variant | generated 'Player' opponent | R2 | 1.3750 | 48 | 0 | archive: architectures_v2/…/47551115a0122cb36466b706 |
| 171 | `9ce719252be7` | novel_9ce719252be7 | novel-opponent | generated 'Player' opponent | R2 | 1.3542 | 48 | 0 | archive: architectures_v2/…/9ce719252be76ae5b920922b |
| 172 | `b13164de32eb` | planner_adaptive.py | archived-variant | other #15 | R2 | 1.3542 | 48 | 0 | archive: outputs/…/planner_adaptive.py |
| 173 | `c3f7d36077ad` | c3f7d36077ad8bea61d6ac5e51429d7ac406c91e8337f6b3435739fbd741a52e.py | archived-variant | other #10 | R2 | 1.3542 | 48 | 0 | archive: architectures_v2/…/c3f7d36077ad8bea61d6ac5e |
| 174 | `fdb39165d7a8` | novel_fdb39165d7a8 | novel-opponent | generated 'Player' opponent | R2 | 1.3125 | 48 | 0 | archive: architectures_v2/…/fdb39165d7a89b74c5e3ca36 |
| 175 | `5451ead76bcb` | 5451ead76bcb85b76184fae184d38945aded3d1a51cdeb315cc00a7c2d63ccf3.py | archived-variant | generated 'Player' opponent | R2 | 1.3125 | 48 | 0 | archive: architectures_v2/…/5451ead76bcb85b76184fae1 |
| 176 | `71061537773b` | novel_71061537773b | novel-opponent | generated 'Player' opponent | R2 | 1.3125 | 48 | 0 | archive: architectures_v2/…/71061537773b8890d4bf4ed7 |
| 177 | `d5b6a11d3f62` | novel_d5b6a11d3f62 | novel-opponent | generated 'Player' opponent | R2 | 1.3125 | 48 | 0 | archive: architectures_v2/…/d5b6a11d3f623c70d1290d97 |
| 178 | `96036d2c3f19` | novel_96036d2c3f19 | novel-opponent | generated 'Player' opponent | R2 | 1.3125 | 48 | 0 | archive: architectures_v2/…/96036d2c3f19e6adc6870863 |
| 179 | `f9ebc7878ac1` | novel_d_titfortat | novel-d | novel-d | R2 | 1.3021 | 48 | 0 | archive: validation/…/f9ebc7878ac1.py |
| 180 | `96b41b6efe62` | planner_rules.py | archived-variant | Transfer / evolved economic planner | R2 | 1.2812 | 48 | 0 | archive: outputs/…/planner_rules.py |
| 181 | `b9d9e5ac8ec2` | novel_a_paranoid | novel-a | novel-a | R2 | 1.2708 | 48 | 0 | archive: validation/…/b9d9e5ac8ec2.py |
| 182 | `33a8f20e1220` | novel_33a8f20e1220 | novel-opponent | generated 'Player' opponent | R2 | 1.2708 | 48 | 0 | archive: architectures_v2/…/33a8f20e12206c504372bd32 |
| 183 | `b87478d47485` | novel_a_mcts | novel-a | novel-a | R2 | 1.2500 | 48 | 0 | archive: validation/…/b87478d47485.py |
| 184 | `a6c0c5abcded` | opponents/opp_raider_03.py | opponent-field | other #29 | R2 | 1.2500 | 48 | 0 | opponents/opp_raider_03.py @ b9e9751 |
| 185 | `710e79a95e37` | 710e79a95e37622aa0009fd01d9a42709da310bd6c057b0622454d27a88907bc.py | archived-variant | generated 'Player' opponent | R2 | 1.2083 | 48 | 0 | archive: architectures_v2/…/710e79a95e37622aa0009fd0 |
| 186 | `11045a993b06` | 11045a993b063465daa5571cee9ec876a37e1919cd9fb5d6dfe730f4fc5760e8.py | archived-variant | other #26 | R2 | 1.2083 | 48 | 0 | archive: architectures_v2/…/11045a993b063465daa5571c |
| 187 | `48ddea4c22e6` | novel_48ddea4c22e6 | novel-opponent | generated 'Player' opponent | R2 | 1.1875 | 48 | 0 | archive: architectures_v2/…/48ddea4c22e6652fcad49209 |
| 188 | `00ac96aaee71` | novel_00ac96aaee71 | novel-opponent | generated 'Player' opponent | R2 | 1.1875 | 48 | 0 | archive: architectures_v2/…/00ac96aaee71469af58fb8e2 |
| 189 | `b0b8349136f7` | novel_b0b8349136f7 | novel-opponent | generated 'Player' opponent | R2 | 1.1875 | 48 | 0 | archive: architectures_v2/…/b0b8349136f74a52dc8dd6ce |
| 190 | `f6226e4070ab` | f6226e4070ab430446cbc39c963dca8cb46426a816ad5c57f61c4373c11aafc7.py | archived-variant | generated 'Player' opponent | R2 | 1.1875 | 48 | 0 | archive: architectures_v2/…/f6226e4070ab430446cbc39c |
| 191 | `98c53339aac0` | zenith/lab/humanlike/hx_aggro.py | own-lineage | other #48 | R2 | 1.1667 | 48 | 0 | zenith/lab/humanlike/hx_aggro.py @ c3dfbfd |
| 192 | `9fa9d92c8246` | novel_9fa9d92c8246 | novel-opponent | generated 'Player' opponent | R2 | 1.1667 | 48 | 0 | archive: architectures_v2/…/9fa9d92c8246e6e353eeb6c2 |
| 193 | `835a2f3756a6` | 835a2f3756a654cd0960ec218e72ecc9b19ddb50ab0ab0913fd5d347d19f0c1e.py | archived-variant | generated 'Player' opponent | R2 | 1.1667 | 48 | 0 | archive: architectures_v2/…/835a2f3756a654cd0960ec21 |
| 194 | `bac67650a6e1` | novel_bac67650a6e1 | novel-opponent | generated 'Player' opponent | R2 | 1.1458 | 48 | 0 | archive: architectures_v2/…/bac67650a6e115393e963953 |
| 195 | `284f94f4e723` | 284f94f4e723713e8316476f426793cd451749fad001d69cb4c3d7aa4e19b2eb.py | archived-variant | generated 'Player' opponent | R2 | 1.1250 | 48 | 0 | archive: architectures_v2/…/284f94f4e723713e8316476f |
| 196 | `efb0b78a0797` | opponents/opp_adaptive_gpt1.py | opponent-field | simple act()-only bot | R2 | 1.1042 | 48 | 0 | opponents/opp_adaptive_gpt1.py @ 3be829a |
| 197 | `d2f10af60c92` | novel_d2f10af60c92 | novel-opponent | generated 'Player' opponent | R2 | 1.0833 | 48 | 0 | archive: architectures_v2/…/d2f10af60c9228b79f547aa7 |
| 198 | `6423f121fd54` | novel_6423f121fd54 | novel-opponent | generated 'Player' opponent | R2 | 1.0833 | 48 | 0 | archive: architectures_v2/…/6423f121fd5466c97e82b8dc |
| 199 | `c6c03f8b5e32` | c6c03f8b5e327050544b3b9d556433ae1ad4e545d856230cea3001d2727771c0.py | archived-variant | generated 'Player' opponent | R2 | 1.0625 | 48 | 0 | archive: architectures_v2/…/c6c03f8b5e327050544b3b9d |
| 200 | `c2ead1cf64c5` | novel_c2ead1cf64c5 | novel-opponent | generated 'Player' opponent | R2 | 1.0417 | 48 | 0 | archive: architectures_v2/…/c2ead1cf64c54ebae3218d88 |
| 201 | `bb2cf166a49f` | agent_new.py | own-lineage | other #34 | R2 | 0.0000 | 48 | 3840 | agent_new.py @ 668be6b |
| 202 | `aabbd479dd2f` | aabbd479dd2f8da3c48a9dd07b2d187a81c5bc6b71749cb7fd4b97427b219f4d.py | archived-variant | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/aabbd479dd2f8da3c48a9dd0 |
| 203 | `e60b6d8bbe3c` | novel_a_rhea | novel-a | novel-a | R1 | 1.1875 | 16 | 0 | archive: validation/…/e60b6d8bbe3c.py |
| 204 | `22badfa2ee55` | 22badfa2ee552e669db1095726c4afdd0a823441a6198ea6ff5d3839d07501aa.py | archived-variant | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/22badfa2ee552e669db10957 |
| 205 | `698feae1ef9d` | 698feae1ef9da4e69907b26d31652dad9355b13db67698f0597f3adc86c1e2f5.py | archived-variant | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/698feae1ef9da4e69907b26d |
| 206 | `8058dbdf93f2` | novel_8058dbdf93f2 | novel-opponent | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/8058dbdf93f267d2527d904d |
| 207 | `a6315448d671` | novel_a6315448d671 | novel-opponent | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/a6315448d67121a6f06c269e |
| 208 | `1bd939d99bfa` | 1bd939d99bfaf8e2638c152a3d021b4f843b27ec7551fa71fe832a5adf02f3ac.py | archived-variant | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/1bd939d99bfaf8e2638c152a |
| 209 | `89c1701caf18` | novel_89c1701caf18 | novel-opponent | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/89c1701caf181ab90694bba3 |
| 210 | `0412b54e3ab1` | 0412b54e3ab14211e6dc211472ffddb3b1ea2489ecac77c5115ddb5dc0085d2b.py | archived-variant | generated 'Player' opponent | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/0412b54e3ab14211e6dc2114 |
| 211 | `ede52321b2c5` | ede52321b2c567c8a5c7f2c48396ed1f2450d6d859e7fa5c3e3b53f793396b58.py | archived-variant | other #8 | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/ede52321b2c567c8a5c7f2c4 |
| 212 | `87f33c216193` | opponents/opp_greedy_gemini1.py | opponent-field | simple act()-only bot | R1 | 1.1875 | 16 | 0 | opponents/opp_greedy_gemini1.py @ 3be829a |
| 213 | `91d888bad7fc` | 91d888bad7fcf6a7246ac96ea9cb7badfb09f74261879e9c6b8428efeb2025df.py | archived-variant | other #8 | R1 | 1.1875 | 16 | 0 | archive: architectures_v2/…/91d888bad7fcf6a7246ac96e |
| 214 | `3a923b854cd9` | novel_3a923b854cd9 | novel-opponent | generated 'Player' opponent | R1 | 1.1562 | 16 | 0 | archive: architectures_v2/…/3a923b854cd9cae358f8a54f |
| 215 | `33915aab14af` | 33915aab14af4b716f8af275ec824062410830af331f94596b4cdaa310760313.py | archived-variant | generated 'Player' opponent | R1 | 1.1562 | 16 | 0 | archive: architectures_v2/…/33915aab14af4b716f8af275 |
| 216 | `5d4e77c1b40b` | 5d4e77c1b40b700076aeab39bbe0aabb6f35e236c977bde19aa52a0caea66e10.py | archived-variant | generated 'Player' opponent | R1 | 1.1562 | 16 | 0 | archive: architectures_v2/…/5d4e77c1b40b700076aeab39 |
| 217 | `a951d742bddc` | novel_a951d742bddc | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/a951d742bddc18b9884168cf |
| 218 | `a4a1690acb18` | a4a1690acb18674e3bc3568f4c6f7c988d81b083aeded9cf5802dc5696ac584f.py | archived-variant | other #9 | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/a4a1690acb18674e3bc3568f |
| 219 | `1d3d62f6e157` | novel_1d3d62f6e157 | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/1d3d62f6e15773af910c6bb6 |
| 220 | `648040760a86` | novel_648040760a86 | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/648040760a86106ccadb17f9 |
| 221 | `b4a5da4cce01` | b4a5da4cce01ae89c4fa4565e97a8cce01a80403a0ce77f86c79803fe6232526.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/b4a5da4cce01ae89c4fa4565 |
| 222 | `d268c510eb89` | d268c510eb893592d6b3f5a05520e342c16114a1d8dbacd67fe63c1093881c8d.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/d268c510eb893592d6b3f5a0 |
| 223 | `d83915ef371e` | novel_d83915ef371e | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/d83915ef371e6ed9ba77d40b |
| 224 | `ffaa2168c1b1` | novel_ffaa2168c1b1 | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/ffaa2168c1b1aecbbcece02a |
| 225 | `5a28fae12504` | novel_5a28fae12504 | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/5a28fae12504fb79adebe6a2 |
| 226 | `2bbe66748e55` | 2bbe66748e55086f7c891bf6a778294624c8bdb2159a5424af3658c157eaf7e6.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/2bbe66748e55086f7c891bf6 |
| 227 | `0e0e32a15c3b` | novel_0e0e32a15c3b | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/0e0e32a15c3bbb37423f3589 |
| 228 | `374872357480` | novel_374872357480 | novel-opponent | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/3748723574805b51704c9008 |
| 229 | `7e17afbb7d1d` | 7e17afbb7d1df9099a55d871844842a580f57f5adc31267a364d102d1d057d0b.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/7e17afbb7d1df9099a55d871 |
| 230 | `45d91a14843a` | 45d91a14843a7a79aa5b69d09f09b7ec5c9d40b4921087b5fa4364044a2806ea.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/45d91a14843a7a79aa5b69d0 |
| 231 | `84bb59a0fb04` | 84bb59a0fb046b0fe14256578413e7f5ad7f9f03ab58fc4981ee5b103e8cef4c.py | archived-variant | generated 'Player' opponent | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/84bb59a0fb046b0fe1425657 |
| 232 | `238790102d13` | 238790102d13451f5db99813deb27dc87b8fab3e5632cee568826575f69c1fa6.py | archived-variant | other #8 | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/238790102d13451f5db99813 |
| 233 | `e89042e60e73` | e89042e60e7393644df8ee166de074f0a81718d8903c3fe76db75f73be7475b4.py | archived-variant | other #8 | R1 | 1.1250 | 16 | 0 | archive: architectures_v2/…/e89042e60e7393644df8ee16 |
| 234 | `3ad8ac8c48a2` | opponents/opp_raider_gpt1.py | opponent-field | other #40 | R1 | 1.1250 | 16 | 0 | opponents/opp_raider_gpt1.py @ 0e8b4a9 |
| 235 | `417b8a675b38` | novel_417b8a675b38 | novel-opponent | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/417b8a675b3843b68edeaf7e |
| 236 | `d000ed1bd98f` | 5e9cd25c6f871cd3ccca52c8b252adcfd24011347ace749c7f14174648447763.py | evolved-genome | guarded Transfer (current main family) | R1 | 1.0625 | 16 | 0 | archive: evidence/…/5e9cd25c6f871cd3ccca52c8 |
| 237 | `8946856226c5` | 8946856226c5e6f5b76ee90289b115cbd9d36743e5627c1b256bb2d1d3e00a65.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/8946856226c5e6f5b76ee902 |
| 238 | `73bb5af62fb0` | novel_73bb5af62fb0 | novel-opponent | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/73bb5af62fb0e56625551d4c |
| 239 | `d09279b31adc` | d09279b31adc4bbd71480545a7b0c32083cb7630619cc581f962d47e00437e57.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/d09279b31adc4bbd71480545 |
| 240 | `911b744e2242` | 911b744e2242302c448c0c220993fc38bc0d2a99e65cacd2bcd61ca43fba64f7.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/911b744e2242302c448c0c22 |
| 241 | `b34daa045cf8` | novel_b34daa045cf8 | novel-opponent | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/b34daa045cf8b89c20569eff |
| 242 | `e8a9541449b7` | e8a9541449b79518fefce9bb4d8718e5f4cf383af34b8aa9620529d696ed67ef.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/e8a9541449b79518fefce9bb |
| 243 | `6e960d224ab5` | 6e960d224ab52a64738eed1e913570f4b5b221ee1113fdacc2a997b5ea612b78.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/6e960d224ab52a64738eed1e |
| 244 | `9bf1d8b01048` | novel_9bf1d8b01048 | novel-opponent | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/9bf1d8b01048c3a812a91bea |
| 245 | `3a05c56ef7f5` | novel_3a05c56ef7f5 | novel-opponent | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/3a05c56ef7f5a8eb6ffa2a95 |
| 246 | `254173bdebc5` | planner.py | archived-variant | other #15 | R1 | 1.0625 | 16 | 0 | archive: outputs/…/planner.py |
| 247 | `7162d1545fbf` | 7162d1545fbf58ef3f29035d6e4d460c71d1f2f3799aa390f7262dbc7e410b9d.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/7162d1545fbf58ef3f29035d |
| 248 | `33a7d6066aee` | 33a7d6066aee1ac27387f8e5bfa02eb3f861029b603be0c1b81367f20f630858.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/33a7d6066aee1ac27387f8e5 |
| 249 | `e7ea25fe8574` | e7ea25fe857482c34541cf739e8ec1eabb5290e191070af5cdf51cd1431a65ce.py | archived-variant | other #9 | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/e7ea25fe857482c34541cf73 |
| 250 | `180e7a921c02` | 180e7a921c02f5d85540a59442ece7b1dca377af3cf17ae1108f3aa2a564ac7a.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/180e7a921c02f5d85540a594 |
| 251 | `52546043ecc9` | 52546043ecc9e522cd8f71578897e6fa0591acd56976dce68edc80a84158a784.py | archived-variant | generated 'Player' opponent | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/52546043ecc9e522cd8f7157 |
| 252 | `b05ff3b815e6` | opponents/opp_raider_04.py | opponent-field | other #47 | R1 | 1.0625 | 16 | 0 | opponents/opp_raider_04.py @ b9e9751 |
| 253 | `2a9fa5c1127f` | opponents/opp_adaptive_02.py | opponent-field | other #29 | R1 | 1.0625 | 16 | 0 | opponents/opp_adaptive_02.py @ b9e9751 |
| 254 | `f5a54e20dbe3` | f5a54e20dbe36133c62d1bb57a157d5ab50d0964f1dd8a526bc4b18ee6631982.py | archived-variant | other #9 | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/f5a54e20dbe36133c62d1bb5 |
| 255 | `e60cf4147155` | e60cf414715554ff673f34c7527286f4c9833189a69a714316633acc4bd2eb51.py | archived-variant | other #8 | R1 | 1.0625 | 16 | 0 | archive: architectures_v2/…/e60cf414715554ff673f34c7 |
| 256 | `fbb732fdf81f` | 8d269f6f1cd96c3c4aeeaf2208efd05fcc414e2cc36796652e7e4d982e4fe392.py | evolved-genome | tiny evolved Rival | R1 | 1.0625 | 16 | 0 | archive: evidence/…/8d269f6f1cd96c3c4aeeaf22 |
| 257 | `208bc84d1915` | 208bc84d1915ee075d00247f1e201618b4be7378e3f3ffe862b0de17cf45df29.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/208bc84d1915ee075d00247f |
| 258 | `5cb591641636` | novel_5cb591641636 | novel-opponent | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/5cb591641636845334ecdd8b |
| 259 | `8cd5c1de46d4` | 8cd5c1de46d42c2c61bee6e3e09a380065a82ba96b5588c3b923bdd720a87d3b.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/8cd5c1de46d42c2c61bee6e3 |
| 260 | `9d22040695db` | novel_9d22040695db | novel-opponent | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/9d22040695db9ac60f2ba628 |
| 261 | `2aa2042606f4` | novel_2aa2042606f4 | novel-opponent | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/2aa2042606f4653e769f30b8 |
| 262 | `f353062a8e71` | novel_f353062a8e71 | novel-opponent | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/f353062a8e71bc64092b14e2 |
| 263 | `bf638b040c3b` | novel_bf638b040c3b | novel-opponent | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/bf638b040c3b616ebbc105cd |
| 264 | `e305df54207d` | e305df54207de7677fdc0388bfb7ff1cc94d1f263c10e2273cc64f7a033ba321.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/e305df54207de7677fdc0388 |
| 265 | `edef8bfa2e0f` | edef8bfa2e0f6a5d8da03a123735cab7e160042ca58b1996a6b0468eb75a8595.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/edef8bfa2e0f6a5d8da03a12 |
| 266 | `b39f2e192386` | b39f2e1923864b2750b4e8500b8dcee103cbd6e23ccaa71862008aa32284965d.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/b39f2e1923864b2750b4e850 |
| 267 | `8ecfbc1043db` | 8ecfbc1043dbf8edb1f0717fe60e02fe4669db3118ed1edb28396d5470554f82.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/8ecfbc1043dbf8edb1f0717f |
| 268 | `d32f99f7a06e` | d32f99f7a06e2bbadec425710cb19afddafb22a6f3d9807da259eb19e1818b9f.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/d32f99f7a06e2bbadec42571 |
| 269 | `2e044c4d24d9` | 407ff92668ba4d7a1e3cb92466b3547e96895517449f0912a6e7acd327c46c23.py | evolved-genome | guarded Transfer (current main family) | R1 | 1.0000 | 16 | 0 | archive: evidence/…/407ff92668ba4d7a1e3cb924 |
| 270 | `c09f981aa63c` | c09f981aa63c3319db8765cf56630b32ea719fbab1370e6738872e4ce2a4d641.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/c09f981aa63c3319db8765cf |
| 271 | `f074cd444ed3` | f074cd444ed354041b6b65914ae2b450eb11c1ff6ece0cfd2462582ed01814a8.py | archived-variant | generated 'Player' opponent | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/f074cd444ed354041b6b6591 |
| 272 | `a5031eaed1a1` | opponents/opp_buggy_01.py | opponent-field | simple act()-only bot | R1 | 1.0000 | 16 | 6 | opponents/opp_buggy_01.py @ b9e9751 |
| 273 | `c03a13ea7349` | c03a13ea7349b86bcbb4552964d926d1f2cbb760afadd35a54fd59787bf5640c.py | archived-variant | other #8 | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/c03a13ea7349b86bcbb45529 |
| 274 | `d14526f372e3` | opponents/opp_opportunist_gemini1.py | opponent-field | simple act()-only bot | R1 | 1.0000 | 16 | 0 | opponents/opp_opportunist_gemini1.py @ 3be829a |
| 275 | `29943674e478` | 29943674e478229ad5c4b869b15852d4581e0c305c1e73c7002f6c064540b489.py | archived-variant | other #9 | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/29943674e478229ad5c4b869 |
| 276 | `38ad64faa5ab` | opponents/opp_adaptive_gemini1.py | opponent-field | simple act()-only bot | R1 | 1.0000 | 16 | 0 | opponents/opp_adaptive_gemini1.py @ 0e8b4a9 |
| 277 | `cc3cb316bbc4` | cc3cb316bbc4fd149ba1235aea5f2d6b234e5807fbf5b3636f1adf43f2b4eebc.py | archived-variant | other #33 | R1 | 1.0000 | 16 | 0 | archive: architectures_v2/…/cc3cb316bbc4fd149ba1235a |
| 278 | `0966302c1e7d` | novel_0966302c1e7d | novel-opponent | generated 'Player' opponent | R1 | 0.9688 | 16 | 0 | archive: architectures_v2/…/0966302c1e7deecd52393014 |
| 279 | `e23de391a94d` | opponents/opp_adaptive_01.py | opponent-field | other #13 | R1 | 0.9375 | 16 | 0 | opponents/opp_adaptive_01.py @ b9e9751 |
| 280 | `d68923b9c463` | novel_d68923b9c463 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/d68923b9c463a61004250e6c |
| 281 | `158c277f276e` | novel_158c277f276e | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/158c277f276ec9b830818a61 |
| 282 | `cf5f02337dad` | cf5f02337dadf70beef9fd0db31256d27c831992fe96d59dccc28fb455d3aad5.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/cf5f02337dadf70beef9fd0d |
| 283 | `e604e1c520b3` | e604e1c520b3523a26194318e8622710f9439b406844cc5244f5b9ebba3ff061.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/e604e1c520b3523a26194318 |
| 284 | `dc2c502a9d61` | dc2c502a9d613504078efe9a81ba6bcd11fa2e605de225c2e537f728e3f385ab.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/dc2c502a9d613504078efe9a |
| 285 | `33d26faa1bb3` | novel_33d26faa1bb3 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/33d26faa1bb3b27c1668b1ac |
| 286 | `35f136e9e108` | 35f136e9e108bd1a109e637764b5b63e4e132cd8aad64e9db2a519f9e2aba2e2.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/35f136e9e108bd1a109e6377 |
| 287 | `e20622c4dfc6` | novel_e20622c4dfc6 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/e20622c4dfc6c2818d4d3616 |
| 288 | `0f40546e83b8` | novel_0f40546e83b8 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/0f40546e83b8da98c5635c39 |
| 289 | `96d75ae18836` | 96d75ae1883685630ddc61e77db526a5b28eff85ac79fdd02dcfea31ca028420.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/96d75ae1883685630ddc61e7 |
| 290 | `e1214b9abc39` | novel_e1214b9abc39 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/e1214b9abc39b2af9ee95bf1 |
| 291 | `c47b6a819163` | c47b6a8191631a6f0e1483f3de5db0b12d08301a4bea09d27861362886e40810.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/c47b6a8191631a6f0e1483f3 |
| 292 | `d36f4ffb36cd` | novel_d36f4ffb36cd | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/d36f4ffb36cd9994f9a6808c |
| 293 | `a9aeb92243f5` | novel_a9aeb92243f5 | novel-opponent | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/a9aeb92243f5a2bd32f10d0a |
| 294 | `8daa5d1de9c3` | 8daa5d1de9c3afcadd68fafffc98d7e4880eced55e46ded99531f5f900d0a2d9.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/8daa5d1de9c3afcadd68faff |
| 295 | `a9163654b2d5` | a9163654b2d57350b3c6ff54748239daeedbc15fda23da6b8d4c02099c80abe3.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/a9163654b2d57350b3c6ff54 |
| 296 | `d8e12594d770` | d8e12594d770dd68b28885a5d41b1bca0f804963d8a09816cc55399945e7906a.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/d8e12594d770dd68b28885a5 |
| 297 | `8fb0b82dba6d` | 8fb0b82dba6d16b3acc36f42e8d746219e5944999397b43c2194e47ac57fcb45.py | archived-variant | generated 'Player' opponent | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/8fb0b82dba6d16b3acc36f42 |
| 298 | `815918c3a2db` | 815918c3a2db14c07f694a32a7e6f9f752b989e2952554cb2ce60e63810c0ae9.py | archived-variant | other #14 | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/815918c3a2db14c07f694a32 |
| 299 | `2164474c40f9` | opponents/opp_naive_01.py | opponent-field | simple act()-only bot | R1 | 0.9375 | 16 | 0 | opponents/opp_naive_01.py @ b9e9751 |
| 300 | `53f876827a9f` | 53f876827a9f6987b9483003ae8bdd7714e67d7116bff109007b3fafbf3f1109.py | archived-variant | other #26 | R1 | 0.9375 | 16 | 0 | archive: architectures_v2/…/53f876827a9f6987b9483003 |
| 301 | `6ec950a65098` | opponents/opp_opportunist_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.9375 | 16 | 0 | opponents/opp_opportunist_gpt1.py @ 3be829a |
| 302 | `8eac9789c4c5` | opponents/opp_raider_01.py | opponent-field | other #13 | R1 | 0.9375 | 16 | 0 | opponents/opp_raider_01.py @ b9e9751 |
| 303 | `ecc22c954a65` | novel_ecc22c954a65 | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/ecc22c954a65a4b76edcdb22 |
| 304 | `4be1276ff329` | 4be1276ff32989cfde4cd6b37d10f89145980d70dffefd03f14f40d1da9f3ffb.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/4be1276ff32989cfde4cd6b3 |
| 305 | `b10836f7e7e6` | novel_b10836f7e7e6 | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/b10836f7e7e61702bd1580c6 |
| 306 | `201f44173081` | 201f441730813f482e83360c6a36eda848d5fb482cadcdc0b142b8e2c9ded6fc.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/201f441730813f482e83360c |
| 307 | `26649a5e6863` | novel_26649a5e6863 | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/26649a5e68633c7146396f0d |
| 308 | `8400e5c4d577` | novel_8400e5c4d577 | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/8400e5c4d57737f94c601e87 |
| 309 | `a5faa6111a0d` | a5faa6111a0dd6a84b366132ba7f0f94ab97f0c19ec6322fe04dbc1748a767d2.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/a5faa6111a0dd6a84b366132 |
| 310 | `29d868d2eaff` | novel_29d868d2eaff | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/29d868d2eaff398d22bb51b5 |
| 311 | `1c7e83af6c36` | 1c7e83af6c36ab91660e6ebd1ee69c8166e6f6300c2f48605a17acc7e90811e6.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/1c7e83af6c36ab91660e6ebd |
| 312 | `6ccd9608c49a` | novel_6ccd9608c49a | novel-opponent | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/6ccd9608c49aa4d86a01f24f |
| 313 | `ffa8ee918960` | ffa8ee9189601e1cc1770e1dba5c95ebb88acb7d5e8989da81c4acdd38fede55.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/ffa8ee9189601e1cc1770e1d |
| 314 | `3a56c6a88766` | 3a56c6a88766da5f42b2d67610a02f0583ea96619aadba3ad68a6f5a3f229684.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/3a56c6a88766da5f42b2d676 |
| 315 | `013fbccc96f3` | 013fbccc96f30f67f7c90dc1013bac8ddcf5d4c352555e8943f1b3a512cbf2a5.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/013fbccc96f30f67f7c90dc1 |
| 316 | `86ea5b330f56` | 86ea5b330f567af30d9f5402c0adb986dd2d336140e51e93195b61b3a162326e.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/86ea5b330f567af30d9f5402 |
| 317 | `219abf2e7151` | 219abf2e7151e9dc594911b7e7f5b236c3e1475ecf9d5b326232bcb25adba821.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/219abf2e7151e9dc594911b7 |
| 318 | `b64da0272cbb` | b64da0272cbbaa782e6af251ee0fdae69fc0120ed228c51534a30da00d6bc2f6.py | archived-variant | other #10 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/b64da0272cbbaa782e6af251 |
| 319 | `a12c00342f98` | a12c00342f98907a018a8ae780fea0d1584b3d375f388e518258a4242c730b0b.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/a12c00342f98907a018a8ae7 |
| 320 | `b3a2cd626fb5` | b3a2cd626fb55f62ca5685508abdf7a6ffb0366881627f7fbee5bd042e85423d.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/b3a2cd626fb55f62ca568550 |
| 321 | `7e322ce18c11` | 7e322ce18c11c3c8be1f8801c6e68cf6da16cdea99ab0a61e03fe82b01db31e8.py | archived-variant | generated 'Player' opponent | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/7e322ce18c11c3c8be1f8801 |
| 322 | `684566ff8ecc` | 684566ff8ecc2afa8c078a2c5fe8a24b865b88625aaf9ccb5fd44eaede24083a.py | archived-variant | other #10 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/684566ff8ecc2afa8c078a2c |
| 323 | `3ac6d190b421` | 3ac6d190b421360939e71c13fb7c5a70b937a246b6fd8631ba35f97e36ce71cd.py | archived-variant | other #10 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/3ac6d190b421360939e71c13 |
| 324 | `514775d141be` | 514775d141be466c6507fca74e3b99594920d1151f27f0d6d3d124d800e9fa87.py | archived-variant | other #24 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/514775d141be466c6507fca7 |
| 325 | `8cbef7eccb4e` | 8cbef7eccb4e1d8ab9dcb21d0d768295cfec530dc3deb05262fbdbd38cf96a2e.py | archived-variant | other #10 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/8cbef7eccb4e1d8ab9dcb21d |
| 326 | `067e2202b8e1` | opponents/opp_naive_gpt2.py | opponent-field | simple act()-only bot | R1 | 0.8750 | 16 | 0 | opponents/opp_naive_gpt2.py @ 0e8b4a9 |
| 327 | `2fd113a92d7b` | opponents/opp_opportunist_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.8750 | 16 | 0 | opponents/opp_opportunist_gemini1.py @ 0e8b4a9 |
| 328 | `f7f9acb0057b` | f7f9acb0057bc18b42c44b303a810a0df6fe0868a341a433579894c3f3dda723.py | archived-variant | other #14 | R1 | 0.8750 | 16 | 0 | archive: architectures_v2/…/f7f9acb0057bc18b42c44b30 |
| 329 | `80235e109f34` | 80235e109f3468eb5782660be5433c3ba1ee6fc2d2739ef0b4560f488d267704.py | archived-variant | generated 'Player' opponent | R1 | 0.8438 | 16 | 0 | archive: architectures_v2/…/80235e109f3468eb5782660b |
| 330 | `4ec816bcb4d4` | 4ec816bcb4d4993f4643564bd8b8260835335335f7e04ab0052e8b9a6b829162.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/4ec816bcb4d4993f4643564b |
| 331 | `2654bc182419` | novel_2654bc182419 | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/2654bc1824198329ddda7019 |
| 332 | `4160cf99ce6d` | 4160cf99ce6d0f2c416ae73f9bf506e0c5929e1101195ae37e100b8a7fa0bca5.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/4160cf99ce6d0f2c416ae73f |
| 333 | `b4fce585f8cd` | novel_b4fce585f8cd | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/b4fce585f8cd7ae26cfa30d5 |
| 334 | `92e20d66111a` | novel_92e20d66111a | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/92e20d66111a0818e049399e |
| 335 | `13a39a685825` | 13a39a6858252e418db105782ade551e54690ce23e76ea790910449f94c7e449.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/13a39a6858252e418db10578 |
| 336 | `3e91b94e1081` | 3e91b94e1081345b60b3b26b671a1dbf434898ba2c9d441b07f4494fc7dafc9b.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/3e91b94e1081345b60b3b26b |
| 337 | `8fa52d78fb21` | novel_8fa52d78fb21 | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/8fa52d78fb2112ae6b9e8b3f |
| 338 | `0af16778b1e0` | 0af16778b1e05f53e69650e9be3965f89a57d3a517ec5ca228ccafa153db627f.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/0af16778b1e05f53e69650e9 |
| 339 | `96f5ad11f8f3` | 96f5ad11f8f3f57169a4024074f3ad2815118c6942ac1d896620e20fb88e38d1.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/96f5ad11f8f3f57169a40240 |
| 340 | `d0c6e141c242` | d0c6e141c242b0b83940d5450486e90535898dee4bf47f4a06f85d125ab96ed2.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/d0c6e141c242b0b83940d545 |
| 341 | `5c62dda9b58a` | novel_5c62dda9b58a | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/5c62dda9b58adbc6bd8e4ef1 |
| 342 | `0b57f0be1299` | 0b57f0be12997591bda7cf92c5d7efc91395f0fe065d26bb412c249cb3893e42.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/0b57f0be12997591bda7cf92 |
| 343 | `42e759b51db9` | opponents/opp_shield_03.py | opponent-field | other #21 | R1 | 0.8125 | 16 | 0 | opponents/opp_shield_03.py @ b9e9751 |
| 344 | `083e6f66fca9` | 083e6f66fca9eee058476151886e04180f6a401992ab7be7efcdd3acd10ee14b.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/083e6f66fca9eee058476151 |
| 345 | `f6ce1650ae56` | f6ce1650ae566ff5f5dbe2a9a1e863a30d710b4ed634fcf10c754151ee34e383.py | archived-variant | other #9 | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/f6ce1650ae566ff5f5dbe2a9 |
| 346 | `605f98c72110` | 605f98c72110f01ea4882d41006c09d8bb2b6ba08d5b23aad2cd3648c40b1831.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/605f98c72110f01ea4882d41 |
| 347 | `e31a0c9c7501` | novel_e31a0c9c7501 | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/e31a0c9c75014134a71bbd01 |
| 348 | `a35744ac0e43` | novel_a35744ac0e43 | novel-opponent | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/a35744ac0e439d4f8b544d6a |
| 349 | `b5f421ecfad4` | b5f421ecfad4fefe89cd5096ae3c1fc55af4c8febff6906b4e261a10e8c36c81.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/b5f421ecfad4fefe89cd5096 |
| 350 | `b8d8718db89a` | bot_frozen_progress.py | archived-variant | Transfer / evolved economic planner | R1 | 0.8125 | 16 | 0 | archive: outputs/…/bot_frozen_progress.py |
| 351 | `72932ac69d8e` | 72932ac69d8e75836b3610b54da27fb0af4917e59ed938a62cd40cacb799f149.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/72932ac69d8e75836b3610b5 |
| 352 | `4fb8269883a3` | 4fb8269883a3e247afbed2aedb1d4ebd6dea0ea50d8eb3046d2d900e0ebd73e1.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/4fb8269883a3e247afbed2ae |
| 353 | `00033f835753` | 00033f8357532975c4bcd3915c4ade2abac8165c8a0727badf7f6a878424e6ca.py | archived-variant | generated 'Player' opponent | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/00033f8357532975c4bcd391 |
| 354 | `25e30d29c248` | 25e30d29c248a616fd55ad2b7f1221a4e093e9c8be93223fb8f56cdd5616f441.py | archived-variant | other #14 | R1 | 0.8125 | 16 | 0 | archive: architectures_v2/…/25e30d29c248a616fd55ad2b |
| 355 | `d653643c3c5f` | opponents/opp_naive_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.8125 | 16 | 0 | opponents/opp_naive_gemini1.py @ 0e8b4a9 |
| 356 | `002d7bddb757` | 002d7bddb75790f38cc6795d6f9d823b765a5cf7d7160049dbe048933685eca1.py | archived-variant | generated 'Player' opponent | R1 | 0.7812 | 16 | 0 | archive: architectures_v2/…/002d7bddb75790f38cc6795d |
| 357 | `99745eac22a7` | novel_99745eac22a7 | novel-opponent | generated 'Player' opponent | R1 | 0.7812 | 16 | 0 | archive: architectures_v2/…/99745eac22a75e7f26a0d057 |
| 358 | `da186e8776da` | da186e8776da54cdfa541e2977bf8aae376667b62758b3394e68cbf81e62b0f0.py | archived-variant | generated 'Player' opponent | R1 | 0.7812 | 16 | 0 | archive: architectures_v2/…/da186e8776da54cdfa541e29 |
| 359 | `a8b3c73d1016` | a8b3c73d1016a2a26173adbb19a612880bd63b9cf46276bd345b96507e4c1d19.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/a8b3c73d1016a2a26173adbb |
| 360 | `453b26073bf9` | novel_453b26073bf9 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/453b26073bf9109492a3a700 |
| 361 | `07101cc1472a` | novel_07101cc1472a | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/07101cc1472addfc4b484736 |
| 362 | `c87fbe293b2f` | novel_c87fbe293b2f | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/c87fbe293b2f9465a0854847 |
| 363 | `c2610eae0f70` | c2610eae0f70e12d1510ee201b8d9d8a98af0ce3faeae151d3068041d6ae2178.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/c2610eae0f70e12d1510ee20 |
| 364 | `7c9f1e431c64` | 7c9f1e431c644ee2a9e0c0fcdba1d29e2cd4adf6b1e2f1aa65aca0c73becbdbc.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/7c9f1e431c644ee2a9e0c0fc |
| 365 | `684dde975cfb` | 684dde975cfb450d1caa823816eb45d4d8c4042e21f8ebd83b3e297b01ddd947.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/684dde975cfb450d1caa8238 |
| 366 | `6862f4448641` | 6862f44486417a2f24e96496b0ef2c103844241957bac366e6a96fa2439b7744.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/6862f44486417a2f24e96496 |
| 367 | `415c239c29d1` | novel_415c239c29d1 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/415c239c29d121a24a0fa9cc |
| 368 | `b61bfaa1c5e7` | b61bfaa1c5e7ed8f7f82d6c7971ebe9006d4063529cefac7fd74a1434293cdde.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/b61bfaa1c5e7ed8f7f82d6c7 |
| 369 | `f94574e84444` | f94574e84444eff99bf963e8bd1913506bdb319f3a93691ce6c9ba0299b0a657.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/f94574e84444eff99bf963e8 |
| 370 | `aeeac56ee37e` | aeeac56ee37e4b6cfb56b6b1465e72108ec2d6ae7571fc56305dc79542243000.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/aeeac56ee37e4b6cfb56b6b1 |
| 371 | `f874cd5b9966` | f874cd5b9966fee295b79c4251a1cad7be44f16db993cea955fa1758b727a0f0.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/f874cd5b9966fee295b79c42 |
| 372 | `af0a26d450b8` | novel_af0a26d450b8 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/af0a26d450b8a8c6959892b2 |
| 373 | `7a9381a30249` | 7a9381a30249b56063c3e7b46bbdcbb51a731a4b8e68e0fc658ae40c8a8d4f07.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/7a9381a30249b56063c3e7b4 |
| 374 | `a058c3eefde4` | novel_a058c3eefde4 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/a058c3eefde4d2f99559aca9 |
| 375 | `2a092692e4be` | 2a092692e4be3e3fd63e26fcf6953e9aa95b40d4127366194aa12ef7d12989f4.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/2a092692e4be3e3fd63e26fc |
| 376 | `bbe5f9c2b16a` | novel_bbe5f9c2b16a | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/bbe5f9c2b16af94880862f43 |
| 377 | `c6fbb9975c17` | novel_c6fbb9975c17 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/c6fbb9975c17c88ee0899428 |
| 378 | `e7e6a73ffdd3` | e7e6a73ffdd3fe159dd6c2fe93b351234dd36f5b345cb9543639e5233a5029bb.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/e7e6a73ffdd3fe159dd6c2fe |
| 379 | `044e72a940c5` | 044e72a940c5da256cbcd7dfe3540a6f8f0bd832390ba4b36d50fa271fdcd7d2.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/044e72a940c5da256cbcd7df |
| 380 | `acb3b5b8f773` | novel_acb3b5b8f773 | novel-opponent | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/acb3b5b8f773fe10a09ae184 |
| 381 | `2fdcd8ccf891` | 2fdcd8ccf891a35d4732c11ebf0daa7cfb1a4b5b19b4dc27304a51507a4db043.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/2fdcd8ccf891a35d4732c11e |
| 382 | `dfa6e0427b2a` | dfa6e0427b2a9e3614579723ff20550603ef8e2c6cf3b4c12fd5a47f98afc530.py | archived-variant | generated 'Player' opponent | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/dfa6e0427b2a9e3614579723 |
| 383 | `c3621deb6773` | c3621deb67731fd2392bc26257c2c95c378a0c123ee9404b795643405181e018.py | archived-variant | other #8 | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/c3621deb67731fd2392bc262 |
| 384 | `cc26fd640c08` | cc26fd640c08828424b29d1d36a4cec7577c30e706b1da02614cda60b78c058f.py | archived-variant | other #14 | R1 | 0.7500 | 16 | 0 | archive: architectures_v2/…/cc26fd640c08828424b29d1d |
| 385 | `3e59ce7421a6` | novel_3e59ce7421a6 | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/3e59ce7421a6d0399ef54652 |
| 386 | `412a532ee42b` | novel_412a532ee42b | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/412a532ee42b622e4791b401 |
| 387 | `96124af629c7` | novel_96124af629c7 | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/96124af629c785e5ae95244e |
| 388 | `0bb5208c4dae` | novel_0bb5208c4dae | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/0bb5208c4dae470ec2554dda |
| 389 | `af6e02f8a253` | af6e02f8a2532f2add5690697e97d53346a9b7aba9d5e23e638dd218e076bbdd.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/af6e02f8a2532f2add569069 |
| 390 | `f25ab71bf1a1` | f25ab71bf1a13161b13b55a83cf4f30d75275fa1753375773451f0f8d576934b.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/f25ab71bf1a13161b13b55a8 |
| 391 | `f76ca5827744` | f76ca58277448effad0bb7bd662d325b62f1ee820915af676cf0c37f3aa1bb5f.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/f76ca58277448effad0bb7bd |
| 392 | `83bc99c5801f` | novel_83bc99c5801f | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/83bc99c5801f5bc79eca2229 |
| 393 | `a35ab1ef52ca` | a35ab1ef52ca893461bb864faf9e94c47ff08a89a7b521d8d4d495d30161114a.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/a35ab1ef52ca893461bb864f |
| 394 | `c10ac8bb96f1` | c10ac8bb96f163b69afbcefb758432afe237edbe64357062fbccd8f942fc935c.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/c10ac8bb96f163b69afbcefb |
| 395 | `8387ed29fd1b` | novel_8387ed29fd1b | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/8387ed29fd1b04980eae1268 |
| 396 | `a8bf9a0838da` | a8bf9a0838da7bfd429591181cf4285942001abcef3cb6061ec1ca442efb4daf.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/a8bf9a0838da7bfd42959118 |
| 397 | `02d64851a308` | 02d64851a30843efca509242f7723a3dc3b99f0819f6f77623ec5b8f3f4799b6.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/02d64851a30843efca509242 |
| 398 | `8df168eb3311` | 8df168eb33119daa8426f9a397ceba89b91eb271399e15e8b5332d7c88117c21.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/8df168eb33119daa8426f9a3 |
| 399 | `3a585dbd47de` | 3a585dbd47de172a2f013801ffd7d60e32a8e8d0084876de56dd4b8426594a04.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/3a585dbd47de172a2f013801 |
| 400 | `cc53f636bdf8` | opponents/opp_farmer_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.6875 | 16 | 0 | opponents/opp_farmer_gemini1.py @ 3be829a |
| 401 | `5d2c9bc55d2d` | novel_5d2c9bc55d2d | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/5d2c9bc55d2d8a3a12b48400 |
| 402 | `62d8ac1f1fa8` | novel_62d8ac1f1fa8 | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/62d8ac1f1fa8f430320a55ab |
| 403 | `0e4182eed5e5` | novel_0e4182eed5e5 | novel-opponent | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/0e4182eed5e5075b466a8834 |
| 404 | `6970d68d17ff` | 6970d68d17ff60c64eb5fd4b091af17441358c44301e0884d65643099d7c2e76.py | archived-variant | generated 'Player' opponent | R1 | 0.6875 | 16 | 0 | archive: architectures_v2/…/6970d68d17ff60c64eb5fd4b |
| 405 | `dc6cf21af88d` | opponents/opp_greedy_gpt1.py | opponent-field | other #38 | R1 | 0.6875 | 16 | 0 | opponents/opp_greedy_gpt1.py @ 0e8b4a9 |
| 406 | `fe6b1a80cf06` | novel_fe6b1a80cf06 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/fe6b1a80cf064cb353f99ba1 |
| 407 | `19059bece653` | 19059bece6536879a5577c85ff5f3872b1effb22c71e418d738551bb18965773.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/19059bece6536879a5577c85 |
| 408 | `6e197e893d96` | novel_6e197e893d96 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/6e197e893d9692caa9610cbe |
| 409 | `8cc12a1065f0` | novel_8cc12a1065f0 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/8cc12a1065f0456f97e85ff5 |
| 410 | `68223f8b6cb8` | novel_68223f8b6cb8 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/68223f8b6cb8eac19d2a4466 |
| 411 | `953b0b410c35` | 953b0b410c35914b1587bbefd077ed37e9e01f4d2fb3c4338ebd375520fb7dc9.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/953b0b410c35914b1587bbef |
| 412 | `97a75dcd2461` | 97a75dcd2461b3781b625bb9d86c8b93d2a75c85b1ebec21f52afd6a1c2e48e2.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/97a75dcd2461b3781b625bb9 |
| 413 | `951a6cca7e0f` | 951a6cca7e0f6429dc34f25549b977dd3090b662ee5ee9589185a9fa2625a98d.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/951a6cca7e0f6429dc34f255 |
| 414 | `21750b874b6c` | novel_21750b874b6c | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/21750b874b6cba4096efa487 |
| 415 | `52a05cba6f74` | 52a05cba6f74758c9727cff2c08b3643b801549a294ba82fc173f6361c815438.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/52a05cba6f74758c9727cff2 |
| 416 | `5604b1aecc83` | novel_5604b1aecc83 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/5604b1aecc8309dc19c2c5ff |
| 417 | `55437d062713` | 55437d0627139174bb82e76818327ed910ee9aa74557ee2a4c4a77ef632d5300.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/55437d0627139174bb82e768 |
| 418 | `1cdcba187107` | opponents/opp_adaptive_03.py | opponent-field | other #45 | R1 | 0.6250 | 16 | 0 | opponents/opp_adaptive_03.py @ b9e9751 |
| 419 | `399228eba0dc` | novel_399228eba0dc | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/399228eba0dc1fa321edb8b5 |
| 420 | `bf955f0fe361` | bf955f0fe3612a7c1030b1148b9ac5783835ba7df7141017bb4bbe2f1e33ffa7.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/bf955f0fe3612a7c1030b114 |
| 421 | `5b332e1ffc4a` | novel_5b332e1ffc4a | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/5b332e1ffc4ab93e73522bf1 |
| 422 | `29abfe9dc7bd` | 29abfe9dc7bd905fdb5c3019b5572bbdf3d98a3eb06a93b8ba352f1375304a60.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/29abfe9dc7bd905fdb5c3019 |
| 423 | `cf340c6d7a9c` | novel_cf340c6d7a9c | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/cf340c6d7a9cb0427f316026 |
| 424 | `334707718414` | 334707718414306f911049dac9a06f7985aced08bd541fc3b56f1f2bd72b7870.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/334707718414306f911049da |
| 425 | `b238d83270ec` | b238d83270ecd0467cc15e5e53d3521dbf2c71bf6e17aefbef949d3bdf11c296.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/b238d83270ecd0467cc15e5e |
| 426 | `025d015836e8` | novel_025d015836e8 | novel-opponent | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/025d015836e8da17fda0b1ca |
| 427 | `0b0240047529` | 0b02400475299f32dfff539e4616749d628b2fd7faf7c400b1e46240694dd5f3.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/0b02400475299f32dfff539e |
| 428 | `31cc7b93f23c` | 31cc7b93f23cef96fc65451a66a93d9339793ebf825b38b9ea8f8130e46d6f9b.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/31cc7b93f23cef96fc65451a |
| 429 | `83edc77b2b3f` | 83edc77b2b3fc45f2670baf7116c899d4374240e442da3339152b6620c04575b.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/83edc77b2b3fc45f2670baf7 |
| 430 | `27fbb33378ea` | opponents/opp_naive_04.py | opponent-field | simple act()-only bot | R1 | 0.6250 | 16 | 0 | opponents/opp_naive_04.py @ b9e9751 |
| 431 | `ead3c24d59c6` | ead3c24d59c610b14f6ef0e04584e0b28dbf25e4d2520bed3d4c95b9f67c6148.py | archived-variant | generated 'Player' opponent | R1 | 0.6250 | 16 | 0 | archive: architectures_v2/…/ead3c24d59c610b14f6ef0e0 |
| 432 | `19f1b426c49c` | opponents/opp_raider_02.py | opponent-field | other #13 | R1 | 0.6250 | 16 | 0 | opponents/opp_raider_02.py @ b9e9751 |
| 433 | `d44e9ce2fa35` | opponents/opp_planner_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.6250 | 16 | 0 | opponents/opp_planner_gemini1.py @ 0e8b4a9 |
| 434 | `d22576ac14c2` | 2ee97b4f0f786917b47776f1c80506c671fe5916cba441afbfcd2b06ce8a89c5.py | evolved-genome | tiny evolved Rival | R1 | 0.6250 | 16 | 0 | archive: evidence/…/2ee97b4f0f786917b47776f1 |
| 435 | `3598d1870493` | 461c60eb879f842490366d1508dd73dab974be8dbbb06dc349303393d701a507.py | evolved-genome | tiny evolved Rival | R1 | 0.6250 | 16 | 0 | archive: evidence/…/461c60eb879f842490366d15 |
| 436 | `aa308ce71155` | 3f6f13d7e3ba96f26deca9e8509f4282f52494248d055288582d9bbb947176ff.py | evolved-genome | tiny evolved Rival | R1 | 0.6250 | 16 | 0 | archive: evidence/…/3f6f13d7e3ba96f26deca9e8 |
| 437 | `e80dd8341b71` | e80dd8341b718ace60f44d6cb344b492ef62a9fef63c3ebc95589dd270462f33.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/e80dd8341b718ace60f44d6c |
| 438 | `be885384874c` | opponents/opp_buggy_02.py | opponent-field | other #21 | R1 | 0.5625 | 16 | 0 | opponents/opp_buggy_02.py @ b9e9751 |
| 439 | `b0594e95ed35` | novel_b0594e95ed35 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/b0594e95ed354e52451a05e1 |
| 440 | `d3b700901c4d` | novel_d3b700901c4d | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/d3b700901c4d2ad4a29faa3b |
| 441 | `7b5be6d32e72` | novel_7b5be6d32e72 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/7b5be6d32e72d76ec0b9f3c1 |
| 442 | `0ce93d1bed8e` | 0ce93d1bed8e83f3f4c5656f08779fa4bd985f7f706fe1a00c711a6e418fd4f4.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/0ce93d1bed8e83f3f4c5656f |
| 443 | `0db330d2bb63` | opponents/opp_farmer_04.py | opponent-field | other #30 | R1 | 0.5625 | 16 | 0 | opponents/opp_farmer_04.py @ b9e9751 |
| 444 | `4cce0bf6115b` | novel_4cce0bf6115b | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/4cce0bf6115b2213ca8e4316 |
| 445 | `145f9b37124a` | novel_145f9b37124a | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/145f9b37124a973f6b19f694 |
| 446 | `8879f6f27a3b` | 8879f6f27a3b48206129455dfea65552f45f3b1572dee595692d048e039c3fcb.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/8879f6f27a3b48206129455d |
| 447 | `3533bd4a98eb` | 3533bd4a98eb788ff26176d2d1329043bc14192f5b8d2d4879d957d98e695946.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/3533bd4a98eb788ff26176d2 |
| 448 | `7db81c260e4a` | 7db81c260e4a6e3842399f226627f8c9d5dc0a4c456fa501d500d7c8b94d1ccc.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/7db81c260e4a6e3842399f22 |
| 449 | `1a7087244713` | 1a70872447130961bfba3215b054d209426662786ce11a6af23e8178c328a42a.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/1a70872447130961bfba3215 |
| 450 | `5a890c6242be` | 5a890c6242bee9431078a808137e29c728c4b92d71231c2f2d9fec631950bcf9.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/5a890c6242bee9431078a808 |
| 451 | `bc14c9bc7470` | bc14c9bc7470c709d2fc270d3753e29bec04b19592abfb2dda6bbeffd8c06ed2.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/bc14c9bc7470c709d2fc270d |
| 452 | `4dc8a91b2eb8` | 4dc8a91b2eb8832cf02c401a65353f9210ded23afad2862b436a1679575f21da.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/4dc8a91b2eb8832cf02c401a |
| 453 | `3ae316c79388` | 3ae316c793886a5fdaabb00647871affdf75a0c86cace4bac82d0ba228dc7456.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/3ae316c793886a5fdaabb006 |
| 454 | `e9a08c96a667` | novel_e9a08c96a667 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/e9a08c96a66786b848ad0905 |
| 455 | `04f37cec8b60` | novel_04f37cec8b60 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/04f37cec8b60a12ae99bd528 |
| 456 | `b603a9876079` | b603a9876079d15176dd5211fafa554a5f0019136ae5c173d9e046a3fc93d871.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/b603a9876079d15176dd5211 |
| 457 | `7579aaaf8cfb` | novel_7579aaaf8cfb | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/7579aaaf8cfb1e72c001a191 |
| 458 | `a912ba287283` | novel_a912ba287283 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/a912ba287283cab613c27b89 |
| 459 | `1556b3ade562` | novel_1556b3ade562 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/1556b3ade562353a9a8f44b7 |
| 460 | `00640fa1f6de` | novel_00640fa1f6de | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/00640fa1f6de5229f778ae6e |
| 461 | `473163e4f7c0` | novel_473163e4f7c0 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/473163e4f7c0df412936fae0 |
| 462 | `992df94810fc` | novel_992df94810fc | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/992df94810fcd39fe73a20fa |
| 463 | `80f427aec6f2` | 80f427aec6f220b8113336d54dc7c887d39b05858f2b4f88f3a24f9877c5c983.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/80f427aec6f220b8113336d5 |
| 464 | `170c95a0b7c8` | novel_170c95a0b7c8 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/170c95a0b7c880e3f156b5a2 |
| 465 | `5bd3e3e73203` | 5bd3e3e73203e49efe2952936c106fb18e33b48a1d849ee5da68f9f289a9b4de.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/5bd3e3e73203e49efe295293 |
| 466 | `0aef67e4f848` | novel_0aef67e4f848 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/0aef67e4f848598545707576 |
| 467 | `a6636327b8c4` | novel_a6636327b8c4 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/a6636327b8c41b5c8bd8f0b3 |
| 468 | `5860703bb3a3` | 5860703bb3a3690c60f2859049193c6694e28c472c391923e2a6b3ae32453d75.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/5860703bb3a3690c60f28590 |
| 469 | `6e58e14dca73` | 6e58e14dca7302e60ec234f7da51d26e7a961ec1b8549e3974228313e7f2a3c0.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/6e58e14dca7302e60ec234f7 |
| 470 | `dd61561271b2` | novel_dd61561271b2 | novel-opponent | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/dd61561271b2deb74471ab86 |
| 471 | `eef605ca1061` | opponents/opp_naive_gpt1.py | opponent-field | other #39 | R1 | 0.5625 | 16 | 0 | opponents/opp_naive_gpt1.py @ 0e8b4a9 |
| 472 | `6d89dfce1292` | 6d89dfce12922634ee9c3038a52c06003bb419f1fc91c4b7df3d014d322b0dbf.py | archived-variant | generated 'Player' opponent | R1 | 0.5625 | 16 | 0 | archive: architectures_v2/…/6d89dfce12922634ee9c3038 |
| 473 | `1056046dff6b` | opponents/opp_bait_03.py | opponent-field | other #46 | R1 | 0.5625 | 16 | 0 | opponents/opp_bait_03.py @ b9e9751 |
| 474 | `ec6bfb8f29dd` | 416d4ba94ab693d840da709751be669ac6d2f2f5e556ec881c3991c713316585.py | evolved-genome | tiny evolved Rival | R1 | 0.5625 | 16 | 0 | archive: evidence/…/416d4ba94ab693d840da7097 |
| 475 | `49183562673f` | novel_49183562673f | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/49183562673f4d0fd319c3e7 |
| 476 | `10f6def67530` | novel_10f6def67530 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/10f6def67530207b15046f99 |
| 477 | `a06fba051998` | novel_a06fba051998 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/a06fba051998613c654ec3bd |
| 478 | `f5573545e5ad` | f5573545e5adeb5053a7da2a868a5569bc7c39a7abdb92c8196e2bc68a059b9a.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/f5573545e5adeb5053a7da2a |
| 479 | `8bd92fbe5981` | 8bd92fbe5981d822cd3f722e47321f625605cf59a01de2d822260240b0d6c238.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/8bd92fbe5981d822cd3f722e |
| 480 | `9eda766930de` | 9eda766930de72e781ef45d8f544fcd703464dc635e68ca49f7491509c100f2f.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/9eda766930de72e781ef45d8 |
| 481 | `636153b56554` | novel_636153b56554 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/636153b565546e35402e46bc |
| 482 | `0bb418bc2483` | novel_0bb418bc2483 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/0bb418bc24831d6b920fe4dc |
| 483 | `ec88c0691174` | ec88c06911740ec29fd821d04de8f0dfd6e8bbbb0d3936048ee5b1352477bb8c.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/ec88c06911740ec29fd821d0 |
| 484 | `4dcd8263bfb4` | novel_4dcd8263bfb4 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/4dcd8263bfb4d9a1bd1feeeb |
| 485 | `ab39cda757ee` | opponents/opp_farmer_02.py | opponent-field | other #30 | R1 | 0.5000 | 16 | 0 | opponents/opp_farmer_02.py @ b9e9751 |
| 486 | `59608033eb40` | 59608033eb40778d258118e396bc8eb6439f59406de8e93b271a70059ce5bbfa.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/59608033eb40778d258118e3 |
| 487 | `da4a05158310` | da4a0515831047919b68ff8a5b94a31f745c5b2122ea4ca01c4210fd73e51b32.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/da4a0515831047919b68ff8a |
| 488 | `b2a0d6c92732` | novel_b2a0d6c92732 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/b2a0d6c927322af5c7f87a37 |
| 489 | `ad053b858504` | ad053b858504a284fda171fdfe7323ffee7603900dca86ae43c9fbe86a48ca5b.py | archived-variant | other #9 | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/ad053b858504a284fda171fd |
| 490 | `3e05e5aaee7c` | 3e05e5aaee7cbe50a2c99c0ff65bd9ee352d78e7280744e548f63272f7da63fa.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/3e05e5aaee7cbe50a2c99c0f |
| 491 | `fb3cc6b5fbf9` | fb3cc6b5fbf9e649740e862b276f9e12befa5b94f09bc5dc01137e38d89f6918.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/fb3cc6b5fbf9e649740e862b |
| 492 | `16ba21231b61` | novel_16ba21231b61 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/16ba21231b615146b45bd056 |
| 493 | `3b1b30044cc6` | novel_3b1b30044cc6 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/3b1b30044cc635c9bd221af8 |
| 494 | `2c8c766f6b5b` | novel_2c8c766f6b5b | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/2c8c766f6b5bb1f32c4f5495 |
| 495 | `b2950c989673` | novel_b2950c989673 | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/b2950c989673f4f7b171b61f |
| 496 | `4e4baa8486bf` | novel_4e4baa8486bf | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/4e4baa8486bf004341f8616c |
| 497 | `d8c693d2b47f` | d8c693d2b47f66de01c2fe6853795353484a75ce275f49ea353b5485dfb53489.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/d8c693d2b47f66de01c2fe68 |
| 498 | `f9f5eece5dce` | novel_f9f5eece5dce | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/f9f5eece5dce1af86863cf8d |
| 499 | `3c1bfb1c291e` | novel_3c1bfb1c291e | novel-opponent | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/3c1bfb1c291e7292b70fc464 |
| 500 | `46c23637c833` | 46c23637c8333749253e8e7d982197be05d55d06f4d470aaea3e4050d34c20f6.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/46c23637c8333749253e8e7d |
| 501 | `cb9e8a85e220` | cb9e8a85e220cda4a14ec7e676a15657a35227be5702e2bf57080b6e4e5b690a.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/cb9e8a85e220cda4a14ec7e6 |
| 502 | `fa850333231a` | fa850333231a455934d67749d66e4e26c1c10a750f6df8635b4794760e94e740.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/fa850333231a455934d67749 |
| 503 | `e1940cb738a7` | e1940cb738a7e47f24e3d04d78d8f88b98cc83ab452f6f8b5d4b905e4cc06629.py | archived-variant | generated 'Player' opponent | R1 | 0.5000 | 16 | 0 | archive: architectures_v2/…/e1940cb738a7e47f24e3d04d |
| 504 | `d631c112e332` | 8aa2d05c477d1d9627bc4a0635b6245dcf8b3444a9f4e79b290fc5d8b140be61.py | evolved-genome | tiny evolved Rival | R1 | 0.5000 | 16 | 0 | archive: evidence/…/8aa2d05c477d1d9627bc4a06 |
| 505 | `17feef3a1470` | opponents/opp_quadrantfarmer_gpt1.py | opponent-field | other #36 | R1 | 0.5000 | 16 | 0 | opponents/opp_quadrantfarmer_gpt1.py @ 0e8b4a9 |
| 506 | `6af698080016` | opponents/opp_naive_03.py | opponent-field | simple act()-only bot | R1 | 0.5000 | 16 | 0 | opponents/opp_naive_03.py @ b9e9751 |
| 507 | `0dac7f82726d` | a1cdad51a76b1bd5eb3c9a51f17e9e3f47ad66ccc815261376229bd2ee04fd0f.py | evolved-genome | tiny evolved Rival | R1 | 0.5000 | 16 | 0 | archive: evidence/…/a1cdad51a76b1bd5eb3c9a51 |
| 508 | `302daec51498` | opponents/opp_centrerusher_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.5000 | 16 | 0 | opponents/opp_centrerusher_gpt1.py @ 3be829a |
| 509 | `91ee9713022b` | opponents/opp_raider_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.5000 | 16 | 0 | opponents/opp_raider_gemini1.py @ 0e8b4a9 |
| 510 | `b2a28fd04cbe` | opponents/opp_farmer_01.py | opponent-field | other #13 | R1 | 0.4688 | 16 | 0 | opponents/opp_farmer_01.py @ b9e9751 |
| 511 | `b50f998d9c81` | novel_b50f998d9c81 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/b50f998d9c81b5cec708c8be |
| 512 | `488f07d59d40` | novel_488f07d59d40 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/488f07d59d4012bcfe483672 |
| 513 | `b44523025a46` | b44523025a4606fc09b864bc57dd54fb8d2db0627866f11675fc7c7c5aab0511.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/b44523025a4606fc09b864bc |
| 514 | `c525ed87540f` | c525ed87540f30d1c0736679374e2ff8172d361ff4ab5dcf03d80cfc95c9c485.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/c525ed87540f30d1c0736679 |
| 515 | `fe14a4ccda14` | novel_fe14a4ccda14 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/fe14a4ccda14d3b7f6c10b16 |
| 516 | `379b14d4618c` | novel_379b14d4618c | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/379b14d4618cfe41dbf81251 |
| 517 | `06162bc5287d` | novel_06162bc5287d | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/06162bc5287dffb3d6e80d4c |
| 518 | `e2aefe27ead7` | novel_e2aefe27ead7 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/e2aefe27ead7a5717844355e |
| 519 | `42004a941296` | novel_42004a941296 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/42004a941296080a6fb4947b |
| 520 | `360d8174f905` | novel_360d8174f905 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/360d8174f9055947f71f7166 |
| 521 | `2d8dc4d43e3f` | novel_2d8dc4d43e3f | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/2d8dc4d43e3fe20660814b7b |
| 522 | `d78e28537523` | novel_d78e28537523 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/d78e2853752339f6141f5a3d |
| 523 | `1b2fb8b377d1` | 1b2fb8b377d188c0aaa76590e06f3ca298173f864f0975578fc1b70f2ee48f75.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/1b2fb8b377d188c0aaa76590 |
| 524 | `4fecce318344` | 4fecce318344313f038fcf5cfe6f1414870d86776f049d6b48d79bd0491c2f22.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/4fecce318344313f038fcf5c |
| 525 | `19130dae312d` | 19130dae312d78a17c22dce29e5ce8fde2333032d8256bf1ea18b2d5d2ef42cf.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/19130dae312d78a17c22dce2 |
| 526 | `87080cc52b2d` | novel_87080cc52b2d | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/87080cc52b2ddc76d4b6b10c |
| 527 | `492aa8a38c12` | 492aa8a38c12c0140a8d16ba9fbcc29a09bb800b7af5eb61f2718ed371788add.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/492aa8a38c12c0140a8d16ba |
| 528 | `d1ccf3e4c211` | d1ccf3e4c2119191618ebded5144bdefecb480aab6d61bb325a5688fcdea8ae2.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/d1ccf3e4c2119191618ebded |
| 529 | `23d69c73ff03` | novel_23d69c73ff03 | novel-opponent | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/23d69c73ff03c7e28f87f5ca |
| 530 | `0eba22235e50` | 0eba22235e5056e59661bbade6c2ae3b5aa8c3bcdf8bb68d41441086339f9162.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/0eba22235e5056e59661bbad |
| 531 | `83a79ab14dbb` | 83a79ab14dbb1baf2b767d6791c7d3efa1921152d719d47bbe14d31bcf057440.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/83a79ab14dbb1baf2b767d67 |
| 532 | `9971efcdcf48` | 9971efcdcf487d3d05e7370362f59116b322ce3b4b0f60e2b01780532e5e3f01.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/9971efcdcf487d3d05e73703 |
| 533 | `23d78e2909fb` | 23d78e2909fb9ebd4f0dfa9098b35a0780e8c225baf7a760f2bd508ce1f4781f.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/23d78e2909fb9ebd4f0dfa90 |
| 534 | `3b709806c3f4` | 3b709806c3f4a02426e22077aaab2136730d41b103a37fd1b25bca32f4373933.py | archived-variant | generated 'Player' opponent | R1 | 0.4375 | 16 | 0 | archive: architectures_v2/…/3b709806c3f4a02426e22077 |
| 535 | `15958cc8debf` | 7d86c971d496e61ba63ce1800ba21b72c5fd23f1e98e13dbd9c13493a6b4a733.py | evolved-genome | tiny evolved Rival | R1 | 0.4375 | 16 | 0 | archive: evidence/…/7d86c971d496e61ba63ce180 |
| 536 | `8fb32ee24081` | opponents/opp_bait_01.py | opponent-field | other #41 | R1 | 0.4375 | 16 | 0 | opponents/opp_bait_01.py @ b9e9751 |
| 537 | `9d72d64657ca` | 9d72d64657ca4b9bcc333a3e08a62698782ab8e9273855dfed357235dd741496.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/9d72d64657ca4b9bcc333a3e |
| 538 | `885b73a29a3a` | opponents/opp_farmer_03.py | opponent-field | other #43 | R1 | 0.3750 | 16 | 0 | opponents/opp_farmer_03.py @ b9e9751 |
| 539 | `264686ac90e1` | 264686ac90e138a8d79809e6b435559c9dc247118dba2b49946ce6dad27b15fe.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/264686ac90e138a8d79809e6 |
| 540 | `60128841971e` | 60128841971ef7baab12e3044e5fb02fd3a8b9d3e14623b176dbcc3227c072b0.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/60128841971ef7baab12e304 |
| 541 | `588286ad51ca` | novel_588286ad51ca | novel-opponent | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/588286ad51caa9880d6d8e53 |
| 542 | `3723c6975fea` | 3723c6975fea0e051539fbaa8a2e2707052410898c07bd8289c1df3c857d2429.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/3723c6975fea0e051539fbaa |
| 543 | `78aaeea82ba2` | 78aaeea82ba297ad3eef8c575787c36ef57741592fa83155e7a1f809200f3497.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/78aaeea82ba297ad3eef8c57 |
| 544 | `ce772ce88a29` | ce772ce88a29e039a542d81bec437367022af0948acaf44307e8ab631111a8bd.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/ce772ce88a29e039a542d81b |
| 545 | `4793fc4de68e` | novel_4793fc4de68e | novel-opponent | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/4793fc4de68e254af4100f62 |
| 546 | `070919242a55` | 070919242a55cb29c3455ee6fb12a8f2d7ffc463c3d3b73d6103b66b9cd4efc5.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/070919242a55cb29c3455ee6 |
| 547 | `036f50fabe2c` | 036f50fabe2c0bdb69729631b3827c4e2d777df558335d4995825388f4641bff.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/036f50fabe2c0bdb69729631 |
| 548 | `af776ab2af1c` | af776ab2af1cee9799cdf075510c4cc4e08c92e1d256a3027ee2e803e84be011.py | archived-variant | generated 'Player' opponent | R1 | 0.3750 | 16 | 0 | archive: architectures_v2/…/af776ab2af1cee9799cdf075 |
| 549 | `4d7c8e68b900` | c3f25a6914192146fd62497a46f995e9f0ad56a7ea5c2d4dd27f14f595147902.py | evolved-genome | tiny evolved Rival | R1 | 0.3750 | 16 | 0 | archive: evidence/…/c3f25a6914192146fd62497a |
| 550 | `1a08ff9195ce` | 1a08ff9195cefc121533582dc2cdb1fa67effd6d964df20de69e7d700456270c.py | archived-variant | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/1a08ff9195cefc121533582d |
| 551 | `0c34fb29b3d2` | 0c34fb29b3d2a178dd5f906af61011d8b1c9c4e9215a58f38c727ecc4381d284.py | archived-variant | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/0c34fb29b3d2a178dd5f906a |
| 552 | `3bc996cb3960` | 3bc996cb39602d19ef1be4f19b6e6ada20527d446cf3f3cbc48f389173481966.py | archived-variant | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/3bc996cb39602d19ef1be4f1 |
| 553 | `06a0e029abe4` | novel_06a0e029abe4 | novel-opponent | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/06a0e029abe440ea51dd4515 |
| 554 | `ac91e4cd9366` | ac91e4cd93668626fe37d2b5dd0e4e750811038c1d64d922e8c0b75bb21a58e2.py | archived-variant | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/ac91e4cd93668626fe37d2b5 |
| 555 | `8191e3172b84` | 8191e3172b8477e16dd447e7cdb1622b79e26049f705abb36e2a4710e42afdea.py | archived-variant | generated 'Player' opponent | R1 | 0.3125 | 16 | 0 | archive: architectures_v2/…/8191e3172b8477e16dd447e7 |
| 556 | `01084d4dcdec` | opponents/opp_turtle_gpt1.py | opponent-field | other #37 | R1 | 0.3125 | 16 | 0 | opponents/opp_turtle_gpt1.py @ 0e8b4a9 |
| 557 | `1f7ccdec4a24` | 56826bd865a4ab55572e56e3b610f1d97bfd13981dd96a1904ebd5f5410fb2d6.py | evolved-genome | tiny evolved Rival | R1 | 0.3125 | 16 | 0 | archive: evidence/…/56826bd865a4ab55572e56e3 |
| 558 | `c7620a987067` | opponents/opp_naive_02.py | opponent-field | simple act()-only bot | R1 | 0.3125 | 16 | 0 | opponents/opp_naive_02.py @ b9e9751 |
| 559 | `42bc3f43d67d` | 62fc5c2cb75265589b914430a67c227fb7faa0a098a5496b8e59f4c063c937f6.py | evolved-genome | tiny evolved Rival | R1 | 0.3125 | 16 | 0 | archive: evidence/…/62fc5c2cb75265589b914430 |
| 560 | `ebfa5e8b5162` | 6adbda3902d11f15fc8fe1b5768fb44bda8739de6e15d2817e567271430916de.py | evolved-genome | tiny evolved Rival | R1 | 0.3125 | 16 | 0 | archive: evidence/…/6adbda3902d11f15fc8fe1b5 |
| 561 | `6954147c89f5` | novel_6954147c89f5 | novel-opponent | generated 'Player' opponent | R1 | 0.2500 | 16 | 0 | archive: architectures_v2/…/6954147c89f56eac85c5a715 |
| 562 | `66f73201fca1` | 66f73201fca1902a0bf1bb892578e2d8b0c7b8c9e08304d7c8d6bf01575b1c4a.py | archived-variant | generated 'Player' opponent | R1 | 0.2500 | 16 | 0 | archive: architectures_v2/…/66f73201fca1902a0bf1bb89 |
| 563 | `b0339dc0720f` | b0339dc0720fd42edd1d786371180d5a851b29f486cc2db4be5e12ce75c61fe3.py | archived-variant | generated 'Player' opponent | R1 | 0.2500 | 16 | 0 | archive: architectures_v2/…/b0339dc0720fd42edd1d7863 |
| 564 | `ea4d3771a167` | 46c984c5227ddb3c10f0753819c9d0ce0a6e26e1e352b258b464937104a4a0fc.py | evolved-genome | tiny evolved Rival | R1 | 0.2500 | 16 | 0 | archive: evidence/…/46c984c5227ddb3c10f07538 |
| 565 | `97c5ab4c97b6` | 5b9ab664a41e5f47fee2e12d1a1dd3f14f01e727bb2ecdf89083c6fed53aed21.py | evolved-genome | tiny evolved Rival | R1 | 0.1875 | 16 | 0 | archive: evidence/…/5b9ab664a41e5f47fee2e12d |
| 566 | `cafa58d3140c` | e3accb4a46596a157f0c2291d487b19d3235e788c44be5c029f57202806f617f.py | evolved-genome | tiny evolved Rival | R1 | 0.1875 | 16 | 0 | archive: evidence/…/e3accb4a46596a157f0c2291 |
| 567 | `df8ae3ce630e` | 95884cdbeef20c985d1687ee7c63ba99e16d28c9d18c56f5fd97062ded37004c.py | evolved-genome | tiny evolved Rival | R1 | 0.1875 | 16 | 0 | archive: evidence/…/95884cdbeef20c985d1687ee |
| 568 | `75d5ad95bb84` | ecdb930ba0e5977afe9e58cb92c83280f6f5dad4ed01d448506b411f2adbae76.py | evolved-genome | tiny evolved Rival | R1 | 0.1875 | 16 | 0 | archive: evidence/…/ecdb930ba0e5977afe9e58cb |
| 569 | `0c64624cbe69` | opponents/opp_centrerusher_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.1875 | 16 | 0 | opponents/opp_centrerusher_gemini1.py @ 0e8b4a9 |
| 570 | `b1c03b05de5a` | 85494cdb0619c62f3c32f25cb949c483294b72392d2ad62c37eb4bbbd6fdf49e.py | evolved-genome | tiny evolved Rival | R1 | 0.1875 | 16 | 0 | archive: evidence/…/85494cdb0619c62f3c32f25c |
| 571 | `0b826e99381a` | opponents/opp_planner_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.1875 | 16 | 0 | opponents/opp_planner_gpt1.py @ 0e8b4a9 |
| 572 | `9496320d0850` | 9408af255ee060dc80cdf042eeb62ee34fe9ba9fae3c60adbc3c53560af21a10.py | evolved-genome | tiny evolved Rival | R1 | 0.1250 | 16 | 0 | archive: evidence/…/9408af255ee060dc80cdf042 |
| 573 | `b1f56f1d2d28` | 38e4e6a0f8ed73aa3057975fab4802da2fec989812b21420b11a5109438457be.py | evolved-genome | tiny evolved Rival | R1 | 0.1250 | 16 | 0 | archive: evidence/…/38e4e6a0f8ed73aa3057975f |
| 574 | `75c815b0e25e` | 31cb400e297074bf03de61425517d892231c9bdfaa17f06963cb8b754d0cc0e7.py | evolved-genome | tiny evolved Rival | R1 | 0.0625 | 16 | 0 | archive: evidence/…/31cb400e297074bf03de6142 |
| 575 | `2956bbd05ffc` | opponents/opp_shield_02.py | opponent-field | other #31 | R1 | 0.0625 | 16 | 0 | opponents/opp_shield_02.py @ b9e9751 |
| 576 | `261f10170209` | opponents/opp_shield_01.py | opponent-field | other #21 | R1 | 0.0625 | 16 | 0 | opponents/opp_shield_01.py @ b9e9751 |
| 577 | `1f39121ab611` | 0b1ab83af2078f0df4af850879a71c55fe3c9dd8705a8532af9038496200bea0.py | evolved-genome | tiny evolved Rival | R1 | 0.0625 | 16 | 0 | archive: evidence/…/0b1ab83af2078f0df4af8508 |
| 578 | `651f76d932b5` | 26c53cbb105668e5ab19843ae153c04e3ae3308d57007ab1d7f50252079f11dd.py | evolved-genome | tiny evolved Rival | R1 | 0.0625 | 16 | 0 | archive: evidence/…/26c53cbb105668e5ab19843a |
| 579 | `c7098ef641a0` | opponents/opp_greedy_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.0625 | 16 | 0 | opponents/opp_greedy_gemini1.py @ 0e8b4a9 |
| 580 | `41b44e06e3c1` | opponents/opp_centrerusher_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.0312 | 16 | 0 | opponents/opp_centrerusher_gpt1.py @ 0e8b4a9 |
| 581 | `0bab0e69ac16` | 889f2b6aed727065e1e685b4eeed1b3e81a2e3f9b0267e9cdcbef0f362d81367.py | evolved-genome | tiny evolved Rival | R1 | 0.0000 | 16 | 0 | archive: evidence/…/889f2b6aed727065e1e685b4 |
| 582 | `3a50a56aa9ae` | opponents/opp_naive_05.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_naive_05.py @ b9e9751 |
| 583 | `b73d70bcda60` | b73d70bcda60235d5b751f154f305cb8fefef7286b54920d7f75b01d13e2c4a3.py | archived-variant | other #8 | R1 | 0.0000 | 16 | 0 | archive: architectures_v2/…/b73d70bcda60235d5b751f15 |
| 584 | `2ce4d9d7fca6` | harness/bots/random_bot.py | starter/skeleton | simple act()-only bot | R1 | 0.0000 | 16 | 0 | harness/bots/random_bot.py @ 8f4c650 |
| 585 | `4b5659bf878a` | opponents/opp_buggy_03.py | opponent-field | other #31 | R1 | 0.0000 | 16 | 0 | opponents/opp_buggy_03.py @ b9e9751 |
| 586 | `c71e621ccba0` | safe_floor_bot.py | archived-variant | simple act()-only bot | R1 | 0.0000 | 16 | 0 | archive: outputs/…/safe_floor_bot.py |
| 587 | `1d6702f7400f` | opponents/opp_farmer_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_farmer_gemini1.py @ 0e8b4a9 |
| 588 | `98c622e3bf72` | opponents/opp_bait_02.py | opponent-field | other #13 | R1 | 0.0000 | 16 | 0 | opponents/opp_bait_02.py @ b9e9751 |
| 589 | `2775aa3d6d40` | harness/bots/skeleton.py | starter/skeleton | simple act()-only bot | R1 | 0.0000 | 16 | 0 | harness/bots/skeleton.py @ 8f4c650 |
| 590 | `dbe1f0f1560b` | official_bot.py | archived-variant | simple act()-only bot | R1 | 0.0000 | 16 | 0 | archive: outputs/…/official_bot.py |
| 591 | `479793996c3b` | 479793996c3bf8afd8df9614699f7cd8793c9a473b838bc08a659c14bf3f0b99.py | archived-variant | other #8 | R1 | 0.0000 | 16 | 0 | archive: architectures_v2/…/479793996c3bf8afd8df9614 |
| 592 | `0a0c24fbdc95` | opponents/opp_turtle_gemini1.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_turtle_gemini1.py @ 0e8b4a9 |
| 593 | `b5f0ef1b2796` | opponents/opp_naive_gemini2.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_naive_gemini2.py @ 0e8b4a9 |
| 594 | `719977e69948` | opponents/opp_adaptive_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_adaptive_gpt1.py @ 0e8b4a9 |
| 595 | `729a5e5a3b06` | opponents/opp_opportunist_gpt1.py | opponent-field | simple act()-only bot | R1 | 0.0000 | 16 | 0 | opponents/opp_opportunist_gpt1.py @ 0e8b4a9 |
