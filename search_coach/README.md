# Public-history search coach prototype

This is an **offline diagnostic** built around the existing champion. It does
not modify `bot.py`, replace its action, mutate its configuration or claim a
new champion. The incumbent remains the deployed default. This prototype is
open-loop beam Monte Carlo search, **not a full BMCTS implementation**.

## Information boundary

`PublicBelief` starts from the actual initial four-field observation and takes
only the focal player's own accepted past action and its next public view for
each transition. It never accepts an actual referee object, opponent controller,
controller seed, private counter, future action or a mid-game private snapshot.
Only the canonical STAY-only Shield rules and cooldown-filtered legal lists are
supported. On-time legal own actions are assumed accepted; the interface has no
acceptance acknowledgement that could resolve every silent server substitution.

The initial token holder is unknown when `is_priority_token` is false. The
filter therefore starts with all three compatible holders. It reconstructs
possible hidden cooldowns, work progress and freeze counters by enumerating
stationary rivals' STAY/available-SHIELD choices and keeping only transitions
whose complete public result matches. Successfully moved rivals have a unique
cardinal action. Under the canonical rules, a failed move has the same physical
effects as STAY, so its intended destination need not be guessed.

All compatible hidden states are retained up to the explicit support cap.
Duplicates are collapsed. If the cap discards states, `exact_support` becomes
false and dropped states are counted. The real state can then be lost. A later
unexplained observation raises `InconsistentObservation`; it does not silently
invent a hidden-state repair. The retained states are a possibility set with
uniform sampling, **not a calibrated Bayesian posterior**. Unknown action
likelihoods cannot be recovered by merely counting explanations.

## Bounded counterfactual search

Each root action has its own continuation beam so a shallow score cannot remove
the entire root before the final horizon. Every plan uses one common requested
action sequence across all sampled hidden states. If a requested action is
publicly illegal at execution, it becomes STAY. The planner does not optimize a
different focal continuation for each hidden particle: that would grant the
focal player knowledge it does not have, often called strategy fusion.

Each simulated rival chooses afresh from its own public counterfactual board,
using a mixture of simple economic, pressure, wandering and holding models.
All four choices use the same pre-turn board. Rivals cannot see the focal
player's hypothetical current action before choosing. The diagnostic never
replays a real opponent's recorded future moves after a deviation. Randomness
depends only on the public prefix, the explicit diagnostic seed and sample
index; actual opponent seeds and identities are absent.

The cutoff value combines simulated score-margin change with up to twelve
turns of income margin. The reported sample standard deviation describes this
small artificial model sample; it is not confidence in the true opponent's
response or proof of an optimal action. Handwritten rival models, finite
sampling, beam pruning and short horizons can all give the wrong recommendation.

## Validation

Run from the repository root:

```powershell
python -m unittest search_coach.test_coach -v
python -m search_coach.replay --games 8 --horizon 3 --beam-width 2 --rollouts 6
```

Eight tests cover initial token uncertainty, successful movement between cells
of the same opponent, blocked movement counting as STAY, capped-support failure,
input boundaries, mutual Shield backfires, determinism and input immutability. A full reachable history
also creates two actual games with different rival cooldowns but identical focal
observations and own actions: a rival is either caught by a landlord Shield or
backfires with its own Shield. Both explanations remain possible, and the
resulting diagnostic outputs are identical. The test observer's private-state
checks never become coach inputs.

`replay_audit.json` records eight archived champion games, all four seats and all
three opponent fields. The observer generates each public view, then asks the
coach before applying the recorded joint action. The baseline is separately
replayed through the same public views and must reproduce every recorded focal
action. Exact support is checked against the true state by the observer after
every transition, with all source and transcript hashes recorded. These are
replays and diagnostics, **zero new primary campaign games**.

The default audit runs 24 diagnostic positions (turns 12, 34 and 60 of each
game), with depth 3, beam width 2 per root and six rollouts per sequence. Runtime
is measured in the evidence. This Python prototype does not meet or claim a
200 ms deployment budget. A disagreement with the incumbent is a case to
investigate, not evidence that the coach is stronger.

## Next architecture step

Keep the existing legal-action, rule and inference code intact while evolving
its bounded configuration. Use this coach to collect difficult public cases
and test candidate explanations. Validate coach suggestions by complete games
against fresh opponent instances; do not tune against one transcript's hidden
future or promote a candidate because it fits a coach's short-horizon score.

A full information-set BMCTS would branch on possible future observations and
choose each continuation only from the public history available at that node.
It needs public-history keys, correlated belief updates, public-only opponent
likelihood models, uncertainty-aware rollout values and measured runtime. A
faithful batched policy/search port could then use the separately tested GPU
physics. Neither the tensor physics benchmark nor this prototype establishes
that end-to-end speed or strength yet.
