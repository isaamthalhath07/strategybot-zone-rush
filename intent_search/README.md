# Joint intent information-tree prototype

This is a bounded CPU research prototype. It is not the deployed bot, a new game runner, a full BMCTS audit, or evidence of improved playing strength. It changes no frozen model, referee, earlier search module or campaign source. It needs only the existing standard-library Python environment.

The frozen public-history intent model forecast observed TRAIN transitions better in its separate pilot. Forecast improvement does not prove better decisions. This prototype tests a legitimate way to use that model: sample a correlated physical-state/persistent-type explanation, simulate public responses, and aggregate values in a shared information-history tree.

## Information and sampling contract

Inputs are exactly the opening four-field public observation, every accepted own action and following public observation, a root label and bounded search settings. There is no input for an actual game, score counter, cooldown, controller/type label, opponent seed, hidden snapshot, posterior file or future tape. Strict shape/type checks reject additional fields. A cold midgame view is insufficient. The immutable public map/home descriptors and true public-prefix clock must match every inferred state.

The frozen `IntentFilter` produces normalized log weights over **joint physical-state × three-rival type assignments**. The prototype preserves those weights and their correlations. It does not sample uniform physical support, independently sample type marginals or infer actual rival identities. Each simulation samples one joint pair, then retains all three hypothetical rival types for that entire trajectory.

Sampling uses log-space Gumbel-max over every finite joint log weight; small weights are not exponentiated to zero or explicitly clipped. The implementation uses binary64 arithmetic and 52-bit open-interval uniforms. Its finite uniform resolution bounds attainable Gumbel tails; it is **not exact real-arithmetic sampling**, especially for extremely small posterior masses. Keeping an entry does not guarantee that a finite search can resolve its probability. A declared total joint-sampling work cap rejects oversized requests without removing hypotheses.

Random keys depend on the normalized public-prefix SHA, explicit diagnostic seed, declared model version and domain-separated simulation/depth/seat indices. Root labels, task order, actual opponent seeds and chosen focal actions do not seed rival draws. Focal rollout keys additionally use only the simulated **public** own-action/observation history; they exclude sampled types, private counters and simulation index.

Every simulated actor receives its own immutable four-field view of the same pre-turn state. Rival intention draws are computed before the focal intention is applied. The frozen public `policy` evaluates each rival's retained hypothetical type. Focal fallback uses the fixed public economic policy. Models never receive another actor's realized current action. Public legal actions may depend on that hypothetical actor's own cooldown, as they would in a real view.

## Tree and evaluation

The unchanged compact CPU `Tree` selects actions using only the public-history node and accumulated statistics. Each node is scoped by root and parent, own action and exact 65-byte dynamic public observation; the verified base/home/focal descriptor is static per root. Neither sampled private states nor type assignments are node keys or selection features. Shared future observation branches allow subsequent actions to respond to what the focal actor would see. Retaining one sampled persistent type throughout a trajectory lets subtree visits reflect the corresponding conditional model mixture without per-particle focal optimization.

Every legal action at a node receives at least two trials before optional beam pruning. Default beam width 6 keeps all actions. Smaller beams use the frozen tree's fixed initial pruning rule and can discard good actions after sampling noise. A node cap switches to the same public economic rollout at the same public history across particles. UCT values and recommendations are finite Monte Carlo estimates, not optimal values or an equilibrium.

The effective horizon is clipped to `80 - public_prefix_length`; inferred states also must carry that exact true clock. Every sampled transition, including terminal transitions, is checked against both frozen independent referees, including complete physical fields, income and legal actions. Any disagreement or source mutation quarantines the whole result. This counterfactual referee checking is **not** full-game actor regeneration or a per-game BMCTS certificate.

At the true end, utility is the exact pairwise numerator: 2 for each rival beaten, 1 for a tie, 0 for a loss, summing to 0..6. Before the end it applies that rank formula to `score + k*income`, with `k` clipped to actual remaining turns. That static-income projection is a heuristic that can miss future captures, shielding costs and rank reversals. A terminal leaf has no turn-81 actor observation or child decision. It receives its terminal score directly in backup.

## Running and limits

```powershell
python -m unittest intent_search.test_mcts intent_search.test_cli -v
python -m intent_search --input public_prefix.json --output fresh_search_result.json
```

The input follows this shape; replace the board placeholder with the actual serialized public board:

```json
{"schema":1,"kind":"joint-intent-public-history-mcts/1","root_id":"public-label","initial_observation":{"board":"PUBLIC_8_BY_8_CELLS","bot_id":1,"is_priority_token":true,"legal_actions":["EAST","SOUTH","STAY","SHIELD"]},"transitions":[],"search":{"seed":71,"simulations":32,"horizon":5,"beam_width":6,"max_nodes":256,"income_tail":12,"max_states":1024,"max_particles":65536,"max_joint_intents":200000,"max_joint_sampling_terms":4194304,"trace":true}}
```

Every subsequent transition is `{"own_action":"STAY","observation":NEXT_PUBLIC_OBSERVATION}`. The CLI accepts one public root, limits input to 2 MiB, refuses to overwrite a result and publishes only after complete successful inference/search/source checks. Inference budget failures are explicit; there is no state repair or silent pruning. The maximum accepted settings are 512 simulations, 8 plies, 8192 nodes, 1024 physical states, 65536 state/type pairs and 4,194,304 joint sampler terms. This is not a 200 ms runtime claim or a distributed worker qualification.

Output includes all node visits/value sums, root empirical rank estimates, inferred-model posterior diagnostics, explicit approximations, source pins and optional simulated action/observation/value traces. Diagnostic traces may describe **inferred hypothetical** state/type indices and simulated referee scores; these are outputs, never actor inputs or actual hidden state. Preparation/search wall times are bookkeeping, not a performance or strength benchmark.

Tests cover hidden-distinct worlds with identical public prefixes, joint correlation/nonuniform mass, unchanged complete filter weights, persistent types, simultaneous public actors, shared public fallback under node caps, exact true-terminal backups without turn-81 views, all-turn two-referee checks and source/referee quarantine. Fixtures are synthetic public prefixes; no primary, architecture-study or held-out outcome is consumed.

All four rival policies react to the current public board; only the behavioral type persists. The model does not infer persistent goals, route commitments or an opponent that adapts its strategic plan.

A strength claim would require a separate preregistered fresh-match comparison with the same legal/public information and runtime constraints. Wrong persistent types, poor model calibration, simple economic rollouts, finite samples, horizon bias and optional pruning can all make more search choose worse actions. No model is promoted or deployed here, and all new-game/primary/completed-game/full-BMCTS credit remains zero.
