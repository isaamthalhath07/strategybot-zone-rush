# Public-history observation-branching tree coach

This is a bounded offline research prototype. It leaves the deployed bot, the
current campaign, the public belief filter and the GPU worker unchanged. It
credits zero primary games and zero completed per-game BMCTS audits.

## Information and decision boundaries

The only input is an actual opening four-field public observation, the focal
player's own accepted past actions, subsequent focal public observations and
bounded diagnostic settings. No actual referee instance, controller identity,
opponent seed, private counter or future action tape is accepted.

The existing `PublicBelief` reconstructs a correlated set of compatible hidden
states. The prototype samples that set uniformly at each simulation's root.
Uniform support is not a calibrated posterior, and a support cap can discard the
real state. Both limitations remain explicit in every report.

One search node represents the entire focal public action/observation history.
Its key extends the parent history with the focal action and the resulting
four-field focal observation. It never includes the sampled hidden state,
opponent model family or private counter. Two particles arriving at the same
history share one action-value table. Different observable outcomes create
different continuation nodes, so the policy can react to observations rather
than committing to one open-loop action sequence.

The action selector takes only a node's public legal list and accumulated visit
and value statistics. Simulator state is confined to root sampling, transition
physics, public-view construction and return evaluation. Focal rollout decisions
also take only the focal public observation. They never optimize a separate
continuation from a sampled particle's private contents.

## Search and simultaneous play

Each simulation starts from a sampled compatible joint state and samples
hypothetical rival model families independently of that state. Rival choices use
only each rival's own pre-turn public view and explicit hypothetical randomness.
Those random streams derive from the root public history, diagnostic seed,
simulation number, seat and turn. Actual opponent seeds are absent. All four
choices use the same pre-turn views; rival choice receives no focal current
action argument.

The reference search uses history-tree UCT. It expands a new public-history node
and uses a public-only economic rollout policy to finish the bounded horizon.
Returns update all selected history/action edges on the path. This is root
sampling with an observation tree, inspired by the history-tree construction in
[Silver and Veness, *Monte-Carlo Planning in Large POMDPs*](https://papers.nips.cc/paper_files/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf).
The prototype does not inherit that paper's guarantees: its rival models,
uncalibrated support, heuristic cutoff and optional pruning change the problem.

Every legal root action is sampled before pruning. More generally, every legal
action at a reached tree node receives a minimum number of samples before that
node may retain only its best `beam_width` actions for that decision. This is
dynamic top-K pruning: all actions are ranked again on each visit, and a
previously excluded action can re-enter if retained actions' averages fall.
Width six disables action pruning. The report records visits, observed branches,
actions ever excluded, pruning events and node-cap events. Pruning can discard
the correct action after noisy early samples; a finite run is not an optimality
certificate.

The final root recommendation is the action with the highest empirical mean,
with canonical action ordering for ties. It considers all root arms, including
those with only the minimum sample count. A lucky sparsely sampled action can
therefore beat a much better measured alternative. No confidence interval,
equilibrium certificate or reliable-best-action guarantee follows from this
selection rule.

## Objective and accounting

At a real terminal state, the return is the official pairwise score: one point
per rival beaten, half per rival tied and zero per rival that beats the focal
player. Internally this is the exact integer numerator 0..6. There is no
score-minus-mean substitute. At a nonterminal cutoff, the same rank formula is
applied to scores plus a bounded income tail. That is an explicit heuristic,
because future captures, freezes and raids can change income and ranks.

The horizon is clipped to the actual remaining turns. Simulations, synthetic
turns, terminal evaluations and heuristic cutoffs are counted separately. No
simulation is a newly executed primary game, and sampling a position does not
complete a game's requested BMCTS audit. The prototype neither trains nor
promotes a policy and makes no 200 ms deployment or GPU speed claim.

## Pros, costs and required evidence

The advantage over the existing open-loop diagnostic is observation-dependent
continuation with shared information-set statistics. Root sampling preserves
joint hidden-state correlations without choosing a private-state-specific focal
policy. Public-only rival policies respond to deviations instead of replaying an
opponent's recorded future tape.

The cost is a large chance tree: many distinct public boards yield few revisits,
so most computation can remain rollout evaluation. Short horizons, an economic
rollout policy, simplistic rival models, support truncation, optional action
pruning and the node cap can all produce poor recommendations. This is a
single-agent model of simulated rivals, not a multiplayer equilibrium solver.
Model mismatch and overfitting must be measured in fresh complete-game controls
before any deployment decision.

Focused tests must establish deterministic public-only input behavior, hidden
indistinguishability, shared-node selection, actual observation branching,
simultaneous public rival decisions, legal recommendations, exact terminal
ranking, immutable inputs and explicit approximation/accounting limits. Those
checks establish bounded implementation behavior, not playing strength.
