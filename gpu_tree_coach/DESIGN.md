# Public-observation tree search: bounded CUDA prototype

This is an offline observation-tree MCTS prototype, not a deployed bot, a primary game runner, or a proof that search improves playing strength. It uses actual batched CUDA physics **and** integer public-observation rival/rollout policies. The information tree and sequential UCT bookkeeping remain on the CPU. Existing frozen engines, bots, and campaign assurances are unchanged.

## Decision and information boundary

An input contains the initial four-field public observation, the complete sequence of accepted own actions and subsequent public observations, and bounded diagnostic settings. It accepts no actual game, controller, private counter, actual opponent seed, or future action stream. Exact shape/type checks precede inference. Maps must obey the mirrored integer 1..3 map contract.

`PublicBelief` reconstructs correlated physical states from that public prefix. The retained support is a possibility set, **not a likelihood-weighted posterior**. The prototype samples uniformly from retained states, not independently from cooldown marginals. Capped support and dropped states are reported by the existing inference summary; an unexplained later observation is unsupported, without a fabricated repair or recommendation.

Draw keys are SHA-256 of the model version, public-prefix SHA, explicit diagnostic seed, domain, simulation index, and seat. Arbitrary root IDs, chunk order, packet hashes, real controllers and hardware are absent. The fixed focal rollout key excludes the simulation index. Hypothetical rival keys vary between simulations and remain fixed within one simulation. These are diagnostic hypotheses, not recovered actual rival identities.

All four policies receive their own public views of the same pre-turn state. Rivals are computed before the tree's chosen focal action replaces its default action; no rival model receives that chosen action. A rival may use its own advertised legal actions and priority, as a real player can. Focal UCT receives only node ID, stored public observations, and accumulated statistics. Inferred scores, progress, cooldowns, hypothetical types and sampled particles are never node keys or focal selection features.

## Sequential search over public histories

Each iteration performs **one simulation per independent root**, then completes its entire backup before another simulation at that root. Batching different roots increases device occupancy without delayed updates or virtual-loss approximations within a tree.

At every node each legal action receives two visits before optional pruning. Thereafter the active set is the best `beam_width` actions by their then-current empirical mean; this initial beam is **fixed**, so early sampling noise can permanently exclude a good action. Set beam width 6 to disable action pruning. The selected active action maximizes

\[
  {Q(h,a)\over6N(h,a)} + c\sqrt{{\log(N(h)+1)\over N(h,a)}}.
\]

Tie breaking is canonical action order. The root recommendation uses the largest empirical mean, then visit count, then action order. This is a finite-sample heuristic against an assumed opponent model, not a multiplayer equilibrium or best-response guarantee. An initially lucky, sparsely sampled pruned action may still have the best reported root mean; both its two samples and exclusion remain visible.

After a selected action and observed successor, the tree follows an existing child or creates at most one new node during that simulation. Subsequent steps use the fixed public rollout policy. The exact child key is `(parent_id, own_action, public_bytes)` within its root. Parent links preserve the observed history and own actions, so histories with identical current boards can remain distinct. Python dictionaries compare the complete byte strings even when hashes collide.

## Exact compact observation representation

All inferred states must agree on the immutable public base values, home mask and home ownership. The focal ID and these static descriptors are retained per root. Each dynamic public cell is one byte:

| Bits | Field |
| --- | --- |
|0–2|occupant 0..4|
|3–5|owner 0..4|
|6|upgraded Boolean|
|7|frozen Boolean|

The 65th byte stores the focal legal mask in bits0–5 and its public priority flag in bit6. These 65 bytes are an exact representation of the public observation **under that verified static contract**. They omit no dynamic public cell field. They reveal no opponent remaining freeze duration or cooldown. Packed bytes, rather than 384 Python scalar cell fields, cross the device/CPU tree boundary after a step. Optional diagnostic traces add four action bytes; final integer utilities also return to CPU. Setup transfers the inferred support once.

After inference, prepared roots retain inferred states, the current immutable public view, static descriptors, public-prefix SHA, cap summary and options, not a duplicate raw trace. This preserves the inputs used by **this fixed model**. It is not a sufficient statistic for arbitrary history-dependent rival behavior: a hash cannot reconstruct earlier feints or choices. Future intent models must fit and retain public-history sufficient statistics before discarding that history.

## Clock and objective

Effective horizon is `min(requested_horizon, 80-public_prefix_length)`. `BatchGame.turn` is only a local physics counter after reconstructing a root; `batch.over()` is never used to decide actual terminal time. Every model's public step index also includes prefix length.

For a genuine terminal simulation the value is exactly

\[
U_i=\sum_{j\ne i}\left(2\,\mathbf1[S_i>S_j]+\mathbf1[S_i=S_j]\right)\in\{0,\ldots,6\}.
\]

At a nonterminal cutoff the same rank formula is applied to `score + k*income`, with `k` clipped to actual remaining turns. That projection assumes static future income and is explicitly a **heuristic**. It can miss a planned capture, shielding costs or ranking reversals. Income tail 0 is available for an ablation, but also has horizon bias. Inferred scores enter the referee-side value calculation, not the public policy. Simulated trajectories never receive completed-game audit or primary-match credit.

## Determinism, bounds and quarantine

The scalar implementation uses the independent stdlib referee, a separately written dict-node tree/selector/backup and independent public byte encoding. The tensor implementation uses the frozen integer policy, tensor physics and compact node class. Both share only the declared public-input inference and draw schedule. Tests compare exact recommendations, all node N/Q/children/pruning and every action/observation/value trace. There is no numeric tolerance. Source mutation or any requested scalar check disagreement quarantines the return.

Per-root support and node caps remain the same under chunking. Batch support/root/reserved-node budgets limit active memory. Retained-result and total-root budgets bound accumulated results and ID tracking. A streaming result sink avoids retaining whole output trees. The CLI writes a temporary JSONL receipt and publishes it only after all inputs, source checks and requested comparisons pass. Unsupported roots are explicitly marked and get no recommendation. No private state is accepted from serialized input.

An optional CUDA Graph captures exactly one unchanged integer-policy/physics/packing step. It takes preallocated hypothetical keys, public step indices and requested focal actions. `BatchGame.step` rebinds several tensors, so the captured operation copies every updated dynamic field into stable input buffers before replay. Warmup and capture use scratch state; all mutable fields are restored from the inferred support before each simulation. Graph construction cost is included for every benchmark invocation. No graph captures CPU UCT, samples multiple stale actions at once, or changes the rule engine. A separate15-step regression compares every eager/graph state field, not merely the public result.

## What this resolves and what it does not

Observation branches allow the future focal action to depend on what it will actually see, addressing a limitation of open-loop sequences. Aggregating across correlated states avoids per-particle best-action fusion. GPU integer policy evaluation can accelerate a sufficiently large set of independent searches. CPU selection and synchronous public observation transfers still limit scaling and can make small batches slower.

The rival type mixture, uniform support weights, rollout policy, cutoff value, exploration constant and fixed pruning are uncalibrated. The models have no fitted persistent feint/Shield intent posterior and are much simpler than the archived championship candidates. More search can confidently exploit the wrong model. No architecture or policy promotion follows from speed, parity, this toy fixture panel, or a favorable hypothetical rollout value.

The next legitimate strength experiment should compare against the same frozen public-prefix decision set with exact terminal rank where feasible, separate intent-model ablations from search depth, include Shield feints and delayed bait, then validate any resulting standalone policy on fresh rule-checked complete matches. Runtime/transport qualification for primary actors does not automatically qualify this prototype.
