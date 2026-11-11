# Prospective numeric-family strategy review

The proposed12-gene Blocker and10-gene Feint spaces are reasonable **restricted first search spaces**, with the recommended first-protocol change `BlockerBot.LEADER_BUMP ∈ [0,0.2]`. I found no denominator, sign or rule-mechanics reason to reject the other proposed bounds. These are prospective engineering bounds, not optimality, exhaustive coverage or strength claims. No partial study result, current game score, candidate game, controller or GPU operation was consumed for this review.

The reviewed exact templates are [Blocker](../tester_bots/blocker.py), SHA256 `1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5`, and [Feint](../confirmation_campaign/evidence/architectures_v2/feint_original.py), SHA256 `f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94`. The relevant equations are in `_Core._rho/_pstay/_aggr/_update_alpha/_prot/_conflict/_jobs/_search/_defend`, both `_pick` methods and the Blocker bonuses. [space.py](space.py) is an exporter, not an executed policy experiment.

The final first-protocol exporter adopts the0.2 leader cap; its reviewed SHA256 is `bce6dd1fa5950a8752182ce4c70e17ea10d74245a7fe650cc735b3483b2ae041`.

## Bounds and actual meaning

| Gene | First-protocol bounds | Interpretation and limiting cases |
|---|---|---|
| `_Core.ALPHA` | `[0,1]` | With fixed `DYN=True`, mainly the protection-premium coefficient, **not** the ordinary rival-denial weight. |
| `_Core.RHO0` | `[0.01,0.99]` | Initial estimated probability of a shield response, with fixed pseudo-count strength2.5. |
| `_Core.STAY0` | `[0.01,0.99]` | Initial observed-arrival stay rate used in level1 shield defence, with strength3. |
| `_Core.AGG0` | `[0.01,0.99]` | Initial raid-threat intensity, later increased by observed raids and scaled by mobility. It is not itself a calibrated probability. |
| `_Core.PROT` | `[0,1.2]` | Protection/fortification premium; zero removes this premium and makes `ALPHA` behaviorally inactive under the fixed normal `DYN` path. |
| `_Core.KEEP` | `[0,1]` | Retain the old target if its rate is at least `KEEP × best_rate`. Lower values mean **more** commitment; zero can retain a very weak target while it remains in the candidate list. |
| `_Core.CLAIM_THR` | `[0,1]` | Threat discount on bare neutral claims. Zero removes that discount, not all raid-risk modeling. |
| `_Core.SHW` | `[0,2]` | Shield-benefit multiplier. Zero disables voluntary shield defence in these entry policies. |
| `_Core.CONF` | `[0,1]` | Strength of the forecast-conflict discount. Zero removes that discount, not forecasting, decoy logic or Blocker route/sniping terms. |
| Active `HOP_RISK` | `[0.01,0.99]` | Threshold for hopping while working vulnerable rival land. Use `_Core.HOP_RISK` for Blocker and `FeintBot.HOP_RISK` for Feint. |
| `BlockerBot.LEADER_BUMP` | **`[0,0.2]`** | Additional leader-denial weight. Default0.15 remains available. |
| `BlockerBot.DENY` | `[0,1]` | Scales one close neutral-cell denial term. Zero does **not** disable route blocking, parking, sniping, raid bonuses or the leader shield multiplier. |

`FeintBot.HOP_RISK` overrides `_Core.HOP_RISK`; excluding the inactive inherited Feint locus is correct. `KEEP` is used by both the base and Feint override. Every other proposed locus has an active use, but many require particular public contexts before changing an action.

## Numeric safety and value signs

Writing observed counts as `h,n`, the response estimates are

\[
\rho=(h+2.5RHO0)/(n+2.5),\qquad p_{stay}=(h+3STAY0)/(n+3).
\]

The denominators stay positive and the estimates stay in `[0,1]` when the source's observed-success counts do not exceed opportunities. Changing the prior mean does not change its fixed strength; its influence decays as `2.5/(n+2.5)` or `3/(n+3)`. These are public behavioral estimates with heuristic event attribution, not identified real opponent types.

The aggression calculation clips at1.4, and the distance threat table is in `[0,1]`. Consequently the raid retention factor `1−0.3×aggression×threat` is at least0.58. Aggregate cell threat is clipped at0.9, so `1−CLAIM_THR×threat ≥ 0.1`. The forecast discount is a product of three factors `1−m×lo×CONF`, with `m≤1` and `lo≤0.9`; every factor remains at least0.1. At strong conflict the existing `f≤0.05` filter can still remove neutral jobs. That is a discontinuity, not a negative reward or singularity.

The protection term is

\[
PROT\;thr\;b\,[R(1+ALPHA)/2+8ALPHA].
\]

It remains nonnegative. Its upper range can strongly favor fortification; this is a modeling/strategy choice, not a mechanically necessary reward bound. `ALPHA=0` still leaves an own-income protection component when `PROT>0`.

All job work times remain at least1; travel and waits are nonnegative. First-, second- and third-job rate denominators are therefore positive. Forecast normalization checks positive total mass; Feint's apparent-value normalizers have explicit fallbacks; its `r/top` uses a positive retained job rate. The shield opportunity-cost scale starts positive and updates toward `max(best_rate,1)`, so `SHW=0` cannot create a zero denominator or reverse a positive shield cost. No whitelisted parameter changes those guards, the80-turn clock, capture rules or action legality.

Blocker bonuses do use that endogenous opportunity-cost scale, so estimated rate and blocking premiums can reinforce one another. Keeping parameters finite and bounded does not make this proxy an independently calibrated value function. Selection must use actual completed-game rank utility, never the policy's internally inflated job scores.

## Pairwise incentives and the leader cap

For official pairwise utility, an isolated increase `δ≥0` in our score helps every rival comparison; an isolated equal decrease in one rival's score helps only that comparison. Pointwise,

\[
U(s+\delta e_f)-U(s)\;\ge\;U(s-\delta e_r)-U(s).
\]

The source approximates relative damage value by normalized projected-margin densities, then clips ordinary rival weights to `[0.1,0.8]`. A leader bump at most0.2 keeps their sum with the bump at most1. The originally suggested0.5 permits1.3 and abandons that local marginal-score interpretation. Damaging a distant leader may primarily help the other rivals while sacrificing a closer own rank boundary.

This supports0.2 as a disciplined first bound, **not** a global optimality theorem. Route occupation, timing, uncertainty and forecast error are not isolated score transfers. A larger weight could compensate a misspecified model or select a useful spatial tactic. No obvious strategy requires retaining0.5 now: all route/parking/sniping/leader-shield mechanisms remain present. Nevertheless0.2 can exclude some action phenotypes. A later expansion should be an explicit prospective TRAIN-search protocol, without treating the current study as an adaptive tuning panel.

## Identifiability, mutation and omissions

The space has meaningful interactions and broad action plateaus. `ALPHA` and `PROT` jointly determine protection and become unidentifiable when `PROT=0`. `RHO0` and `HOP_RISK` jointly govern threshold crossings. `STAY0` and `SHW` jointly affect defence; `AGG0` interacts with protection and bare-claim discounting. Aggression saturates after enough observed raids, making its initial prior less influential. A changed numeric literal need not produce a changed action, and an unchanged action need not prove the gene useless.

Distinct1..3-locus Gaussian mutation with default standard deviation `0.06 × range` and six-decimal rounding is a defensible local operator. Clipping creates boundary mass; `CONF=1` starts on a boundary. The export/mutation path should reject nonfinite/Boolean values, guarantee a genuine numeric change after clipping, and deduplicate candidate exports by SHA256. The current implementation's bounded deterministic fallback addresses an unchanged mutation proposal. Default export must retain original literal spelling and all other bytes exactly. A preserved initial RNG seed does not preserve future draw alignment when different decisions consume different numbers of draws.

These loci mainly optimize shared economic/risk behavior. They do not exhaust either architecture. Important fixed Feint controls include decoy mix, near-tie slack, honest-route probability, decoy refresh probability and path-bias magnitudes. Fixed Blocker controls include leader persistence, route/parking/sniping weights and thresholds, and the leader shield multiplier. In particular, `DENY` is not a master Blocker knob. Their omission is reasonable for a first low-dimensional space, but forbids a claim of exhaustive structural optimization.

Keep `POOL=22`, `K1=8`, `K2=5`, `BAIT`, `DYN`, `CLAIM_BONUS_SHARE`, all observation/inference code, direct `player.act`, focal public-seat RNG initialization and all non-whitelisted bytes fixed. This preserves the intended architecture and bounded planning structure, though it does not prove equal wall time for every genotype. Register operator scale, any grouped crossover, sources and selection rules before fitness is read. Validate family candidates with fresh complete games, legal public inputs, deadline/fallback checks and independent referee/actor admission. No gene value, source identity, map lookup or oracle feature should be selected from partial study outcomes.

This review creates no candidate files, games, evolution round, deployed policy, primary credit, completed per-game BMCTS credit or promotion.
