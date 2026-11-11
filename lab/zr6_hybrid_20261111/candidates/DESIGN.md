# Adaptive Raider with verified Shield windows

Both candidates start from the exact 39,029-byte `zr6` branch source at `77c867f`, SHA-256 `8b87bf8221c5937fc3bd51562850a6ac550a0cec49681640332b19c4ea0144cb`. The source builder leaves the route beam, holdings model, opponent priors, normal defense decision, input parser and runtime clock intact. It adds two narrow tactical mechanisms derived from the verified 5bc bot's cooldown and contest handling.

The earlier 1,000-game comparison motivated keeping `zr6`'s existing same-owner sidesteps. Many of its upgraded central captures follow a successful hop to another cell of the same defender and three consecutive stays there. A forced return to the origin would discard that option. The matched games show an association between those tactics and the larger advantage in territory and rank. They cannot isolate the contribution of each policy feature because the routes and opponent reactions differ over whole games.

| Candidate | SHA-256 | Changes |
| --- | --- | --- |
| `zr6_window.py` | `1441c61e57e368ab8a3704c834e53c9351461127a3dab2c0dbffb7dbf2f79684` | Add an optional follow-up to an actual sidestep after confirming the defender cast Shield. Compare the landing cell and return to the original cell. |
| `zr6_window_route.py` | `21088da5e184827c02364230fbe1e9b57540a67861ef74f47ffe4e45b4339d60` | Also compare actual legal sidestep choices using destination payoff, remaining work, token and owner priority, and return safety. |

The cast check intersects every compatible Shield pattern derived from the previous and current public boards. It excludes previously frozen or moving casters, seats whose observed work proves they could not have cast, and previously certified cooldowns. It accounts for catches and backfires under the effective-STAY rule. A single best-fitting explanation from the original opponent model never authorizes a continuation by itself. The proof uses only past public observations.

After a verified cast and successful hop, an optional capture must fit within the four unavailable Shield turns and the game deadline. A move into an occupied square is rejected. A contested move must win for every priority token consistent with public evidence. The existing capture valuation compares the landing and return, with the follow-up required to earn at least 98% of the planner's best individual job rate. The chosen target and its valuation are checked on every callback. An economically better ordinary action or the original Shield decision can end the commitment.

The route candidate preserves both kinds of sidestep. It prices an actual adjacent same-owner destination or a safe return to the original tile using fresh work and elapsed turns. A defender who casts may catch another eligible rival, so the escape payoff excludes speculative backfire value. The conservative contest checks can reject a hop that would have succeeded in the particular simultaneous action combination. The unchanged beam also still approximates hypothetical raid jobs before arrival, which can overstate a route that the stricter tactical step later rejects. These tradeoffs require fresh comparison.

Targeted referee fixtures passed for both exact sources. A unique Shield backfire after a same-owner hop opened a verified capture window and the richer landing cell changed ownership after three new stays. An ambiguous freeze produced no certificate. Owner priority and the turn-80 finish boundary behaved as intended. These engineering fixtures executed no strength games.

The `_MEMS[seat].hybrid_diag` counters record selected hops, verified windows, follow-up decisions, changed decisions, observed ownership flips and changed sidestep choices. A selected hop can fail or meet no cast. The observed ownership counter can miss a capture on the final turn because there is no next observation. Use the actual game tape for capture totals and keep the diagnostic counts separate from causal attribution.
