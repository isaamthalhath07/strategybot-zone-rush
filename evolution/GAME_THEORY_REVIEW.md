# Mathematical strategy review

The existing bot is a useful foundation, but evolving its current 23 numbers is
not enough to remove every structural weakness. My recommended architecture is
the existing economic planner, a better public-history opponent predictor, and a
small tactical search that resolves simultaneous actions and scores official
pairwise outcomes. Keep evolution as the method for fitting and selecting these
components. A neural replacement has no demonstrated advantage here.

This review concerns parent `e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5`.
It changes no production file and certifies no universally optimal strategy.
Line numbers below refer to that frozen parent. Mathematical counterexamples
establish a model limitation; only independent closed-loop games can establish
that a proposed change makes a stronger bot.

## Findings that can be tested now

| Priority | Finding | Consequence | Next experiment |
|---|---|---|---|
| 1 | Second/third jobs reuse income valued at their original completion time. | Deeper planning can overvalue income that arrives late. | Four-arm arrival-clock/depth comparison; candidate files are already built. |
| 1 | The CPU coach optimizes score minus mean rival score. | It can recommend fewer official pairwise wins even at the terminal state. | Exact pairwise terminal utility; clearly labelled, calibrated continuation proxy. |
| 1 | Waiting to Shield assumes we retain a future defensive action. | A landlord can freeze us before the raider's completion attempt. | Condition the early-Shield guard on our ability to remain available. |
| 2 | Future rivals are static obstacles in the first route and mostly absent from later routes. | Missing races, interceptions, vacated paths and future contests. | Predict distributions of rival moves/targets from public history. |
| 2 | Shield miss probability multiplies marginal stay probabilities. | Correlated rival behavior can misprice backfires. | Compare independence, joint likelihoods and conservative correlation bounds. |
| 2 | Marginal cooldown sets discard joint correlations; support is not a posterior. | Search can evaluate impossible combinations or assign unjustified probabilities. | Weighted joint public-history particles, with approximation losses exposed. |
| 2 | One scalar league mean can discard specialists and hide cyclic matchups. | A stronger average candidate can gain an exploitable weakness. | Keep behavioral specialists and train independent best-response challengers. |

### A. Delayed recurring income is counted for too many turns

At lines 465–473, each job's reward is valued using its travel time from the
current position. Lines 517 and 538 reuse that reward after placing the job
second or third. The feasibility check accounts for elapsed time, but the
recurring-income reward does not. Postcapture upgrades at lines 520–526 already
use the delayed clock; that branch should not be changed for this experiment.

For a job whose completion time is `c`, remaining horizon is `L`, retention cap
is `R`, marginal income is `m`, and one-off cash is `b`, the consistent value is:

`V(c) = m * min(L - c + 1, R) + b`, for `c <= L`; otherwise zero.

For example, with eleven turns left, a neutral 3-point job originally costing
two turns is valued at 30. If another job and the intervening route delay its
completion to turn ten, only two scoring turns remain: its value is 6. A raid's
one-off cash must survive this adjustment; only recurring income ages.

The isolated experiment preserves the parent's strategy numbers, current risk
divisors, denial/upgrade multipliers, one-off raid cash, input handling, Shield
inference and tactical guards. It changes only second/third-job reward timing.
It does not solve future occupancy, changing ownership or defender behavior.

The fixed-prefix probe replayed 32 registered incumbent games, reproducing all
2,560 incumbent decisions. On the exact same public histories and derived
memory, the depth-three clock correction changed 14 recommendations: eight on
turns 41–64 and six on turns 65–80. It changed none on turns 1–40 in this sample.
The largest recorded weighted job correction was 360.72 to 76.52. These are
decision diagnostics, not fourteen proven improvements. Old weights may partly
compensate for the old optimism, so even a sound valuation correction can hurt
strength until retuned.

Files under `mathematical_candidates/` provide the correction, its depth-two
version, and the unchanged parent's depth-two control. Compare all four arms on
new maps and opponents, then independently confirm the chosen arm. Avoid
selecting the depth or retuning on the same final cohort.

### B. Official outcomes require rival-specific utility

For Round 1, use:

`U = sum_j [1(score_self > score_j) + 0.5 * 1(score_self == score_j)]`.

Raw score and mean score margin are different objectives. Terminal scores
`[101,100,100,100]` give the focal bot three pairwise wins and margin 1. Scores
`[200,201,202,1]` give it one pairwise win but a mean rival margin of 65.33.
A margin-based terminal teacher ranks these in the wrong order.

The current root uses score-gap-dependent denial weights, which recognizes part
of this issue. However, its positive baseline denial value still rewards hurting
very distant rivals; that can be useful under uncertain future income, but it is
not the exact marginal value of changing rank. The CPU beam coach explicitly
uses mean margin plus an income tail. It remains a diagnostic; do not treat its
action disagreements as optimality labels.

A nonterminal approximation can estimate each finishing score gap separately:

`U_hat = sum_j Phi((mu_self - mu_j) / sigma_j)`.

Here `sigma_j` represents calibrated uncertainty in a finishing-score difference,
not a secret counter. Then marginal denial of rival `j` is proportional to
`phi(gap_j / sigma_j) / sigma_j`: a close rival matters more than an already
unreachable one. This Gaussian approximation is a proposed model, not an assumed
truth. Compare it with empirical outcome prediction on held-out public features.
Use exact draws and wins at the real terminal state.

There is also a multiplayer reason to retain movement in terminal search. In the
constructed, legal turn-80 case in `mathematical_probes.py`, our move wins a
contest and forces a rival to STAY on a third rival's upgraded cell. That causes
a raid. Our own score remains 1,012, but the near-score third rival falls from
1,014 to 1,008. Our pairwise wins rise from one to two, even though our mean
margin gets worse. Both independent referees reproduce this example. Therefore
"arrival scores nothing, so prune all final moves" is not a valid general
pairwise-utility argument. This is ordinary documented contest/raid behavior,
not an exploit of the simulator.

### C. The option to Shield later can disappear

The early-Shield guard at lines 586–589 skips a raider on upgraded land until its
inferred progress is two. Waiting often saves a Shield and avoids an unnecessary
backfire. It assumes we can still act at the later completion attempt.

The probe constructs a complete legal opening prefix ending on turn 17:

- A stands on B's home at cell 7. B at 6 and D at 15 close both exits.
- C stands on A's upgraded 3-point cell 18, with one completed stay.
- A's public-history tracker is correct, including C's progress and cooldown
  support. A nevertheless recommends STAY.

If B shields and C stays, A freezes for two turns. C reaches progress two, then
captures next turn while A cannot shield. If A shields now, it catches C, remains
immune to B's Shield, and causes B's Shield to backfire. After two turns A's
scores are 129 versus 123, and C's are 84 versus 135. Both referees reproduce the
outcomes from the entire prefix. Opponents' hypothetical actions are stipulated
for this counterexample, not supplied to the real bot.

A narrow candidate should allow the early defense when the current landlord
could shield us and every unblocked exit is closed. Keep the ordinary wait guard
elsewhere. A broader tactical model should value both denying the raider and
preserving our own ability to act. This is a proposed experiment; one reachable
counterexample does not prove that always shielding early is profitable.

### D. Predict intent as a distribution

`_paths` treats current rival positions as blocked throughout its first-job BFS.
Later jobs use Manhattan distances and the original task table. This is safe for
the immediate action, but it can be pessimistic about paths rivals will vacate
and optimistic about later routes crossing occupied or contested cells.

Learn `P(next action | public history)` and, optionally, a distribution over a
small set of target cells. Useful public features include repeated direction,
approach to valuable cells, observed stationary commitment, current ownership,
estimated cooldown support, remaining work and priority uncertainty. A movement
predictor must distinguish intended movement from effective STAY: an observed
stationary player may have lost a contest. Treat unavailable intent as latent,
or use training-only action labels with strictly public decision features.

Before using a predictor in the bot, require better Brier/log-loss calibration
than simple persistence and uniform legal-action baselines on new opponent
instances and entire withheld families. Then test policy strength. A predictor
can have better action accuracy while making the bot weaker if its mistakes
occur at consequential Shield/raid decisions.

### E. Shield is a simultaneous mixed-strategy problem

A local illustration has attacker STAY/MOVE and defender DEVELOP/SHIELD, with
attacker surrogate payoff matrix `[[G,-F],[0,B]]`. Here `G` is the gain from an
undefended stay, `F` the freeze/progress-loss cost, and `B` the value of inducing a
backfire while moving elsewhere. In this illustrative zero-sum model:

`P(attacker stays) = B / (G+F+B)`;
`P(defender shields) = G / (G+F+B)`.

For `G=48,F=18,B=12`, these are 0.1538 and 0.6154. Both sides are indifferent
between their two actions. The four-player game is not this local zero-sum game;
the formula demonstrates why a deterministic threshold can be exploited, not a
universal prescription for Shield frequency.

Test small randomization only near measured tactical indifference, using a
private per-game RNG and recorded training seeds. A board-derived deterministic
seed remains predictable to an opponent with the public source and history.
Randomness can reduce average strength, so measure best-response resistance and
ordinary field performance together. It must never use rival seeds or hidden
controller identities.

With two raiders each having catch probability 0.6, independence predicts miss
probability 0.16. The same marginals permit miss probabilities anywhere from
zero to 0.4. The root's product at line 603 is therefore an independence model,
not a consequence of knowing those marginal probabilities. Linear expected
freeze benefit can still add across rivals; the backfire term cannot ignore
their dependence. Start by measuring joint calibration; if data are sparse,
compare a conservative miss bound with the current independence approximation.

## Which optimization methods fit this bot?

The following choices are engineering judgments for this code and budget, not
claims that an algorithm guarantees a better competition entry.

| Method | Benefit here | Main limitation | Recommendation |
|---|---|---|---|
| Current bounded population evolution | Preserves a strong single-file policy; parallel games; interpretable ablations. | Cannot invent missing features or fix structural value errors. | Continue as the control and parameter-fitting layer. |
| CMA-ES on continuous genes | Learns correlated changes, potentially useful for interacting economy/risk weights. | Noisy rank fitness, bound clipping and the two integer genes need explicit treatment. | Compare against the existing evolution at equal game budgets; enumerate/mutate depth and breadth separately. |
| Differential evolution | Simple population-based changes across a wide parameter space. | Can spend many games on large, poor moves; same structural limits as other gene optimizers. | An independent island, not an assumed upgrade. |
| Bayesian optimization | Useful when each semantic feature/configuration trial is expensive. | A noisy, partly discrete, discontinuous 23-gene space makes surrogate modelling harder. | Small expensive architecture studies; not the first choice for millions of cheap games. |
| Macro dynamic programming or richer route beam | Correctly accounts for completion times, ownership changes and service work. | Exact search over 64 cells is too large; opponent responses make the state richer. | Prototype top-K target search after the clock ablation. |
| Public-belief tactical search | Directly addresses rival plans, ambiguity, contests and Shield timing. | Model bias and hidden-state strategy fusion; expensive CPU rollouts. | Highest-priority architectural addition after value correctness. |
| PSRO-style league and exploiters | Retains counterstrategies and reveals nontransitive weaknesses. | Four-player joint profiles cannot be reduced to a single two-player payoff matrix without assumptions. | Add independent challenger training and specialist retention. |
| Small supervised predictor/value model | GPU training can produce a tiny inline model for standard-library inference. | Bad labels or leakage can train a persuasive but wrong policy; must export identical features. | Prefer this before a full neural actor replacement. |
| PPO/full learned actor | Can discover policies beyond hand-designed jobs. | Major new training problem, reward design, nonstationary rivals, deployment/export and sample efficiency. | Separate challenger research; no reason to discard the incumbent first. |
| CFR or whole-game equilibrium solving | Principled imperfect-information framework in suitable games. | Famous two-player zero-sum guarantees do not automatically apply to this four-player score game; whole state tree is enormous. | Local abstractions/research tools, not a quick "solve the game" claim. |

These judgments are informed by the original [CMA-ES tutorial](https://arxiv.org/abs/1604.00772),
[differential-evolution article by its authors](https://jacobfilipp.com/DrDobbs/articles/DDJ/1997/9704/9704a/9704a.htm),
[Bayesian-optimization paper](https://arxiv.org/abs/1206.2944),
[PSRO paper](https://arxiv.org/abs/1711.00832),
[PPO paper](https://arxiv.org/abs/1707.06347), and
[CFR paper](https://papers.nips.cc/paper_files/paper/2007/hash/08d98638c6fcd194a4b1e6992063e944-Abstract.html).
Their existence is not evidence that any one method improves this particular bot.

## Search and learning boundaries

The new public support filter is a useful improvement over independent cooldown
sets. Uniform probability over retained states is still not a calibrated
posterior: histories and hidden actions can have different likelihoods. Any
state cap must report discarded support and must not silently recreate a hidden
truth when the observations become inconsistent.

Keep focal decisions tied to information histories. Optimizing a different
future focal action for each indistinguishable hidden state is strategy fusion;
the existing common open-loop sequence avoids that error but sacrifices future
adaptation. A later information-set tree may branch on future public
observations, not on inaccessible sampled state. This distinction is documented
in the original [Information Set Monte Carlo Tree Search paper](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf).

All four players choose from the same pre-turn public board. A rival model must
not receive the realized candidate action before choosing its own simultaneous
action. Replaying the real future action tape after a hypothetical deviation is
also invalid: the rival would see a different subsequent board. Three rivals
need independent incentives in the normal opponent model; an omniscient hostile
coalition is a labelled stress test, not an estimate of ordinary play.

Offline training may use simulated outcomes as labels. No actual rival identity,
controller seed, private counter or future action enters a deployed decision or
a purported public-information coach. Exogenous randomness for our own search
and own policy is a different input from secretly reading opponents' randomness.
Source-pinned public-feature exports and identical-public-history tests should
check that boundary.

## Selection, overfitting and the large campaign

The initial best mutation led discovery but failed fresh confirmation. That is
exactly why a selection winner is not a release decision. The recorded 2,048
trial games and full independent replay demonstrate mechanics for those games;
they do not prove generalization. A source-correct clock fix also needs a fresh
comparison, because the parent's fitted numbers can compensate for its old
approximation.

Keep discovery, rotating confirmation and a final untouched bank distinct.
Repeated per-round 95% intervals are not family-wise error control. Choose one
global finalist after the bounded campaign, then evaluate it against the frozen
incumbent on an unconsumed final bank. After a final result is inspected, that
bank is consumed. Do not tune on it and continue calling it final evidence.

Use map clusters for uncertainty: 200 games on one board do not provide 200
independent maps. With 10,000 maps and 200 games each, record all 2,000,000 game
identities and six million rival-instance identities, but describe their actual
behavioral families honestly. New seeds and weights are not six million new
algorithms. Withhold controller architectures as well as map seeds. Preserve
strong economic, racing, denial, baiting, erratic and specialized challengers;
otherwise a large random field can inflate average performance while hiding a
loss to another serious submission.

Report official pairwise mean, first-place rate, score, per-family results,
faults and decision time separately. A worst-field or CVaR constraint can be a
deliberate robustness requirement, but substituting it for the official mean
changes the objective. Fix the intended tradeoff before seeing final results.
If ratings are held fixed for a sampled lineup, ordinary pairwise Elo expected
terms do not depend on the chosen current action; pairwise outcomes are a useful
direct surrogate. Unknown tournament mixing and nontransitivity still prevent a
universal "best Elo" guarantee from one test distribution.

## Prioritized execution order

1. Complete the source-frozen four-arm arrival-clock/depth comparison. Independently
   audit legality, timing, public tracking and scores; reserve new maps for the
   selected arm's confirmation.
2. Add the reachable anticipatory-Shield regression, then test a narrow
   availability-aware guard against the original. Do not disable early-wait
   protection everywhere because of one adversarial case.
3. Make teacher terminal utility exactly pairwise and measure any nonterminal
   projection against held-out outcomes. Retain movement in joint terminal
   resolution unless a dominance proof covers the actual objective.
4. Fit a small public movement/target predictor, validate calibration, then test
   bounded tactical lookahead only on consequential or near-tied decisions.
5. Add specialist preservation and independent best-response challengers to the
   league. Compare CMA-ES or differential evolution on separate islands with an
   equal real-game budget and the same protected rule logic.
6. Distill a validated tactical teacher into a small standard-library model only
   after its information boundary and outcome objective pass review. Measure
   end-to-end GPU policy/search throughput; physics-only replay rates are not
   real-bot game rates.

All submitted behavior must remain one standard-library file with `act(state)`,
four documented public inputs and the real deadline. GPU libraries belong to
offline experimentation. Preserve the known-good fallback and independently
review each release. No finite campaign or mathematical surrogate can establish
zero errors or optimality against every possible opponent.
