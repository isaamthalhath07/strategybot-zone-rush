# Strategy and fair-play review — 7 November 2026

This review distinguishes rule correctness, heuristic forecasts, and measured playing strength. A legal correction can improve a calculation while weakening a policy whose weights were tuned around the old calculation. Unknown opponents and an unavailable official referee prevent an honest claim of perfection or guaranteed victory.

## Rules and intended interface

The primary sources are [the official starter README](https://github.com/RedPokerJoker123/StrategyBot/blob/main/README.md) and the local [nine-page rulebook](StrategyBot_RuleBook.pdf). The detailed checklist and source hashes are in [the independent rules audit](audit/rules_audit.md).

- Four bots, 8×8 mirrored integer-value map, 80 simultaneous turns. Movement precedes work, then income is paid, then the priority token rotates.
- Initially occupied cells stay closed for that turn; arrival does not itself capture. A blocked move counts as STAY. Moving owners win contested entry; otherwise cyclic priority decides.
- One STAY captures neutral or rival level-one territory; three capture rival level two. Three STAYs upgrade owned level one. Moving, shielding, and freezing reset work progress.
- A successful raid pays `8 × base value × old level`; the cell becomes level one. Work completed this turn earns this turn's income. Homes cannot be captured, including when a rival occupies them.
- A shield catches eligible rivals who STAY on owned land, including homes. It freezes caught rivals for two turns; catching nobody backfires. The next four turns are on cooldown.
- Round 1 compares scores only: equal scores draw. Round 2 breaks score ties by cells; remaining ties depend on stage. The old local referee wrongly used cell counts for Round 1. This is corrected and regression-tested.
- The single submitted `bot.py` must expose `act(state)`, use only the standard library, leave input unchanged, and return a listed legal action within 200 ms (2 s first turn).

History-derived estimates are permitted: the official README allows globals during a game. The submission reads public board fields, seat, token Boolean, and legal actions; it does not read the local engine, files, network, or opponents' code. Local testing internals are observer data and are not supplied to the policy. AI assistance is explicitly allowed. Collusion, inter-team code sharing, interfering with the referee, multiple entries, and exploiting server bugs are prohibited.

The reported private clarification that frozen forced STAY gives no progress cannot be independently authenticated from the public material. The official server remains authoritative. The test map distribution is also a local modeling choice; flat and independently mirrored maps are therefore included in robustness checks.

## Competing approaches

This is a comparison of the important strategy families, not an enumeration of every possible history-dependent policy.

| Approach | Advantage | Failure mode / when to avoid it |
|---|---|---|
| Broad early expansion | Recurring income compounds over many turns | Travel and low-value cells consume scarce actions |
| Safe quadrant farming | Predictable income with little conflict | Concedes contested high-value cells and can be outgrown |
| Immediate home upgrade | Permanent additional income, immune to capture | A low-value home delays more productive opening work |
| Marginal-value target ranking | Fast, broad coverage, simple adaptation | Misses clusters and interactions between successive jobs |
| Route beam search | Prices multi-cell travel and commitments together | Candidate pruning and opponent forecasts can miss the best route |
| Claim-and-upgrade visits | Avoids a later return trip | Locks up four turns and increases the bounty available to raiders |
| Centre rush | Takes valuable contested income early | Long approach, collision risk, exposed ownership |
| Cheap level-one raids | One work turn buys land, bounty, and denial | Shields and counter-raids can erase the advantage |
| Level-two raids | Larger immediate bounty | Three work turns expose the attacker repeatedly |
| Raid-first aggression | Bounties retain value late; can swing close pairings | Attacking one rival often benefits two uninvolved rivals |
| Permanent camping | Occupancy prevents entry | Gives up productive work elsewhere |
| Never shield | Preserves all productive actions | Concedes easy, valuable raids |
| Shield on sight | Punishes committed simple raiders | Predictable baiting causes backfire and cooldown |
| Adaptive defensive shielding | Learns commitment from observed history | Sparse observations and deterministic thresholds remain exploitable |
| Placement-aware denial | Targets pairings that can still change | Forecast errors and multiplayer externalities can waste actions |
| Pure self-play learned policy | Can discover unprogrammed behavior | Existing learned policy lacks effective route planning and is weak in local tests |

The strongest supported architecture remains route-based economic planning, selective raids, and adaptive defence. That is a practical hypothesis supported by this project's opponents, not a Nash-equilibrium result. Historical strategy-sweep scores in README/EXPLAINED used earlier policies and the old ranking implementation; they are historical evidence, not fresh measurements of this build.

## Concrete defects and experiments

Independent reviewers reproduced these defects:

1. **Missing completion-turn income.** On the final turn, a bot on a neutral three-point cell could leave for a one-point outcome instead of capturing for four. Basic and upgraded completion income, including the intermediate claim phase of a combined visit, need inclusive counting.
2. **Banked progress survived a hypothetical departure.** A beam route could leave a nearly completed upgrade and return while still paying only the reduced work cost. A real move resets that progress.
3. **Immune homes were priced as capturable losses.** Catching a home visitor can have tempo value, but it cannot prevent a home capture.
4. **Impossible final captures triggered shields.** A rival with zero of three required stays cannot complete the capture on the final turn.
5. **Geometric ties assumed seat-to-corner assignment.** The interface exposes actual homes; using them avoids an undocumented seat convention.
6. **An attempted idle baseline was rejected.** Although an idle comparison looked reasonable on own or neutral land, the limited route surrogate omits opportunities revealed by movement. Adding a zero-value idle floor caused paralysis and measurable losses, so it is absent from the final submission. STAY on enemy land also commits a raid and can be shielded.

The first 120 fresh stranger games compared the original policy to an income-only correction: `2.692 → 2.725 PW/3`, paired difference `+0.0333`, SE `0.0263`. This is not statistically significant. Raw outcomes: [income experiment](audit_strategy_strangers_631781_120.json).

A subsequent 600-task comparison rejected the combined corrections: main-field differences were `−0.0563` against strangers, `−0.2875` against peers, and `−0.1844` against mixed opponents. Peer and mixed confidence intervals excluded zero. No illegal action, input mutation, escaped exception, or swallowed planner exception occurred across 384,000 observed calls. A concurrent source edit was detected at the end; the worker policy was fixed at initialization, but this report retains the source-provenance caveat. See [raw paired evidence](audit/comparison.json).

An eight-way, 100-task causal comparison isolated the idle floor: `−0.2300 PW/3`, SE `0.0601`. Work-income counting alone was level, candidate-priority counting `+0.030`, both income changes `+0.010`, defence `+0.020`, and progress/home-frame changes were identical on that sample. These small individual differences are not established gains. [Raw ablation evidence](audit_ablation_peer_920771_100.json) and exact source snapshots preserve all alternatives. The final submission removes the idle floor and retains the rule-grounded bookkeeping and feasibility corrections.

Opponent parameter snapshots are insufficient by themselves: they instantiate the current implementation. Fresh comparisons freeze the *implementation* in [baseline_mybot.py](audit/baseline_mybot.py), so changing our bot does not move the opponent goalposts.

## Final independent confirmation

The corrected candidate was copied byte-for-byte into [an immutable candidate snapshot](audit/final_candidate_mybot.py), then compared on a fresh seed `202611079`. Its executable code and merged parameters match the generated `bot.py`. Every main field uses 160 paired tasks; every stress field uses 40. Seats and priority-token starts are balanced. Stress maps include canonical, independently mirrored, all-one, and all-three boards. The final run passed its source-hash guards.

| Field | Original PW/3 | Corrected PW/3 | Paired difference, 95% CI |
|---|---:|---:|---|
| Unfamiliar designs | 2.7625 | 2.7625 | 0.0000 [−0.0248, +0.0248] |
| Frozen peers | 1.7781 | 1.7406 | −0.0375 [−0.1051, +0.0301] |
| Mixed field | 1.9094 | 1.8844 | −0.0250 [−0.0640, +0.0140] |
| Unfamiliar designs, stress maps | 2.6750 | 2.7250 | +0.0500 [−0.0206, +0.1206] |
| Frozen peers, stress maps | 1.9375 | 1.9625 | +0.0250 [−0.0892, +0.1392] |
| Mixed field, stress maps | 1.7750 | 1.8500 | +0.0750 [−0.0583, +0.2083] |

None of these intervals establishes improvement or regression. **Failure to detect a difference does not prove equivalence or noninferiority.** The corrected build addresses reproduced rule arithmetic and route-feasibility defects; it is not advertised as a statistically stronger tournament policy. The original implementation remains available for comparison.

There were 600 paired tasks, 1,200 games, and 384,000 observed calls, with zero illegal actions, input mutations, escaped exceptions, swallowed planner exceptions, or timing diagnostics. Pinned-clock policy timing peaked at 33.250 ms for the corrected candidate. [Raw outcomes and source hashes](audit/final_comparison.json) bind this conclusion to the tested implementation. Intervals are descriptive task-level intervals, without a multiple-comparison adjustment.

The transfer diagnostic also completed using the committed v7 weights instead of a nonexistent live-tuner output: tuned versus untuned training performance `2.91 vs 2.54`, held-out archetype performance `2.81 vs 2.30`. This older diagnostic checks tuned weights against defaults; it does **not** establish a gain over the original v7 implementation. [Transfer output](audit/transfer_validation.log).

## Remaining strategic weaknesses

- Future beam raids estimate shield risk using the last travel leg. This is an optimistic forecast, not proof that an observed current cooldown will still protect a later raid. A naive elapsed-time correction lost about `0.138 PW/3` in an exploratory 80-game test; it requires calibration and new validation before promotion.
- The v7 defensive parameters make accepted shields deterministic. Acceptance requires `gain ≥ 2.351882 × cost`, so the computed mixing probability is at least `0.5748`, above `shield_certain = 0.5410`. Learning can adapt to baiting, but there is no demonstrated equilibrium guarantee.
- Candidate pruning, a finite horizon, assumed future ownership, stationary opponent forecasts, and a single approximate value function prevent global optimality.
- Historical opponents come from this project. Two additional [independent challengers](audit/independent_design.md) were authored from the rules with fixed constants and no submission matchup tuning. They add diversity but cannot represent every unknown competition entry.

## Visual evidence

[Open the standalone replay viewer](visual/index.html). It supports playback, stepping, scrubbing, selecting matches, and inspecting cells. It records actual calls to the submitted `act(state)`, requested and resolved actions, scores, income, freezes, cooldowns, and contract failures. The bot receives only public views; the observer can inspect referee internals.

This is explicitly a **local** visual harness. The public repository provides no referee or Arena URL, and no official URL was available in this session. It does not certify equivalence with the competition server. Strong-opponent losses remain visible.

The final viewer contains five complete games and 1,600 recorded actions, with zero observed contract failures. In the strong-opponent example the submission still finishes third (2,258 behind 2,558 and 2,707). Against the two newly authored challengers plus ProBot it finishes second: 2,415 behind ProBot's 2,642. It wins the raid-pressure and diverse-architecture examples; four independent submission modules tie at 2,168. These examples are inspection evidence, not a tournament win-rate estimate.

The viewer was exercised in a real browser: forward/back stepping, timeline to turn 40, cell inspection, automatic playback to turn 44, match switching, and jumping to turn 80. All 64 board cells and score/action panels updated; the browser console reported no messages. Three replay-evidence tests independently replay every accepted action through the engine and verify every saved board/score plus current bot/engine/opponent source hashes.

Shipping verification passed: standard-library imports, exact `act(state)` signature, identical play to the development bot, independent state for shared-module seats, zero internal planner exceptions, useful fallback behavior, and 40 stress games with no illegal outputs or failures. Worst call was 25.8 ms, p99 22.6 ms, mean 8.2 ms, with actual time guards enabled. A separate final public-input contract check passed 1,280 calls, no mutation or illegal/late output, worst 23.329 ms. These are measurements on this machine, not a grader-runtime guarantee.

Final `runtests.py fast` exited successfully: rule examples plus 400 fuzz games, 9,600 tensor/reference state comparisons, tracker checks, 11 planner regressions, deterministic repeated measurements, guards, timing degradation, amnesia, shipped input contract, replay evidence, and seat symmetry. The behavioral audit marks three *opponent* designs for inspection; this is a CHECK result rather than a submission failure. The slower robustness suite passed in the earlier full run; that run's transfer diagnostic initially failed because its default live-tuner file did not exist. The default now names v7 and the transfer diagnostic was rerun successfully. See [final suite log](audit/final_validation.log), [earlier full-suite log](audit/validation.log), and [transfer rerun](audit/transfer_validation.log).

[Artifact verification](audit/final_artifact_verification.json) also confirms the final frozen policy's executable AST and parameters match `bot.py`, all comparison source guards passed, visual hashes match, and the current development source still matches the tested snapshot. This verification can be repeated with `python audit/verify_final_artifacts.py`.

Reproduction commands:

```powershell
python ship.py v7_params.json
python visual_harness.py
python test_visual_harness.py
python runtests.py
python audit_compare.py --current-source audit/final_candidate_mybot.py --games 160 --map-games 40 --workers 4 --seed 202611079 --check-input --out audit/final_comparison.json
```

Policy comparisons pin timing guards to remove machine-load noise. Shipping and visual tests keep the actual timing guards enabled. Their runtime evidence must be reported separately. Do not train on a held-out set and continue calling it held out.
