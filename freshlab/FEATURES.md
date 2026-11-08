# Useful features, opponent learning, and the measured release

This experiment started from commit `6aaa644` on `codex-audit-and-robustness`.
The earlier conversation's v7 results do not describe all corrections now in
that build. The exact starting implementation is preserved in `baseline.py`;
the old standalone submission is preserved in `previous_submission.py`.

## What improved

The accepted change adjusts three existing economic coefficients, selected
using **only newly generated opponents**:

| Coefficient | Starting value | Accepted value |
|---|---:|---:|
| `raid_risk` | 1.592515 | 1.194386 |
| `w_raid` | 1.648359 | 1.401105 |
| `w_raid_late` | 1.432168 | 1.217343 |

This lowers the interception penalty and also lowers how highly raid profits
are valued. It is a joint recalibration: its effect cannot be attributed to
either coefficient independently. It does **not** mean "raid more everywhere".
The route search and existing history tracker are retained.

| Stage | Paired tasks | Baseline PW/3 | Candidate PW/3 | Difference, 95% interval |
|---|---:|---:|---:|---|
| Discovery | 256 | 2.2305 | 2.3242 | +0.0938 [+0.0203, +0.1672] |
| New development algorithms | 384 | 2.2526 | 2.2852 | +0.0326 [-0.0300, +0.0951] |
| Locked final algorithms | **1,024** | **2.1523** | **2.2275** | **+0.0752 [+0.0393, +0.1111]** |
| Balanced blocks, four further new algorithms | **1,024** | **1.9639** | **2.0210** | **+0.0571 [+0.0221, +0.0922]** |

Development alone was inconclusive. The confirmatory final result supports a
gain against this new synthetic distribution. It does not estimate Elo against
real entries, prove global optimality, or guarantee performance against every
map or opponent. Rich-corner maps measured -0.0078 with a wide interval; the
other map subgroup point estimates were positive. All three final algorithm
exposure groups measured positive. Those overlapping subgroup intervals are
descriptive and not separately adjusted for multiple comparisons.

The first final schedule cycled maps and seats together. It balanced seats
overall, but did not balance every map against every seat/token combination.
That result describes its actual paired schedule, not every possible crossing.
An additional registration therefore kept the candidate **unchanged**, added
four further unused algorithms (`unseen.py`), and measured every one of the 16
seat/token combinations within each map block (`confirm.py`). It also supported
a gain. Rich-corner maps remained slightly negative (-0.0430, interval
[-0.1555, +0.0696]); no claim of subgroup noninferiority is made.

`v8_fresh_params.json` is the complete accepted configuration. `bot.py` was built
from it. It contains no new dependency or online model from this directory:
the new style model is still experimental because it did not establish added
playing strength. The exact exported policy was checked against the measured
candidate for 1,280 actions. Release hashes are in `release_verification.json`.

## Can learning the opponent's style work?

Yes for specific predictions, with an important distinction: predicting better
does not automatically mean playing better.

An 80-turn game rarely supplies enough evidence to recover another bot's whole
algorithm. A player-level label such as "aggressive" discards useful context.
The tested model instead estimates:

- **Defence:** will player j shield an imminent capture, given the cell's level,
  value class and whether the game is late?
- **Commitment:** will player j stay on rival territory, given whether the
  defender can shield and the cell's level?
- **Dwell:** will player j continue working on its own unfinished upgrade?

### Observe choices, not forced outcomes

The following must not teach the model the wrong lesson:

| Public observation | Incorrect interpretation | Treatment here |
|---|---|---|
| Frozen bot stays | "It commits to raids" | Censor: it had no choice |
| Defender on cooldown does not shield | "It never defends" | Censor: it had no choice |
| Upgraded raid still needs three STAYs | "It ignored an imminent capture" | Record no imminent-defence sample |
| Three intruders see one shield | Three independent shield decisions | One decision per defender-turn |
| A rival freezes on someone else's cell | The landlord definitely shielded | Enumerate explanations; label only unanimous cases |
| Bot remains while a possible exit becomes occupied | It voluntarily committed | Censor possible failed escape/contest |
| Visitor stays on a home | A capturable cell is threatened | Exclude from capture-defence learning |

An observer harness compared inferred labels with the referee's actual resolved
actions. The actual actions were **never supplied to the played policy or its
model**. There were **0 wrong labels out of 3,108** in 80 games. There were 83
ambiguous transitions and one unexplained transition, on which the model
abstained. This is sample evidence, not a proof of perfect attribution.

### Use conservative probabilities

For a player with y observed commitments/shields in n eligible choices:

```
pooled = (prior_strength * prior + y) / (prior_strength + n)
context_probability = (4 * pooled + context_successes) / (4 + context_count)
```

This shares sparse evidence across contexts without treating one move as a
personality. Candidate variants require at least four eligible observations,
blend learned estimates slowly, and fade distant forecasts back toward the
prior. Each new game resets the model. No opponent identity, implementation,
parameter set or secret state is read.

On fixed baseline trajectories, lower Brier loss means better probability
predictions:

| Prediction | Fixed prior | Per-player average | Context model |
|---|---:|---:|---:|
| Shielding, 725 labelled choices | 0.2922 | 0.1692 | **0.1501** |
| Commitment, 2,383 labelled choices | 0.3223 | 0.2100 | **0.1759** |

Context reduced prediction loss by about 11% and 16% versus a single average per
player. These are prequential results: each probability was computed before its
outcome updated that game's model. They are observational prediction metrics,
not confidence intervals on the policy's tournament score.

### Why the new learner did not ship

The initial defence variant also changed how a three-STAY raid accumulates
interception risk, and lost **0.2083 PW/3** in discovery. Separating that change
from the learned estimate removed most of the loss. Gating adaptation on at
least four observations produced only **+0.0039**, with an interval spanning
zero. With the economic recalibration, the learned and static policies then
tied on the development algorithms: both gained +0.0326.

The simpler static policy was therefore registered for the final test. Selecting
the more complicated model merely because its prediction metric improved would
have been an unsupported promotion.

## Other features implemented and tested

| Feature | Mechanism | Result this round |
|---|---|---|
| Conditional shielding | Context-specific public-history risk | First version harmed play; conservative aligned version inconclusive |
| Conditional raid commitment | Distinguish risky and unanswerable raids | Better prediction; no established policy gain |
| Uncertainty penalty | Treat sparse risk estimates conservatively | Included in exploratory variants; no accepted gain |
| Correct future cooldown timing | Future beam jobs cannot use today's expired window | No established aggregate gain in this experiment |
| Occupied-cell dwell | Avoid waiting for a bot still upgrading | Rarely changed actions; no accepted gain |
| Exact final-turn payoffs | Compare captures, bonuses, upgrades and defence by final placement | Conditional arithmetic passed reference tests; policy gain inconclusive |
| Removing deterministic shield thresholds | Use the existing probability instead of always shielding above a threshold | -0.0195 on discovery, interval spanning zero; rejected |
| More expansion / more consolidation | Shift claim/upgrade investment | Both inconclusive or negative |
| Joint raid recalibration | Reduce risk penalty and profit weight together | **Accepted after final architecture-held-out test** |

The final-turn resolver evaluates up to 27 opponent action-class combinations.
Its point arithmetic is checked against the engine conditional on the assumed
STAY, SHIELD and successful-MOVE actions. Opponent probabilities remain
forecasts; blocked/contested moves are represented by STAY mass and are not
clairvoyantly resolved. Exact arithmetic alone therefore does not prove an
optimal final-turn policy against unknown simultaneous choices.

## Next promising additions, with the test each needs

No finite list covers every history-dependent policy. These are concrete
directions ranked by their connection to the rules:

1. **Joint defensive value.** A shield catches all eligible intruders; probability
   of any catch differs from the largest individual commitment probability.
   Test multi-intruder cases and actual economic opportunity cost together.
2. **Small policy mixtures.** Maintain posterior weights over a few plausible
   decision rules from observed actions. Require a proper out-of-sample next-
   action prediction gain before using it for move contests or raid baiting.
3. **Detect strategy changes.** Compare a short recent window with the cumulative
   estimate. Revert toward the prior when the two disagree. Reserve bots that
   switch in a different way from any training bot for the evaluation.
4. **Survival-weighted ownership.** Value income only as long as the bot is likely
   to hold the cell. Learn approach, raid and retention probabilities separately;
   do not reduce every exposed cell by a fixed arbitrary penalty.
5. **Short exact raid/retreat games.** Use a small joint-action search around a
   border encounter, preserving simultaneous moves, cooldowns, progress resets
   and body blocking. Do not assume an adversary sees our selected action first.
6. **Competition for future work.** Predict which cells are likely to be claimed
   before we arrive. Check for the replanning oscillation that previously broke
   this planner, and keep a committed plan unless the alternative is clearly
   better.
7. **Compute where it matters.** Spend more search on near-equal plans and keep
   cheap decisions cheap. Test real wall-clock limits separately from policy
   comparisons with deadlines removed.

## Anti-overfitting protocol used here

- No old zoo bot, competitor, previous policy snapshot or bred counter appears
  as a training opponent. The initial focal policy retains its previously
  learned weights, as the fixed baseline being improved.
- Every task creates three new random opponent parameter sets. No generated
  opponent is optimised against this submission or accepted/rejected according
  to how well it beats us.
- Discovery, development and final use disjoint scheduling families and seeds,
  with new map seeds and per-game parameters. Common map distributions recur;
  only rich-corner and inverted distributions are withheld until final testing.
  Shared observation plumbing is a limitation;
  these are not twelve independently authored programs.
- Both sides of a pair receive identical maps, seats, tokens and opponent draws.
  Time-based search truncation is disabled during policy comparison.
- Exact source hashes bind every successful run. One exploratory run was
  discarded and rerun after the source-change guard fired; no result from that
  run enters the selection.
- Discovery evaluates several proposals; its significance is exploratory.
  Development chose between the two strongest proposals and preferred the
  simpler one on a tie.
- The final candidate, its exact code hashes, the seed, sample size and promotion
  criterion were written to `final_registration.json` **before final games**.
  The final set was run once. It may now be reported, but must never be reused
  for later selection while called "held out".
- Rich-corner and inverted maps were withheld from discovery. Final subgroup
  outcomes are all published rather than filtering inconvenient losses.

There were **10,624 recorded comparison games**, **3,399,680 observed action
calls**, and **10,176 distinct sampled opponent parameter sets** in the seven
main experiments. Calibration, smoke tests and shipping checks are additional.
The checks observed no illegal action, input mutation or internal planner
exception in the recorded comparisons. Every new inference and payoff test
passed. This does not prove there are no undiscovered defects.

The standalone release passed `ship.py` (40 stress games, zero failures, worst
25.7 ms on this machine) and the independent public-input check (1,280 calls,
no illegal, mutated or late output, worst 14.2 ms). The visual replays were
regenerated from the new bot and replay-verified. Older audit reports still
describe their original frozen artifact; they are historical evidence, not
validation of this release. New provenance is in `release_verification.json`.

Read `RESULTS.md` for all recorded comparisons and the final map breakdown.
Read `README.md` in this directory for commands and the test plan. None of this
establishes the strongest possible policy against unknown real competitors.
