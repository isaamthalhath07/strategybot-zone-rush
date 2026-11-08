> Historical consolidation review before the explicit STAY-only clarification. Current rule conclusions and follow-up tests are in [the STAY-only audit](../official/REVIEW.md). Historical source findings remain preserved.

# Branch and codebase review for consolidation

Audit date: 2026-11-08. This review records evidence and limitations; the new
registered comparison determines the final selection. No historical strength
number below is an estimate against actual competition entrants.

## Scope and reproducible sources

The audit inventories all ten GitHub branch tips plus the open fork PR #10 at
`9fa61215ed4bb6e47c7b0c71928b409d122eee62`: **282 unique Python source blobs,
all parsable**. `static_scope.json` records imports and tooling/data-access call
sites for manual categorization. It indexes the Python source blobs,
checks parsability and import/call surfaces, reads the rule engines, worker and
simulator boundaries, release/build code, branch research reports and raw result
schemas, and traces the principal policy families. This is a combination of
whole-tree static inventory and targeted manual review, not a claim that every
line of every generated result file was manually read.

`branch_inventory.json` records branch commits, file counts, exported policy
hashes and aliases. The old working-tree forward policy is the same frozen
`d2bef4e077e9...` export already preserved in the committed forward submission.
The original dirty checkout was neither altered nor used as a mutable test source.

The frozen comparison corpus contains **69 distinct source files**: 36 primary
contenders and 33 potential tester/control bots. Files shared by several branches
are entered once. The twelve PR #10 novel policies are class-based; each export
adds a simple per-seat `act(state)` wrapper calling the original class's `act`
directly, exposing rather than swallowing internal errors. Their source module
hash and original commit are recorded. PR #10's distinct v9 route is built from
its own `mybot.py`, `ship.py` and `v9_params.json`; its root `bot.py` is only the
older fusion and would otherwise hide that contender.

All frozen exports import only standard-library modules. The AST audit found no
`open`, `input`, `exec`, `eval`, `compile` or `__import__` calls in those initial
exports; neither a repository-local module nor a private referee handle is a
required playing input. The selected export subsequently passed direct public-input, reset, private-counter
oracle and real-worker checks; see [the completed report](../REPORT.md).

## Whole-codebase module assessment

| Module group | Assessment and compact disposition |
|---|---|
| `engine.py`, `arena.py`, map generators, `gpuenv.py` | Reference physics are essential; the GPU engine already has an explicit presence-catch switch. Keep one pinned runtime referee and rule contract rather than several competing default readings. GPU training is offline and not needed by the compact runtime. |
| `mybot.py`, `econ.py`, `fusion.py`, `probot.py`, `agent_new.py`, rival/zoo/AI-field policies | Distinct economic, beam, robust-interface and counter-policy families are represented in frozen contenders or tester sources. Keep the measured standalone winner, not all development import graphs. |
| `tune*`, `measure.py`, `choose.py`, `bench.py`, `h2h.py`, `calib.py`, `final_eval.py`, RL scripts | Offline training and measurement tools legitimately hold referee state and load trusted code. Their private state must not cross into the playing view. Keep the new registered comparison tool/evidence; archive the historical trainers in Git history. |
| `audit`, `strategy_audit`, `crossfield`, `freshlab`, `futurelab`, `territorylab`, `apex` | These retain different hypotheses, baselines, source locks and consumed trials. Preserve their substantive findings and exact candidate sources; do not present all their incompatible "current bot" claims as simultaneously true. |
| `harness`, `human_arena`, local HTML/JS, recording storage | Source snapshots, per-seat worker isolation, bounded messages, origin validation, stale-action protection and fail-closed recording form the useful runtime boundary. Keep one simulator/UI path and its tests. Historical analysis scripts with local Downloads paths are not runtime dependencies. |
| Parameters, neural weights, result JSONs and saved replays | Weights are meaningful only with their exact implementation. Result tables are evidence, not more policy code to concatenate. Preserve new validation plus source provenance; historical records stay retrievable by commit without being rebound to a new root file. |

## Branch inventory and distinct findings

| Branch or PR | Relevant finding | Consolidation treatment |
|---|---|---|
| `main` (`d385e00`) | Fusion primary plus warm walk-planner fallback; input normalization, cold-start recovery, direction calibration, cooldown gating, stuck-job escape and arbitrary-corner starts | Keep engineering lessons; test the actual exported policy under current rules |
| `claude/rulefix-stuck-home` (`ed708f3`) | Original guarded fusion (`b2de2f...`); same economic primary as main | Distinct frozen contender, not a separate independent theory of play |
| `codex/fresh-opponents-and-adaptation` (`13cd215`) | Fresh synthetic-opponent calibration, territorial and forward experiments; corrected human arena | Preserve verified current-rule tracking and simulator contracts; do not pool incompatible studies |
| `codex-audit-and-robustness` (`3e787a9`) | Completion-income, route-progress and observed-home corrections; v7/v8 controls | Preserve correctness fixes and exact baseline provenance |
| `hardened-field-and-fixes` (`961e729`) | Beam route planner with learned shield/commit tendencies | Useful baseline, with older endgame and shield assumptions |
| `research/evolution-2026-11-07` (`0796039`) | Evolved economic macro-action policy and transfer genome | Strong, fast distinct family; include evolved, transfer and user-corrected exports |
| `shaunakbr1` (`9b7432b`), `shaunakbr2` (`4baf239`), `visual-harness` (`7fa9b73`) | Same root policy hash `f7b40080a522...`; v9 Bayesian goal forecasting and rejected forecast-based defense | Deduplicate the identical export; preserve evidence that better prediction is not automatically better play |
| `v7-independent-field` (`c7cbaa9`) | Separately tuned route weights and fields | Distinct tester/contender; old field-specific lead does not establish a present champion |
| Fork PR #10 (`9fa6121`) | Novel v9 route and twelve independently briefed opponent designs | Include the generated route and all twelve actual class policies, especially Racer/Blocker/Feint |

Apex (`641c909b7ef1...`) is another distinct committed contender. Its strong
three-copy evolved-opponent result is a specialist stress case, not proof of a
universal lead. Primary contenders also include the already-corrected presence
research/transfer/forward variants and their immutable historical controls.

## Rule contract and concrete incompatibilities

The current user instruction is authoritative for this consolidation:
**movement resolves first; Shield catches every eligible rival on the owner's
territory after movement**, including arrivals, moves between that owner's cells,
and a rival using its own Shield. Rivals frozen at turn start are ineligible;
moving completely off that owner's land escapes. Freeze blocks the next two game
turns, does not earn work, and a shield has a separate four-turn cooldown.

1. **Older models implement a different catch condition.** For example, Apex's
   `src/sim.py` at the audited commits skips a victim whenever `eff[j] != "STAY"`.
   That is a direct mismatch with the clarified rule, not a strategic preference.
   Its simulated bait/escape/world-search values therefore cannot be taken as
   correct under the new rule without a model correction and revalidation.
2. **Freeze attribution can be ambiguous.** A visible freeze alone does not prove
   which player shielded. Assigning it to the previous cell owner or forcing a
   single cooldown history can make the planner think an actually ready defender
   is harmless. The corrected presence tracker enumerates compatible public
   explanations and retains ambiguity; those invariants are worth preserving.
3. **Moving to another cell of the same defender is not an escape.** Bait/escape
   logic must leave the defender's whole territory. Old source snapshots must
   remain unmodified evidence; promotion requires testing the rule-corrected
   version, not merely relabeling an old benchmark.
4. **Completion income and opportunity costs matter.** A completed claim/raid
   earns that turn's income; banked progress is lost on leaving; a final-turn
   Shield must be compared with the bot's own productive STAY. Correctness
   regressions in the merged tree cover these; tuning cannot substitute for
   getting their accounting right.

## Strategy assessment

| Family | Advantages | Limits and decision |
|---|---|---|
| Economic macro-action planner | Very fast; values claims, upgrades and raids over an income horizon; reliable small standalone artifact | Limited foresight, calibrated risk assumptions and possible renewal traps; strongest rate policy must still be compared on diverse maps and opponents |
| Multi-visit beam walk planner | Plans several productive visits; can preserve route progress and exploit cooldown windows | Candidate pruning and approximate shield pricing can undervalue unseen opportunities; more code and latency; do not transplant tuned weights without their matching logic |
| Goal forecasting / racing | Uses rivals' public movement to avoid doomed races and work in less contested areas | Evidence is sparse and working-in-place is hard to distinguish; forecast accuracy and placement gains are different metrics; retain only a measured decision gain |
| Explicit forward simulation | Represents future claims, upgrades, blocking, raids and simultaneous actions | Wrong model physics compounds across rollouts; generic opponent continuations can be worse than a strong prior; more runtime and state-estimation exposure |
| Exact known-policy prediction / Apex | Can exploit deterministic exact copies without reading their hidden current action | Near-copies can match for many turns before diverging; learned identity is not proof; specialist trios overstate generalization; perfect-model policy-improvement arguments require an actually correct model |
| Fusion and public-interface guards | Contains crashes, adapts board/action formats, recovers from cold starts and unsupported jobs | Combining two policies adds state and maintenance burden; engineering improvements do not confer the other policy's statistical strength |
| Neural / PPO route | GPU engine supports high-throughput offline self-play; inference can be flattened in principle | The retained NN loader reads external weights and imports the development tracker; it is not the requested standalone artifact as written; historical training plateaued and no competitive promotion is supported |
| Weak/buggy archetype zoo | Useful fault, legality, timeout and fallback controls | Many are intentionally naive, illegal or slow; winning against them inflates averages and is insufficient for selecting the strongest tester set |

No strategy is promoted because it has more mechanisms. Appending forecasting,
exact-copy exploitation and long rollouts to the fastest policy can reduce its
strength or break rule parity. A smaller rule-corrected policy with measured
performance is preferable to a larger unvalidated combination.

## Historical claims checked

`historical_claim_checks.json` recomputes every focal pairwise score directly
from the four final scores and recomputes counts, mean PW and mean score for six
archived final/confirmation studies. All six are internally consistent. This
checks their arithmetic, not their external validity or complete replay fidelity.

- Fresh calibration: **+0.0752 PW** on 1,024 final paired tasks and **+0.0571** on
  another 1,024 balanced tasks. It supports the exact v8 artifact on those old
  synthetic fields, not a claim about the new rule or fused export.
- Territorial intent: **+0.0552 PW** on 896 spatial-opponent tasks, followed by
  **-0.0022** on 896 further economic-opponent tasks. The second study does not
  establish a replicated gain. The fixed two-rushers-to-edges rule also failed.
- Conditional one-job futures: **+0.1389 PW** on 864 tasks, then **+0.2545** on
  448 native-clock confirmation tasks against a frozen walk baseline. This does
  not establish a lead over the stronger evolved/presence family.
- Goal forecast branch: its report records **+0.100 PW** against the novel field
  over 1,200 games, but **+0.008 +/- 0.019** on the diluted grand field. The
  forecast-based defense experiment missed its own promotion condition despite
  saving cells. These text claims are inspected, not independently rerun in full.
- Apex's recorded confirmations are old-rule, copy-sensitive results. They remain
  valuable tests of predictability and specialist exploitation, with no automatic
  transfer to the clarified rule or to novel near-relatives.

All twelve novel exports also completed one 80-turn public-contract smoke game
against three independent presence-transfer instances: **zero exceptions, illegal
outputs or input mutations**. The saved diagnostic is `novel_public_contract.json`.
One game per design is a contract check, not a strength ranking; its scoreboards
must not be treated as confirmatory evidence.

## Measurement and compact-repository decisions

- Deduplicate by exact source bytes; record full source SHA and original commit.
  Distinct branch names do not imply distinct bots, and a new filename is not a
  fresh experiment.
- Compare actual process-isolated callbacks under the 200 ms turn / 2 s first-turn
  limits. Historical pinned or virtual clocks can establish deterministic
  equivalence, but cannot certify live runtime limits.
- Use score-only ties for Round 1, and compare on the same maps, seats, token
  starts and opponent lineups. Track actual board contents: fresh seeds can
  produce repeated boards. Balance all 16 seat/token combinations for final
  comparisons; do not select only one favored seat or all-copy trios.
- Old selection/final sets are consumed. Freeze final candidates before fresh
  follow-up data, report uncertainty, and distinguish a measured winner from a
  proof of universal optimality. Select testers for strength and differing
  decisions, not just shared ancestry or easy-to-beat bugs.
- Retain one pinned referee/worker boundary, the human simulator and its recording
  and AI-view tests. Remove duplicate live catalogs, obsolete build defaults and
  research scripts from the compact branch; keep their commits and this review.
- Offline trainers, dynamic test loaders and GPU dependencies belong in historical
  research, not inside the submitted `bot.py`. The runtime policy receives only
  the four public observation fields and its own remembered public history.

The reference engines and GPU environment use private state legitimately for
refereeing, offline labels and differential tests. That is distinct from feeding
private counters, requested human actions or future realized moves into a playing
policy. The frozen export inspection found no such runtime channel. Exact public
policy modeling is not itself cheating, but its unproven identity assumptions are
strategic risks and must be tested honestly.
