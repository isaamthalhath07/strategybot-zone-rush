# Prospective persistent public goal scores

`goal_space.PersistentGoalTemplateSpace()` produces a separate exact structural
family on the fixed f5 public-memory Blocker. Its default standalone SHA256 is
`441596f94a1c2793e8f9c4b02c380160b4fa9985cc0cf50457bbbdfdbc73d514`.
The family identifier is `persistent-goal-public-memory-blocker`, strategy
family `blocker`. It has the same twelve bounded numeric loci, defaults and
operator interface as `PublicMemoryTemplateSpace`. No source is written by the
API. The exported policy uses only the original standard-library imports.

This candidate is **excluded from generation0's eight-policy panel**. It requires
independent correctness review, runtime qualification and an explicit versioned
TRAIN declaration. The deadline coordinator prospectively places its fixed
default in generation1, alongside an exact fixed f5 control, before any TRAIN
outcome; that declaration must be sealed in the initial protocol. The builder's
`requires_explicit_future_train_amendment` flag means this external declaration
is required; the builder alone cannot authorize inclusion. It does not learn
from DEV or FINAL, qualify itself, accept outcomes, grant credit or select a submission.
Neither its strategy benefit nor its 200 ms deadline has been measured.

## Fixed update

For each rival r, keep one persistent immutable 64-entry normalized score vector
`p[r]`. The current public board defines attractiveness `q(g)` using the prior
forecast's valuation: neutral `base`, own unupgraded `0.6·base`, rival upgraded
`0.6·base`, rival unupgraded nonhome `2.5·base`, divided by current Manhattan
distance plus1. Another current occupant multiplies attractiveness by0.3. Own
upgraded cells and other players' homes have zero attractiveness. Normalize q.

Condition the previous vector on q's positive support, then normalize it. If
no previous mass survives, use q. For each valid goal, update

`p_new(g) ∝ L(g)·[0.8·p_valid(g)+0.2·q(g)]`.

For an observed displacement of a rival that was and is unfrozen,

`L(g)=4**(d(previous_position,g)−d(current_position,g))`.

This is the base-4 form of `exp(log(4)·distance_improvement)`. Otherwise `L=1`.
Stationarity, a blocked attempted move and a frozen turn do not supply evidence
of intentional STAY. Only public displacements are used; intended actions,
controller identity, private cooldowns, rival seeds and future paths are absent.
If the entire board has no attractive valid goal, the public current position
is a normalized stay sentinel. This explicitly defined terminal spatial fallback
avoids a zero normalizer; it does not invent an unobserved target.

The update runs at the end of **every** `_observe`, after f5 has reconstructed
public state and appended history. This placement matters because a frozen
focal policy returns early from `_decide`. `_forecast` reads the stored vector
and derives the existing most-likely goal and decreasing-distance next-step
scores; repeated calls cannot update it again. Its `post[r]` aliases the same
immutable tuple. Existing conflict, route, parking, sniping and job scoring
consume those scores. All remaining f5 policy bytes, rule handling, numeric
defaults, direct entry and public-seat RNG initialization are preserved.

These vectors are heuristic normalized goal scores, not an identified Bayesian
posterior or persistent controller-state reconstruction. A fixed hazard may
overcommit to a feint or react too slowly after a plan changes. The public board
also changes when other players capture or occupy targets. A forecast loss
improvement would not by itself establish better full-match rank decisions.

## Exact source and checks

The builder pins the unchanged f5 adapter and its source closure. It inserts
one observation-boundary update and replaces the exact `_Core._forecast`
method with the fixed update/readout methods. Default bytes are SHA-pinned.
Numeric inspection regenerates the entire standalone source and rejects any
other changed byte, including hazard, moved-factor, entry or RNG changes. No
new strategy/cost/rule gene is available. Original and f5 templates remain
separate; cross-template source crossover is forbidden.

Five author synthetic tests cover the independent update equation, default
source hash and canonical numeric exports, source drift, observation updates
while the focal is frozen, blocked-move/STAY indistinguishability, read-only
forecast calls, invalid-target conditioning/restart, f5 own memory against two
referees and hidden-distinct worlds with identical public histories. Scripted
accepted actions isolate memory; no planner-strength games are run.

Run `python -m unittest deadline_strategy.test_goal_space -v`. Later qualification
must verify exact fresh namespaces, full legal/public callback sequences,
unchanged public inputs, no fallback, all real deadlines, independent actor
regeneration and two referees under the new source hash. Actual timing must
include its additional per-observation update, including forced-STAY turns.
There is no speed claim from the bounded three-by-64 vectors alone.

The original `_Core.act` retains an internal illegal-proposal-to-STAY guard,
but its zero execution count is not measured by the current return receipts.
For these exact templates there is a source legality argument: `_decide`
normally returns `legal[0]`, SHIELD only after `_defend` checks membership,
STAY, `_work`, or `_move`. STAY is always in the strict legal mask. `_work`
returns STAY or `_hop`, whose candidates are membership-filtered; `_move`
returns STAY or a membership-filtered option. Feint's move override delegates
to that same method. The goal extension changes none of these return paths.
Thus the guard is unreachable on normal return under the input contract.
The standalone entry calls `player.act` directly, so exceptions propagate;
it bypasses the exception-swallowing `__call__`. This is a source argument,
not a claim of a measured internal-guard count or a proof of all strategic
correctness. Real qualification must still check accepted legality and timing.

The appropriate first strength comparison is fixed f5 versus fixed f5 plus
this goal update on new, unconsumed TRAIN maps and responding rivals, with the
same prospective map/field/seat/token crossing. Keep the numeric defaults fixed
for this structural comparison. Register failure behavior, all contrasts and
whole-map uncertainty before outcomes. Reject or defer it for a correctness or
deadline failure, worse public prediction, or insufficient fresh rank evidence
relative to its added complexity. Do not retune the hazard or likelihood factor
on the same comparison or treat an inconclusive interval as equivalence.

All work here has zero primary-game, complete per-game BMCTS, strength-game and
promotion credit. No original template, live runtime or initial-panel source was
edited. A coordinator that pins every module in this package must finish and
pin this unused file before freezing its manifest, or explicitly separate its
future-amendment closure.
