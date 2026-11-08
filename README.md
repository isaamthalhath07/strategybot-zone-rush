# Zone Rush: consolidated release

`bot.py` is the standalone submission: one file, standard library only, with
`act(state)` as its entry point. It contains the selected economic planner,
public-history tracking, corrected Shield inference, territory escape decisions,
input normalization and failed-job guards. No repository modules, data files,
private referee state or future actions are required by the bot.

## Play

```powershell
python simulator/server.py
```

Open http://127.0.0.1:8778/. Use arrows/WASD, Space to stay and Q to Shield,
or the on-screen controls. Recording is automatic. The AI view shows the same
public inputs as the bot. [Simulator details](simulator/README.md).

New matches use the clarified Shield rule: movement resolves first; eligible
rivals anywhere on the shielder's land are caught, including arrivals and moves
between that owner's cells. Already-frozen rivals are excluded. A freeze forces
the next two game turns. Historical recordings retain their actual rule flags.

## Selection and limits

Ten branches and the open v9 research PR were reviewed. The comparison screened
69 distinct standalone policies, tested three corrected/guarded variants, then
compared 15 candidates with balanced corners and priority tokens. A separate
frozen confirmation compared six finalists on eight distinct unused boards and
three contrasting opponent lineups. **5,052 games and 1,616,640 timed callbacks**
are recorded. The development and final rounds had zero worker faults.

| Frozen final comparison, 384 games each | Mean opponents outscored / 3 |
|---|---:|
| **Selected guarded, rule-corrected Transfer** | **1.8750** |
| Previous Transfer release | 1.8516 |
| Original Transfer | 1.7474 |
| Corrected Transfer with legacy pricing | 1.7279 |
| Repaired evolved research policy | 1.5391 |
| Previous main-branch fusion | 1.5247 |

Tied scores contribute half a result. These are matched local comparisons, not
a competition win rate. The selected bot's +0.3503 over the former main export
has eight-map clustered 95% bootstrap interval [+0.0547, +0.6641]. Its +0.0234
over the closest older release has interval [-0.0495, +0.0964], so that smaller
strength difference is inconclusive. It was selected for its leading measured
result, verified rule correctness and robust public interface. Finite tests do
not prove optimal play against every possible opponent.

[Validation and decisions](validation/REPORT.md),
[branch/codebase review](validation/review/BRANCH_REVIEW.md),
[exact release fingerprints](release_manifest.json).

## Test

Python 3.10 or newer is sufficient for the bot, simulator and Python checks.

```powershell
python tools/check_release.py
```

This runs rules/oracle, inference, public-input, real-worker, recording, privacy,
concurrency, downloaded-folder and recorded-evidence tests. If Node is installed,
it also runs the six offline interface logic groups. Visual testing is optional;
the release is validated through automated tests and actual isolated matches.

For an optional repeat of the frozen comparison:

```powershell
python tools/unpack_sources.py
python tools/benchmark.py --spec validation/final_spec.json --out .cache/repeat.json.gz --workers 8
```

Source restoration verifies every archived hash and never replaces changed files.
Use a new output name for every run. Previous results are never overwritten.

## Compact layout

- `bot.py`: the final, already flattened submission; no build step.
- `tester_bots/`: six strong alternative or specialist policies, each standalone.
- `simulator/`: human controls, public AI view, immutable bot snapshots and history.
- `tests/`: runtime regressions and an independently implemented rules oracle.
- `tools/`: release checks and reproducible comparison helpers.
- `validation/`: registered fixtures, compressed full action/results evidence,
  exact source archive and the audit findings.

Retired trainers, duplicate simulators, parameter trees, result dumps and
experimental import graphs remain in Git history at `d385e00` and the recorded
branch commits. Their useful findings were reviewed; their incompatible
historical strength claims were not pooled into this release. The original
working checkout and any live match were left untouched.
