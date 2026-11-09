This prospective adapter lets the later primary evolution use the original
Blocker and Feint architectures as well as the existing e8 CONFIG family. It
does not change the active four-arm study, choose its winner or execute a new
generation. The running study's 49 source files remain unchanged.

`TemplateSpace('original-blocker')` and `TemplateSpace('original-feint')` read
only their exact pinned standalone templates. Default genes reproduce the
original source bytes. An exported variant replaces only the specified numeric
literal spans; imports, comments, inference and game logic, loop budgets,
architecture switches, focal RNG initialization and the direct `player.act`
entry point stay byte-identical. Re-importing a candidate extracts its numeric
genes and requires exact canonical reconstruction. AST similarity alone cannot
admit a changed policy.

| Family | Mutable literal sites | Other settings |
| --- | ---: | --- |
| Original Blocker | 12 | Fixed original template SHA `1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5` |
| Original Feint | 10 | Fixed original template SHA `f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94` |

Both families may vary `_Core.ALPHA`, `RHO0`, `STAY0`, `PROT`, `KEEP`,
`CLAIM_THR`, `SHW`, `AGG0` and `CONF`. Blocker also varies `_Core.HOP_RISK`
and `BlockerBot.LEADER_BUMP`/`DENY`. Feint varies its active override
`FeintBot.HOP_RISK`; the shadowed `_Core.HOP_RISK` is excluded. Inactive
classes are never mutated. `POOL`, `K1`, `K2`, `BAIT`, `DYN` and both
`CLAIM_BONUS_SHARE` definitions remain fixed.

Priors and risk thresholds remain in [0.01,0.99]. Economic/defense coefficients
have finite declared ranges in `space.py`. The initial leader bump is bounded
by 0.2, keeping the existing dynamic rival weight plus that bump at most one.
This has a local score-trade interpretation; it is not a theorem about the
global game or a claim that larger coefficients can never help. Any later
range or structural expansion needs an explicit prospective TRAIN protocol.
No bounds were selected from partial results of the active study.

Mutations change one to three numeric genes using a separately seeded Gaussian
operator, clamp to bounds and round to six decimals. A deterministic bounded
step prevents a declared mutation from returning an unchanged genotype.
Different parents/operators can still produce duplicate exports after rounding
or clipping, so the future generation coordinator must enforce unique source
SHAs. Grouped crossover is within a family and can reproduce a parent; it does
not claim to create a distinct new candidate every time.

```python
from evolution_templates.space import TemplateSpace

space = TemplateSpace('original-blocker')
genes = space.mutate(space.defaults, seed=202611090001)
standalone_source = space.export(genes)
assert space.inspect_export(standalone_source) == genes
```

This is source-family eligibility only. New exported SHAs still require actual
runtime/public-input qualification and complete match admission. Original
Blocker/Feint contribute zero legacy `_history` oracle checks; all 320 actor
decisions and both referees remain mandatory. The adapter grants no primary
games, BMCTS audits, stronger-play evidence, heldout access or promotion.

The five author tests and nine independent tests use source/AST checks, seeded
operators and short synthetic public trajectories. The latter are mechanics
witnesses, not strength matches. `STRATEGY_REVIEW.md` explains the coefficient
trade-offs, identifiability limitations and future confirmation requirements.
