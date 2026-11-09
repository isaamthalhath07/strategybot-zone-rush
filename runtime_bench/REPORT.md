# Runtime experiment: keep CPython for the unchanged harness

The tested portable PyPy interpreter was approximately half as fast as CPython
on the actual current policy and unchanged game runner. Switching interpreters
does not improve this workload. No campaign backend was changed.

| Runtime | Workers | Timed games | Games/s | PyPy / CPython |
|---|---:|---:|---:|---:|
| CPython 3.12.10 | 1 | 128 | 4.972 | — |
| PyPy 8.0.1 / Python 3.11.17 | 1 | 128 | 2.582 | 0.519 |
| CPython 3.12.10 | 2 | 32 | 9.083 | — |
| PyPy 8.0.1 / Python 3.11.17 | 2 | 32 | 4.667 | 0.514 |

The one-worker conditions used 24 warm-up games. The two-worker conditions used
eight warm-up games per worker and a barrier before measurement. Comparisons
within each worker count use identical fixture lists and the identical benchmark
helper. The one-worker condition repeated two blocks of 64 games; PyPy's second
block was slightly slower, so these data do not show a developing warm-up benefit.

All 320 timed repetitions matched their already-recorded four-player actions on
every one of 80 turns, scores, legal actions and opponent identities: 25,600
four-action vectors and 102,400 callbacks. Warm-ups also checked equivalence.
The unchanged runner enforced public-input copies, timing limits, no hidden
fallbacks and referee-only memory/cooldown checks. Every player receives a fresh
namespace per game, as in the primary evaluator. These are finite equivalence
checks, not a guarantee for every future game or interpreter platform.

The experiments ran under concurrent system load. They used at most two extra
workers. One-worker process CPU time was close to measured game wall time:
25.22 CPU seconds for CPython versus 48.27 for PyPy. The slowdown therefore was
not simply time waiting for other processes in that measurement. Different OS,
PyPy versions, warm-up lengths or harness designs require new measurements.

## Profile and the next falsifiable experiment

Normal, uninstrumented CPython callback time totaled 8.63 of 25.75 timed seconds,
about 34%. The remaining time includes view copying, validation, namespace setup,
reference physics and score replay. A separate instrumented profile identified
generic `copy.deepcopy` as a major cost: one game made 356,610 recursive deepcopy
calls. Profiling overhead magnifies such call-heavy functions, so instrumented
seconds are not a direct estimate of production percentages.

In a separate 1,000-copy microbenchmark, generic deepcopy took 0.365 seconds and
an explicit clone of the six public Cell fields and four public View fields took
0.0117 seconds. The copies had equal public values and independent mutable cells
and action lists. This structural clone was **never substituted into the actual
runner** during the interpreter experiment. A subsequent, separately versioned
[structural-copy experiment](STRUCTURAL_COPY_REPORT.md) measured game-generation
improvements while preserving the original runner and live campaign.

For comparison, 50 real append/flush/fsync operations took 0.0464 seconds, about
0.93 ms per record; serialization and hashing were smaller. This small sample
does not support removing durability checks as the first optimization.

The next candidate optimization is a separately versioned public-view clone
implementation. It must preserve independent observations, input-mutation
detection, all four pre-action views and the independent referee audit. First
compare complete action histories, scores and memory oracles against the frozen
runner, then measure end-to-end throughput. The frozen primary source files and
existing campaign registrations must retain their original hashes; any migration
needs explicit review and runtime metadata. No whole-game gain is claimed here.

## Runtime provenance and reproduction

PyPy was absent from PATH and checked local installation locations. A standalone
official Windows ZIP was downloaded only into `.cache/runtime_bench`, verified
against the independently fetched official checksum page, then extracted and
executed. No global interpreter, PATH, Python environment or package was changed.
The release and download are documented by the [PyPy release notes](https://doc.pypy.org/release-v8.0.1.html)
and [official download page](https://pypy.org/download.html); the archive hash is
published on the [official checksum page](https://pypy.org/checksums).

Archive SHA-256:
`cba5f9e9543c679ea5d31b6c81b7a6667d836e3c18bf3eb6cb8c72147f829896`.
The executable hash, full interpreter version, platform, source guards, task IDs,
helper hash and individual game metrics are retained in `evidence/`. The source
stage is the accepted first 20,000-game primary generation; the experiment binds
its registration, game transcript and audit hashes without modifying them.

The first PyPy attempt completed its game comparisons but failed while collecting
metadata because PyPy has no CPython `gc.get_threshold` function. That attempt has
no performance result and is excluded. The metadata fallback was fixed in this
new benchmark folder, and both interpreters were rerun with the same helper.

Reproduce from the repository root, using a fresh output folder:

```powershell
python -m runtime_bench.fetch_pypy
python -m runtime_bench.pilot --stage .cache/primary/campaign_v1_20261109/train_000 --out .cache/runtime_bench/new_cpython --tasks 64 --warmup 24 --repeats 2
& '.cache/runtime_bench/portable_pypy/pypy3.11-v8.0.1-win64/pypy3.exe' -m runtime_bench.pilot --stage .cache/primary/campaign_v1_20261109/train_000 --out .cache/runtime_bench/new_pypy --tasks 64 --warmup 24 --repeats 2
python -m unittest runtime_bench.test_pilot -v
```

The final submission remains unchanged and valid for CPython's 200 ms deadline.
This experiment admits **zero primary games, zero BMCTS audits and no additional
strength evidence**.
