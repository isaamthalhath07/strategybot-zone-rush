# Independent review: public-history opponent intent

Scope: a proposed bounded research model fitted or updated from focal public
history. This document does not execute a study, change a frozen source, accept
primary games, certify a true opponent type or qualify a policy for deployment.
The implementation belongs in this new folder; existing belief and GPU search
files must retain their registered versions.

## Recommended next step

Build the proposed exact one-step joint filter before running a larger search
benchmark. Retain four persistent **behavioral hypotheses** per rival, such as
farmer, raider, feinter and wanderer, together with correlated hidden physical
states. These are hypothetical policies, not recovered controller identities.
The existing GPU integer mixture is a useful reproducible baseline, but more
simulations against that unfitted mixture do not establish better anticipation
of real opponents.

Each hypothetical policy gets only its own four-field pre-turn view and retained
public position-history features. It must respond again to a changed board after
a deviation. It receives neither the focal player's chosen current action nor
another player's advertised legal list. Focal public legal actions can inform
the focal observer's belief, but must not be copied into rival policy features.
Any intended-action likelihood uses the policy's own legal list from the
hypothetical state; that is information its real counterpart would be given.

A practical first reference has a fixed, declared positive exploratory mixture
on all legal intended actions. A uniform prior over the four hypotheses is
acceptable as a declared prior. Neither an unweighted possibility set nor that
prior is an empirically calibrated posterior. After observing a prefix, the
result is a posterior **conditional on these four assumed policies**. Whether it
predicts the actual population requires a separate test.

## Preserve action aliases and joint uncertainty

`PublicBelief.advance()` is a possibility filter. Its stationary-action shortcut
is valid for retaining possible canonical physical states: blocked/lost-contest
moves have STAY's physical effect. That shortcut cannot be reused unchanged for
probability calculations.

Let `h` be the focal history before this turn, `s` a compatible physical state,
`theta=(theta1,theta2,theta3)` the three hypothetical persistent policy types, and
`a0` a proposed own action. The predictive probability of the next focal public
view `o'` is

```
P(o' | h, do(a0)) =
  sum_(s,theta) w(s,theta | h)
    * sum_(a1,a2,a3)
        product_j pi_theta_j(aj | own_public_view_j(s), public_history_j)
        * 1[ public_focal(T(s, a0,a1,a2,a3)) == o' ].
```

The own action changes transition physics, never the rival action distribution
at that same simultaneous turn. Conditioning a likelihood on `a0` is therefore
different from allowing a rival to see `a0` before choosing.

A visible successful displacement fixes that rival's intended cardinal move.
A stationary result can arise from STAY, SHIELD, movement into an occupied
starting cell, or a lost contest. Enumerate **all legal intended actions** for a
stationary rival, resolve the full joint action, and add every compatible
probability contribution. Frozen players have forced STAY. Geometrically illegal
requests need not enter a model of the guarded legal-action actors.

Do not label a stationary result STAY, or give its probability only the model's
STAY mass. Do not divide by the number of explanations. If several histories or
intents merge into the same retained sufficient state, add their weighted mass.
If they have different persistent type or policy-memory states, they cannot be
merged merely because their physical boards match.

This distinction matters directly to Shield decisions. `P(no displacement)` is
not `P(effective STAY)`: a rival that Shielded is stationary but is not a
STAY-only Shield victim. The useful tactical quantity is joint probability of
being on the relevant land **and** effective STAY after move resolution. A
visible-motion predictor alone cannot supply that quantity.

One hand-checkable alias test can condition the other hypothetical rivals on
fixed choices in the existing reachable catch/backfire example. Give the
stationary subject probabilities STAY .2, blocked WEST .3, SHIELD .1, successful
EAST .3 and successful SOUTH .1. If the relevant next public view matches STAY,
blocked WEST and SHIELD, its conditional mass is .6. The two distinct physical
successors carry .5 mass with unchanged cooldown and .1 with cooldown four; the
conditioned cooldown-four probability is `1/6`. Forgetting the blocked move
would incorrectly report `1/3`. This is an auditor-side conditional algebra
test, not permission to pass actual rival actions into inference.

## Exact kernel reuse without repeated physics

For each physical state `s`, keep one length-64 weight vector over the `4^3`
joint types. Its components preserve correlations between types and hidden
cooldowns/progress/token; do not replace it with three independent marginal
type posteriors.

For a fixed `s`, own action and current public history:

1. Construct all four immutable pre-turn public views.
2. Calculate the `3 x 4 x 6` rival action probabilities once.
3. Enumerate at most `6^3=216` joint rival intents once, not 216 for every type.
4. Clone and resolve physics once per joint intent. Reject outcomes incompatible
   with the observed focal post-view. Group identical physical successors.
5. For each compatible joint intent, form its length-64 product probability
   vector and add `prior_weight_vector * action_probability_vector` to the
   successor. Normalize only after summing all predecessor/intent contributions.

This is an exact computational rearrangement under the declared model. Cached
physics keys need the full physical state, proposed own action, static map/home
identity and rules/version. Cached policy probabilities additionally need the
public history summary used by the policies. Two equal physical boards can
follow different visible headings or feints; a board-only global policy cache
would be wrong.

Do not discard the public trace until its sufficient statistics have been
extracted. The current GPU `PreparedRoot` retains a history hash, not the raw
trace. A hash cannot reconstruct stationary runs, recent directions, repeated
approaches, or same-owner escape behavior. A future search protocol must carry
declared public-derived statistics or reconstruct them before discarding history.

## Numerical and truncation limits

Use stable log likelihood accumulation and normalization, or an explicitly
reviewed equivalent. Positive per-action exploration does not prevent an entire
79-turn joint-type trajectory from underflowing in ordinary products. Do not
silently turn very small finite model mass into impossibility.

Define the budget precisely: `physical_states` and `joint_hypotheses` differ by
up to a factor of 64. If capping, rank physical states by their total joint mass,
preserve their complete joint-type vectors, and report the local normalized
posterior mass removed at each pruning. Report whether the filter is exact.

Local dropped mass is **not** a bound on missing posterior mass after later
observations. In particular, `1-product(1-drop_t)` is not a generally valid final
posterior-loss bound: a rare dropped branch can later become the only plausible
explanation. If a later view has no retained explanation, report unsupported
history; do not invent a repair or silently restart from a private snapshot.
An observation rejected after truncation cannot be treated as a clean model
likelihood failure without recording the approximation that caused it.

Updating should be transactional. Compute likelihoods with pre-turn features,
then append the new public observation only after the update succeeds. On an
unsupported observation, preserve the prior state, history statistics and
normalizer. Updating stationary-run or heading features with the target view
before calculating its probability would leak the answer.

For example, a branch pruned at posterior mass .001 can later have likelihood
one for an observation whose retained-branch likelihood is `1e-9`. Its correct
new posterior mass is approximately .999999. Reporting .001 as the final
missing mass would be wrong despite a seemingly tiny initial drop.

## Features and model mismatch

Useful public-derived features include recent successful headings, stationary
run buckets, local ownership/work opportunities, available empty exits,
same-owner escape exits, unfrozen intruders on a subject's land, nearby public
pressure and turns elapsed. A possible-cooldown domain may be useful to the
focal observer, but it is not a probability distribution. A readiness claim based
on an inferred domain must carry the exact-support/truncation qualification.

The actual registered opponents include persistent feint/raid/upgrade tendencies
and strong planners, while the fixed integer mixture has mostly local choices
and a fixed exploration rate. That code is observer-side knowledge of the test
population only; actual family names, specs, seeds, commitments, rival counters
and source IDs must never be model inputs or labels at inference time.

Four fixed hypotheses are an economical first model, but may all be wrong.
Their posterior can become confident while missing a real long-term plan. A
later goal/commitment model could track public candidate targets and switching
hazards, but should first earn better predictive scores on new maps. Tempered
likelihoods, type switching or a different exploration rate are separate model
changes, not numerical fixes that preserve an exact original posterior.

## Valid predictive evaluation

Use prequential next-public-view likelihood. At each registered prefix, compute
policy probabilities from the prefix first. The observer may then provide the
own accepted action as the transition condition and the next public view as the
scoring target. Actual rival actions are used only by the observer to generate
that target, never by the predictor. Once the target has been scored, it may
become legitimate past information for the next prediction.

The primary predictive score is negative log likelihood of that full public
target. A model assigning zero mass to a valid uncapped history fails that case;
do not drop it from the average or hide it with post-hoc clipping. If a declared
exploration floor is part of the model, score its actual probabilities.
Pre-register treatment of unsupported capped roots and report their count.

Also report Brier scores for observable marginal events: successful displacement
class, newly frozen status, and relevant ownership change. Those scores assess
the stated marginal forecasts, not a full joint likelihood or an identified
SHIELD action. Include reliability bins, sample counts and map-clustered
uncertainty for stationary/movement and tactical freeze events. Accuracy alone
can reward a stationary-majority predictor and miss the decisions that matter.

Compare on identical prefixes to a declared baseline: at minimum a fixed uniform
joint-type mixture with the same exact physical filter. A useful ablation
disables history-conditioned type updating while keeping physics and legal
masking fixed. That separates intent learning from simply improving rule
simulation or excluding impossible movement.

Report paired score differences by map rotation orbit. Resample complete maps,
retaining all games, seats, rivals and times from each selected map. Do not treat
80 correlated turns or three interacting rivals as independent samples. Report
publicly defined tactical strata separately: active rivals with multiple empty
exits, an intruder on another owner's land, a publicly ready focal Shield, and
forced/frozen cases. Strata must be chosen using the pre-view, not whether a
later Shield succeeded.

## TRAIN-only partition and a bounded first panel

Official development/final maps remain reserved. Use only completely accepted
TRAIN generations, with splits and model settings sealed before target scoring.
A temporal plan can use early completed generations for design, the next for
model selection, and later completed generations for a locked research test.
Within each split, group by map content/rotation orbit, never random turn rows.
The campaign's distinct maps make a generation boundary a useful temporal and
cross-map boundary; verify the actual catalog orbits anyway.

For a small implementation panel, pre-register at most 24 public prefixes from
distinct accepted TRAIN maps and fixed turns such as 12, 34 and 60. Select game
IDs by a fixed hash rule before reading outcomes. Restrict the first comparison
to the unchanged incumbent's games so a changing focal controller is not an
unreported source of observational shift. This is a mechanics/predictive pilot,
not enough evidence for a strength claim. A later broader panel needs whole-map
clusters and enough tactical cases for meaningful intervals.

A useful bounded sequence, once the root's new module exists, is:

1. Run exact hand-checkable tests for alias mass, joint correlations, positive
   normalization and same-public/different-hidden-world invariance.
2. Seal the 24-prefix TRAIN-only panel and the four policies/exploration/prior.
3. Score one-step full-public likelihoods for updating and fixed-mixture models;
   preserve input/source/output hashes and unsupported/cap statistics.
4. Inspect negative cases using only public prefixes. Keep any resulting model
   revision separate from the locked later TRAIN test.
5. Integrate a model into a **new** tree-search version only after predictive
   evidence supports it, then test choices in fresh full matches with proper
   actor/runtime audits and untouched policy-selection data.

There is no runnable study command certified by this document: the new module
and its tests are being implemented separately. Do not claim completed fitting,
heldout evaluation or improved play from this design review.

## Adversarial acceptance checks

- A stationary public outcome adds mass from blocked moves as well as STAY;
  Shield aliases retain their different cooldown consequences.
- Different compatible predecessor paths add their weighted probability mass
  rather than overwrite one another or get a uniform reset.
- Joint type/state correlations survive conditioning; products of posterior
  marginals are not substituted for the joint distribution.
- Rival probabilities are identical under different proposed focal current
  actions from the same pre-turn views. Physics outcomes may differ.
- Replacing actual rival labels, seeds and future tape leaves inference unchanged
  for the same public prefix. A predictor API cannot accept those fields.
- Public-history features are extracted before target conditioning and retained
  in any later GPU/worker protocol; a digest is not a substitute for them.
- An uncapped small example matches an exhaustive independent joint enumeration
  in both referees. A capped loss is explicit and never grants game credit.

Better predictive likelihood is useful evidence, but not sufficient to declare
a stronger bot: a changed rollout model can also alter search bias and runtime.
No search recommendation is a proof of optimal play against unknown rivals.
