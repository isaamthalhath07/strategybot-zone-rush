# Novel opponents

Twelve opponent bots written by four independent agents, each given only the
rules (the rulebook summary and `engine.py`, the referee) and explicitly
forbidden to read any bot in this repository — `bot.py`, `mybot.py`, the zoo,
the AI field, the held-out designs, ProBot, the outside designs in
`../outsiders.py`, and the documentation that describes them. They exist to test
the shipped bot against designs that share nothing with its lineage.

| file | family | bots |
|---|---|---|
| `novel_a.py` | search and simulation | `nv_a_mcts` (tree search with rollouts), `nv_a_paranoid` (worst-case lookahead against the nearest rival), `nv_a_rhea` (rolling-horizon evolution of 8-move plans) |
| `novel_b.py` | adversarial to forecasters | `nv_b_feint` (moves so that its real target stays ambiguous to goal inference), `nv_b_blocker` (spatial control of the leader with the closed-cell and token rules), `nv_b_racer` (forecasts rivals itself and races only where it wins) |
| `novel_c.py` | economic philosophies | `nv_c_voronoi` (claims what it reaches first), `nv_c_bloomer` (fortress first, mass raids in the last 25 turns), `nv_c_portfolio` (bandit over five heuristics) |
| `novel_d.py` | in-game learning and social | `nv_d_titfortat` (raids only those who raided it), `nv_d_antileader` (reconstructs scores and attacks the leader), `nv_d_shieldmaster` (precise shields, baits, cooldown-window raids) |

**Verified independently** of the agents' own reports by
[`../verify_novel.py`](../verify_novel.py) (`../results/novel_verification.txt`):
zero exceptions with `act()` called directly, at most 7.8 ms per move on average,
and 1,985–2,821 points against spine / pro / camper, against 1,500–2,050 for the
outside designs on the same yardstick.

**Determinism.** The three `novel_a` bots search until a wall-clock deadline.
The audit harness gives that module a virtual clock calibrated to each bot's
real search speed (`VIRTUAL_STEP` in `../edge_audit.py`), so they search as long
as they do in real time on average but play identically on every replay, which
paired measurement requires. The other nine are deterministic as written.

All twelve use the starter-kit interface — `act` on the view, a string from
`legal_actions`, standard library only — and are registered automatically by
`edge_audit.py` (tiers `novel` and `grand`).
