# Availability-guard adversarial review

Verdict: the change addresses a real conditional failure, but it is not a
dominance improvement. It remains an experimental candidate. A ready landlord
can remove our future defense; readiness alone does not establish that the
landlord will do so, or that the intruder will stay. A feint can reverse the gain
from exactly the same public information state.

Reviewed files are frozen at:

| Source | SHA-256 |
|---|---|
| Production parent | `e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5` |
| Availability only | `9b70ead68aeffe9a7e5b6e4cedcb0713f0985c8d9b38c0eb0e15fd1c335e4637` |
| Arrival plus availability | `26736ce075cb6199ddf0e8dce5e603152d6c29163ea41ec6c294533f14506d32` |

No production bot, candidate source, primary-campaign source or existing runtime
guard file was changed during this review. Added files are this review and
`test_counterplay.py` only.

## What the trigger establishes

The helper reads current public ownership, public freeze flags, legal moves,
occupied cells and public-history cooldown support. It requires the landlord's
support to equal `{0}`, not merely contain zero. This preserves the information
boundary and avoids interpreting an uncertain cooldown as certain readiness.
It changes no physical rule or inference logic. It only allows the existing
Shield valuation to consider an early-stage intruder instead of skipping it.

The condition does not prove a Shield is profitable. It establishes an available
adversarial action and no currently unoccupied legal exit. It does not model
whether the landlord wants to Shield, the intruder's next action, the probability
of a backfire, or the future value of retaining our own cooldown.

Under the canonical move list, an interior cell has four adjacent cells but
there are only three rivals. Therefore all exits cannot be occupied in the
interior. The new trigger is naturally limited to edges and corners, unless the
server uses a more restrictive legal-action convention. Conversely, one currently
unoccupied exit is not necessarily a guaranteed future escape: another player
may contest it. The narrow guard does not solve those wider situations.

## Positive case and matching counterplay

Both profiles begin with the same complete legal sixteen-turn opening prefix
from `anticipatory_shield_counterexample()` in `evolution/mathematical_probes.py`.
At turn 17:

- A stands on B's home at cell 7.
- B at cell 6 and D at cell 15 close A's exits.
- C is on A's upgraded 3-point cell 18, with one completed stay.
- A knows through its public history that B's cooldown is zero.

The prefix is a constructed reachable history, not evidence that either bot
naturally reaches this state in ordinary play. The observer is told its actual
accepted own past actions. From turn 17 onward, each tested bot makes every own
decision normally from public inputs; the opposing action profiles are fixed in
advance, independently of the focal bot's realized action.

**Committed profile:** B shields on turn 17; C stays, then all three rivals stay
through turn 80. The parent's STAY is caught, so it cannot defend C's takeover.
The candidate shields early, catches C, and makes B's Shield backfire. It can
then keep defending the upgraded cell.

**Feint profile:** B stays throughout. C moves EAST on turn 17, WEST on turn 18,
then stays through turn 80. The candidate's turn-17 Shield catches nobody and
backfires. It cannot Shield on turns 18–21; its earliest next cast is turn 22.
C's three stays on turns 19–21 complete the raid before that recharge. The
parent waits and shields on turn 21, preventing the raid.

| Rival profile | Focal policy | Final scores A/B/C/D | A's pairwise wins |
|---|---|---|---:|
| Committed | Parent | 309 / 705 / 873 / 819 | 0 |
| Committed | Availability | 687 / 705 / 456 / 819 | 1 |
| Feint | Parent | 687 / 705 / 456 / 819 | 1 |
| Feint | Availability | 327 / 705 / 855 / 819 | 0 |

The arrival-plus-availability candidate gives the same results in these cases.
All states, timers, ownership and final scores agree in the independent engine
and the pinned vendor referee. No hidden state or opposing future action enters
the focal policy. The tests audit private counters afterwards to verify tracking.

These examples disprove dominance in both directions. In an illustrative mixture
containing only these two profiles, the candidate's expected pairwise advantage
is `p*(+1) + (1-p)*(-1) = 2p-1`. It would need the committed profile's probability
to exceed one half. This is a two-profile calculation, not a field estimate or a
universal Shield threshold. Other joint reactions have different payoffs.

## Counterplay and modelling implications

A landlord standing ready is different from a landlord likely to cast. A pacifist
can remain certainly ready for an entire game. B's home also cannot be taken, so
A's presence there is not itself an immediate capture threat. Shielding can
still have tempo or ranking value, but that must be modelled rather than assumed.

The intruder can exploit a deterministic early defense by moving away and
returning during the four-turn cooldown. A policy that knows the public trigger
does not need to observe A's realized simultaneous action to choose that feint.
The candidate's existing stay estimate discounts early intruders, but the narrow
trigger still produces this predictable branch in the constructed state.

The current home-cell exclusion in the threat loop remains reasonable for this
experiment: rivals cannot capture our home. The rule permits freezing a staying
rival there, but that does not make the freeze automatically valuable. Do not
remove that exclusion as a supposed rules correction.

A short planning horizon can also favor the candidate unfairly. The positive
branch loses the cell within two turns. The negative branch first looks harmless
and loses it on the fifth decision, turn 21. A depth-three search with a static
income tail may observe the benefit and miss the cost. Tactical tests need at
least the full five-decision backfire/return window, or a separately validated
continuation value that captures this timing.

## Next falsifiable step

Estimate the joint distribution of the landlord's Shield and the intruder's
stay/leave/return behavior from public history. Useful features include the
landlord's current productive work and defended land, prior visible defense
choices, the intruder's persistence and repeated targets, current scores inferred
from public history, and feasible exits/contests. Do not insert actual controller
labels, private counters or RNG seeds as features.

Retain physical hidden-state possibilities jointly where needed, but do not
confuse that support with an intention posterior. A support set answers whether
the rival can Shield; an action model estimates whether it will. Their weights
must not come from the hidden controller that generated a test game.

Then compare ordinary play and Shield over a bounded five-or-more-turn tactical
window, using independently responding rivals from the same pre-action board.
Include committed raids, pacifists, move-away/return feints, mutual Shields,
blocked escapes, ambiguous readiness and future contests. Keep official pairwise
utility at the terminal state. Randomization near tactical indifference is a
separate candidate requiring its own seeded comparisons, not a blanket fix.

Before any release, run fresh field comparisons, withheld-family confirmation
and the independent validity audit. Report how often this narrow trigger occurs
in real candidate games; a rare or unreachable-on-policy repair can pass these
fixtures while contributing no field strength. Neither a positive fixture nor a
negative one estimates the relevant joint probabilities.

## Validation

`python -m unittest evolution.availability_candidates.test_availability evolution.availability_candidates.test_counterplay -v`

All six tests pass. They cover the original conservative trigger boundaries,
positive and negative profiles, complete terminal pairwise reversals, both
referees, public-input immutability, legal actions, exact public tracking and
unchanged frozen source hashes. These are regression and counterexample tests;
they count as neither primary campaign games nor new strength evidence.
