# Public e8 paired-root reference

`evaluator.recommend(raw)` is an offline CPU correctness reference for a possible
GPU implementation. It creates no actual match, training experiment, deployment
change or primary/BMCTS/promotion credit. Only synthetic tests have run.

The strict wire has the same six top-level fields and bounded search options as
`intent_search.mcts`, with `kind="public-e8-root-evaluation/1"`. Preparation passes
a copied, kind-normalized input to the frozen `mcts.prepare`, preserving its
complete joint physical-state ×64 persistent type posterior and conservative
inference/work limits. Actual controller/state/type/seed/future inputs are
rejected. `simulations` must divide the number of legal root actions and provide
at least two paired worlds per action. Thus96 trajectories and six actions mean
**16 paired worlds per action**, unlike the earlier96 adaptive world draws.

Every pair samples one complete joint explanation. Every root action receives
that same sample and the same pair/depth rival random keys. Rivals still react
to each resulting public board, so later actions and trajectories may differ.
Shared seed domains do not make trajectories identical across architectures.

Exact immutable e8 source runs in fresh globals per trajectory. Its data-only
`_history` is reconstructed from the opening public view, its past public views
and accepted own actions. Each historical proposal runs before accepted `last`
is synchronized. At the root, each fresh branch runs the original proposal once,
retains its target/bait updates, synchronizes the forced root action, then uses
e8 at every own future step. Function globals are never deep-copied. All actor
inputs are frozen four-field views with six-field frozen cells. Their public
legal set uses reference-engine order: STAY,NORTH,SOUTH,WEST,EAST,SHIELD. Public
wire/history hashes retain the frozen serializer's canonical ordering.

The auditor checks public-input immutability, legal proposals, fallback counters,
equal-public-history proposal/memory invariance and hypothetical referee memory
oracles after calls. All sampled turns match both frozen referees. No turn81
actor view is created. Terminal utility is exact official pairwise rank;
nonterminal utility retains the old static-income heuristic. Every pair, root
action, original/accepted own proposal, public link and result is traced even
when inherited `trace=false`. `beam_width`, `exploration` and `max_nodes` are
accepted for wire compatibility but do not control this root-only evaluator.

Output includes `recommended_action`, reconstructed `baseline_action`, exact
root sums/means, `pair_count`, coverage, policy/oracle counters, public prefill
and paired traces, unchanged posterior diagnostics, source pins and timings.
Exact utility-sum ties prefer the reconstructed baseline, then `engine.ACTIONS`
order. Any source, inference/cap, policy, memory or referee error aborts the whole
job; no hypotheses/actions/cases are dropped. Exceptions propagate.

This architecture changes future own control, root allocation and pairing as
well as the continuation target. It is a package comparison, not a one-factor
ablation. A fallback-only e8 rollout would retain future MCTS control and would
be different. No playing-strength, optimality, equilibrium, online200ms or CUDA
qualification follows from this reference.

```powershell
python -m unittest aligned_search.test_evaluator aligned_search.test_independent -v
```
