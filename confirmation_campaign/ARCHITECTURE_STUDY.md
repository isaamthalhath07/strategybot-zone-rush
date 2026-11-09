# Four-policy architecture confirmation, V2

The next large comparison must include the strongest measured alternative
implementations. Continuing nearly two million games of e8-only numerical
evolution risks optimizing the wrong policy class. This is a new extra-control
study; it does not replace accepted primary games or retroactively change their
protocol, sources, opponents, scores or credit.

V1's two-policy confirmation was prepared but never played or distributed. V2
supersedes that unused plan explicitly and preserves its original files. No V2
games are executed by the preparation tool, and the registration itself grants
no dispatch or promotion permission.

## Frozen policy arms

| Arm | Exact source SHA-256 |
|---|---|
| Current guarded Transfer, e8 | `e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5` |
| Audited defense-tuned Transfer, 50d | `50d82d7ac58162e9cf651136afcedac5586db9a060f153854b00875f13efef37` |
| Original Blocker | `1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5` |
| Original Feint | `f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94` |

These are four policies, not four independent implementations. e8 and 50d share
the guarded Transfer logic and differ in frozen numerical genes. Blocker and
Feint share the archived novel-bot core and differ in the selected behavior
constructor. The latter equivalence is checked by normalizing only the final
`act()` constructor and comparing the full AST. All focal files are exact byte
copies; the study introduces no controller patches or new runtime time cutoffs.

Selection evidence comes from commit
`ae1c29646e7a7293e3ac663da4324be5a80323b0` on
`origin/codex/all-branches-validation`. Its late panel used 24 maps, three fields,
all sixteen seat/token crossings, and 1,152 games per policy. Original Blocker
scored 2.2148 pairwise wins, Feint 2.1645, and e8 1.9553. Those results justify
including these arms; they are consumed selection evidence and are not V2
confirmation results. They do not prove performance on the new opponent mixture.

The branch source archive, its manifest, late raw results/spec/summary and exact
Feint body are pinned under `evidence/architectures_v2/`. The source archive SHA
is `5248b15452932ca2637094fd44d39a43627707c4c31443568e6cfcdd1ad979fb`.

## Fresh maps and matched conditions

V2 reuses the 128 V1 maps and rival parameters only after validating the original
sealed V1 recipe and checking nonconsumption. Each map is crossed with:

- Four fields: economic, independent, erratic and pressure.
- Four focal seats and four starting priority tokens.
- All four frozen policy arms.

The plan contains **8,192 matched conditions and 32,768 complete 80-turn matches**.
Each condition keeps the same rival source/parameters/RNG seeds across arms for
a lower-noise paired comparison. The policies still interact with independently
responding rivals: future actions are not replayed from a different arm's game.
Each match has fresh focal and rival identities, a fresh actor namespace and a
unique task ID. Matched parameters do not mean shared in-game memory or access
to another player's planned action.

All maps remain disjoint by quarter-turn rotation orbit from the complete
10,000-map primary catalog and local historical evaluation maps. Additional
cross-branch exclusion checks cover **all eleven branch_audit `*_spec.json`
files**, not just the late final panel. Those files contain 64 distinct map
orbits. Their exact raw files are archived in `consumed_map_specs.zip`, with
source hashes and orbit lists in `crossbranch_map_coverage.json`. This
conservatively excludes any planned-only panel too. The original V1 maps have
zero overlap with those 64 orbits.

The cross-branch orbit fingerprint is
`3d94d213db0cba064608e8da74424efd4c97c292a3bab54ad1f157836cd2bd45`.
Any detected overlap causes preparation to stop. It does not silently remove
unfavorable maps or choose a new seed after viewing outcomes.

V1 nonconsumption requires its directory to contain only its two source files
and sealed registration. It also checks declared local distribution/return
locations for the V1 control ID or original task IDs. This is a scoped local
check, not cryptographic proof about deleted files or unobserved external
machines. The owner must keep V1 undispatched. A separate V2 supersession record
preserves this limitation and V1's unchanged fingerprints.

## Preregistered inference and reporting

The primary outcome is official Round 1 pairwise wins: each rival outscored is
one point and a tied score is half a point. Maps, fields, seats and tokens have
equal weight. Raw score is reported separately.

All six pairwise arm comparisons are fixed before outcomes. The map-cluster
bootstrap resamples a whole map with all fields, crossings and arms together.
It uses 60,000 resamples and fixed seed 202611091740. Bonferroni adjustment targets
an overall 95% simultaneous confidence family by assigning alpha `0.05/6` to
each two-sided interval. Percentile tails are `0.05/12` and `1-0.05/12`, using
zero-based empirical order statistics 249 and 59,749.

These are Bonferroni-labelled descriptive bootstrap intervals. Approximate
bootstrap coverage, finite map sampling, opponent-family choice and selection
effects prevent a claim of finite-sample familywise coverage or universal
superiority. Report every comparison, rather than only the largest winner's
contrast. Report each arm's overall mean, all four field means, worst-field mean
and contrasts, score, faults and timing. Per-field intervals are explicitly
exploratory unless a later independent protocol specifies their own adjustment.

There is no automatic promotion. A broader architecture choice requires complete
results, valid independent replay, source/runtime checks and a separate release
decision. If a further candidate is tuned using this study, it needs another
unconsumed final confirmation; these maps cannot remain "final" evidence after
their outcomes influence that tuning.

## Runtime qualification and accounting

The existing eight numerical-Transfer qualification controls do not qualify
structural Blocker/Feint logic. V2 predeclares `required_focal_sources` containing
all four exact hashes and `runtime_qualification_task_ids` containing eight
original study tasks: all four arms at map 0 / economic / seat 0 / token 1, and
map 0 / independent / seat 1 / token 2.

The owner may execute those eight actual control tasks as qualification goldens,
preserving their original task IDs, complete raw games, source hashes and full
audit evidence. They count once among the 32,768 study matches, never as new
primary games. They must not be silently regenerated as different study tasks.
Separate helpers then qualify against those exact focal sources and perform
independent peer audits under the reviewed transport protocol.

Original Blocker/Feint lack the Transfer-specific `_history` oracle. Some valid
fixtures therefore produce zero Transfer-memory oracle checks. Extra-control
audit evidence must calculate the actual applicable count rather than inventing
80 checks. Every match still requires both referees, all 320 actor decisions
regenerated, legal actions, unchanged public inputs and deadline checks. The
frozen primary audit schema is not altered to accommodate this new role.

The registration role is `extra_control_assignment`. Primary credit, full BMCTS
audit credit and automatic promotion remain zero. The actual four submission
policies run as standard-library Python on CPU; GPU physics/search experiments
are separate work and cannot be counted as their complete-match evaluations.

## Preparing and verifying

```powershell
python -m unittest confirmation_campaign.test_architectures -v
python -m confirmation_campaign.architectures --parent-v1 .cache/confirmation/defense_50d_001 --output .cache/confirmation/architectures_v2_001
```

The tool refuses an existing output directory, copies exact source bytes,
constructs fresh actor/task identities, validates all four-way parameter matches,
pins source/evidence/protocol hashes, and seals the new registration. It never
executes or distributes the schedule. Corruption tests cover missing/changed
arms, rehashed rival changes, leaked maps, consumed V1 data, identity reuse,
qualification coverage and scope/credit drift. Unit tests mock only prior
admission; they execute no campaign games.
