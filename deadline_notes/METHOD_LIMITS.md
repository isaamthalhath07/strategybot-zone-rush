# Prospective limits of the deadline evolution method

This review uses the frozen protocol/source design only: the
[campaign plan](../deadline_campaign/PLAN.md),
[population/schedule recipe](../deadline_campaign/design.py),
[evaluation rule](../deadline_campaign/evaluation.py),
[time budget](../deadline_campaign/budget.py) and
[complete TRAIN reporter](../deadline_campaign/train_report.py).
It reads no partial TRAIN result, incomplete architecture result, DEV/FINAL
outcome, key or live execution artifact. It creates no runtime or test and
proposes no alteration to the live frozen protocol. Its purpose is to bound
the eventual conclusions before results are available.

**I find no fundamental mathematical invalidity in the bounded search and
fresh validation design as declared.** It estimates strength against a finite
specified mixture and explores a restricted policy family under a wall-time
constraint. It cannot establish global optimality, complete adaptation to
unknown algorithms, or absence of all strategic errors. Source/physics
correctness and statistical strength are separate claims.

## What the complete crossing buys

For a fixed policy a, map m and cell c=(field, focal seat, initial token), write

`Y[a,m] = (1/64) Σ_c U(a,m,c,ξ[a,m,c])`, where `U∈{0,.5,1,1.5,2,2.5,3}`.

The generation estimate is `mean_m Y[a,m]` over16 maps. Its eight policies play
`16×8×64=8,192` full matches, with1,024 matches per policy. This exact crossing
removes unequal weighting of the four fields, four focal seats and four tokens.
It also exposes map-by-field/seat/token interactions rather than trusting an
accidentally favorable starting configuration. The64 cells are deliberately
fixed conditions, not64 independent map draws.

TRAIN arms receive independently generated rival parameters and fresh instance
seeds/identities. Consequently A−B is a **map-matched comparison**, not an effect
against the exact same realized lineup. The field's rival-family multiset is
fixed, but its allocation/parameters can vary across arms. This adds finite
lineup noise; it is not systematic favoritism when the recipe is fixed before
outcomes. Deterministic planners have no action RNG to reseed; their fresh
parameter draws, rather than an unused seed label, create changed instances.
Distinct seeds or source hashes do not create new opponent algorithms.

The16 maps are **fresh and disjoint for each generation**:500+16g through515+16g.
This is not repeated fitting to the same16 boards. Nevertheless the population
adapts to a repeatedly used algorithm/field distribution. Fresh maps address
board reuse, not every form of overfitting.

## Sixteen versus one hundred maps is a real tradeoff

Under an illustrative independent-map model,

`Var(mean_m Y) = Var_m(E[Y|m])/M + E_m(Var[Y|m])/M`.

More independent rival instances within a map can reduce the second term.
They do not remove map-specific differences in whether a strategy works.
Whole-map uncertainty is therefore appropriate; treating1,024 games as1,024
independent maps would overstate precision. The actual fixed catalog and finite
map count do not establish that illustrative model's assumptions, so it is
not a substitute confidence interval.

| Design | Maps | Games per policy per map | Games per8-policy generation |
|---|---:|---:|---:|
| Frozen new complete crossing |16|64|8,192|
| Same crossing on100 maps, hypothetical |100|64|51,200|
| Old primary100-map stage |100|25 on average|20,000|

The hypothetical100-map full crossing costs6.25 times the new generation at
equal per-match cost. The new generation costs0.4096 of an old20,000-game stage,
not0.16: it spends more conditions on each board. The old stage's64 aggregate
fitness cells had39/40 observations across its100 maps; it did not run all64
cells for every policy on each map. These are distinct experimental designs.

If map-level variance stayed equal, changing100 maps to16 would multiply
standard error by`sqrt(100/16)=2.5`. Complete per-map crossing can change that
variance, so2.5 is an illustration, not an empirical error bar or proven loss
of efficiency. Sixteen clusters can give unstable bootstrap tails and weak
evidence for small gains. The benefit is more chances to propose, reject and
refine policies before the ten-hour deadline. Neither design dominates without
knowing improvement sizes, map variability and full pipeline cost in advance.

The time rule uses complete original-plus-independent-audit measurements and
a20% allowance, with separate heldout/packaging reserves. That is a defensible
resource policy. It does not make future runtimes certain: genes, trajectories,
contention and new goal updates can change cost. A whole generation that misses
the eligibility cutoff remains preserved but cannot become a favorable partial
shortlist. Eligibility follows the frozen clock/source/admission rules, not
whether its partial scores look promising.

## What the small evolutionary portfolio explores

Generation0 preserves e8,50d,original Blocker,original Feint,f5 and the exact
learned stage4 offspring_07, plus two numeric children. This avoids discarding
the old numerical work:50d is the old stage4 standardized winner, and the
additional learned source is the best distinct retained genotype excluding
e8/50d. That old sample ordering does not prove a new superiority relation.

Generation1 is a prospectively fixed structural comparison with an exact f5
control and fixed goal extension, plus the declared references/elite/children.
It changes a target-memory/likelihood package, not persistence in isolation.
Its layout was fixed before TRAIN outcomes; it must not be redescribed as an
outcome-driven discovery or retrospectively expanded after seeing a loss.

Generation2 onward uses three fixed originals, two nonreference elites and
one sparse numerical child per strategy family. The fixed references are useful
within-generation anchors and keep all three original families available.
Family allocation prevents one noisy early leader from immediately monopolizing
all offspring. It also spends resources on a family that may be inferior under
the chosen mixture and permits only one new child per family per generation.
This is a deliberate small portfolio search, not a general optimizer.

The e8 operator changes1..4 of23 numeric genes at scale0.08 of their ranges;
Blocker/Feint operators change1..3 of12/10 loci at scale0.06. No crossover is used
by this frozen child recipe. A few local mutations can exploit a good warm
start, but can miss improvements requiring coordinated changes, a different
step size, a deeper valley or missing code. Parameters interact; some affect
actions only near thresholds. A new genotype need not be a new action policy,
and changed actions need not change the final rank. Near-saturated rank utility
makes those plateaus particularly relevant. Numeric search cannot invent a new
opponent model, repair an unmodified valuation formula or supply an equilibrium
solver. The explicit f5/goal structure is therefore a substantive comparison,
not merely a larger volume of the same numerical search.

Only current-population SHA/genotype deduplication and bounded attempts are
promised. A source may coincide with an older dropped source; more evaluations
do not necessarily mean more distinct behaviors. The original, f5 and goal
Blockers share a strategy-family slot but remain different structural templates.
After generation1, only the best current Blocker template supplies that family's
child. A noisy choice can lose a useful structural branch, while the original
Blocker reference remains available. This constrains opportunity, not validity.

## Selection noise, forgetting and regret

Let `estimated_J[a]=J[a]+error[a]` for the eight candidates fixed before a
generation. Selecting the largest estimate tends to select a positive error:
the winner's curse. Keeping two elites and one best parent per family does not
eliminate it. The next fresh generation retests survivors and can reverse the
order; raw means from different generations must not be pooled or ranked as if
they had faced the same maps and rival realizations.

For perspective, if every candidate's error were bounded by ε, the selected
winner's true loss relative to the **best evaluated candidate** would be at
most2ε. That is an elementary conditional bound, not an established ε for this
campaign. It says nothing about the best policy never proposed. The actual
simple regret `sup_(π in all legal policies) J(π)−J(selected)` is unidentified.
Hindsight maxima of noisy observed scores are not an estimate of that quantity.

The last complete population is the only DEV shortlist. This limits selection
scope and removes the temptation to scan hundreds of historical policies on
DEV, but can forget a superior older nonreference after a noisy TRAIN loss.
Three fixed originals are not a complete historical hall of fame. The retained
final anchor supplies a qualified fallback; it does not restore every lost
candidate to the shortlist. A missed improvement can therefore occur even if
every match and statistical calculation is correct. This is an acknowledged
search limitation, not a reason to insert an older favorable source after
partial results or change the frozen shortlist retrospectively.

## Generalization is about algorithms as well as boards

The measured objective is an equal-cell expected utility `J_D(π)` under the
declared map/opponent distribution D. It is not automatically the tournament
objective `J_T(π)` under an unknown T. For a purely illustrative total-variation
bound, if`TV(D,T)<=δ` for the complete exogenous environment distribution, then
`|J_D(π)−J_T(π)|<=3δ`, because utility lies in[0,3]. An arm contrast can change
by as much as`6δ`. The campaign establishes no such δ. Thus more accurately
measuring a small gain under D need not protect its sign under unknown rivals.

The four fields include useful economic, erratic and adversarial pressures,
but remain finite algorithm families and parameter distributions. A policy may
learn the exploitable habits of their shield, route or commitment logic without
using any forbidden identifier. Exact source templates prevent arbitrary map/
identity lookup code; they do not prevent ordinary statistical specialization.
Withholding maps is not the same as withholding opponent architectures.

For any four final scores, the sum of the four official pairwise utilities is6.
That constant-sum fact does not turn this four-player search into a two-player
minimax theorem. The method optimizes against separately responding sampled
rivals. It does not compute a Nash equilibrium, a calibrated best response to
every algorithm, or robustness against an omniscient coordinated coalition.
Such a coalition would itself be a different information/incentive model.

There are concrete strategy-specific risks: Blocker's leader denial can help
other rivals while sacrificing our closer rank boundary; Feint can waste route
value against a nonreactive opponent; e8's numerical weights cannot remove all
its structural approximations; f5 removes contradicted Shield explanations but
does not identify genuinely ambiguous cooldowns; the goal vector can retain a
decoy or react slowly to a changed target. The tested portfolio measures those
tradeoffs on D. It cannot honestly promise every mechanism is beneficial.

## DEV, FINAL and honest conclusions

DEV's matched parameters/RNG seeds create a useful shared-condition comparison;
rivals still respond to each candidate's changed board. They do not share live
memory or a fixed future-action tape. Common random numbers can reduce variance
depending on covariance; matching is not a mathematical guarantee that every
contrast becomes less noisy. DEV selection among eight TRAIN survivors remains
exploratory. A single challenger must then be frozen before the untouched final
cohort, against the prospectively specified complete-study anchor.

The final rule requires positive overall95% lower limit and all four one-sided
Bonferroni field lower limits above−0.05. Requiring all components is a
conservative intersection-union decision, not inherently a five-way inflation
of false promotion. Its finite-map percentile limits remain approximate, and
the field margin intentionally permits a small field decline. If it fails,
the anchor remains. An inconclusive result is not equivalence, proof the new
method learned nothing, or permission to weaken the rule. If a required anchor
or phase cannot be admitted, follow the frozen failure/fallback path rather
than reading a partial study to choose one.

Fresh FINAL can evaluate the one selected concrete challenger despite adaptive
TRAIN/DEV selection. It cannot recover candidates the search never found,
certify the entire policy family, or justify another final draw after a loss.
Report all28 SHA-lexical TRAIN contrasts, field results, source/parent lineage,
actual admitted sample sizes, uncertainty and runtime faults. Fields and
mechanism subsets not in the fixed inference family remain descriptive.
Do not select attractive subsets, tune the fixed goal constants, reuse FINAL,
or rank across generations by raw means.

The defensible endpoint is a legally acting standalone policy selected by a
finite, reproducible, source-frozen protocol with a qualified fallback and
explicit uncertainty. Large callback counts and two referees provide strong
execution evidence for the played histories. They do not prove zero strategic
errors, universal rule correctness in all unvisited states, or the strongest
possible bot. No current outcome is needed to recognize either the method's
usefulness or these limits.
