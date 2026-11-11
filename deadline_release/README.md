# Portable release packager

This tool packages a caller-selected source; it does not choose the strongest bot.
All changes are confined to this new directory. Existing research, runtime and
simulator files are read only. No Git, CUDA, remote workers or credentials are used.

`build_release(selected_source_path, selected_sha256, tester_entries, output_directory,
selection_note=..., decision_manifest=None, evidence_entries=(), validate=True)`
requires a fresh output folder and exact lowercase SHA-256 pins. Tester entries
have `path`, `sha256`, `label`, and optional safe `filename`. Explicit public text
evidence entries have `path`, `sha256`, and optional `label`. Bodies are copied
unchanged. A decision is `{status: reference_only|final_selection,
selected_source_sha256: ...}` plus caller-supplied public provenance. Final status
requires successful package validation and supplied public evidence; it remains
the caller's decision, not a new empirical claim made by this tool.

The portable folder includes selected `bot.py`, chosen standalone testers, the
existing local simulator/static files, exact vendored worker/referee sources and
their provenance, the independent CPU referee, focused generic tests, validation
evidence, `README.md`, `play.py` and a Windows launcher. Python 3.12 and its standard
library suffice. The Git-capable classes retained in the original vendored
`sources.py` are unused by the simulator's local catalog path.

Default validation runs in Python's isolated/no-site mode and executes no full
policy games. It covers both Shield interpretations, independent physics, local
catalog/source snapshots, public information boundaries, recording and error
handling, plus one opening callback per packaged policy. An explicit separate
`tools/smoke_release.py --games 1` command runs one ordinary human-STAY process
control game with three fresh selected-source workers and three independently
replayed source namespaces. It checks the full tape, timing, faults, public
inputs, supported memory projections and both CPU referees. It is not a strength
test or research admission. No smoke games are launched by the packager.

`verify_release(directory)` only verifies files and manifests, without callbacks.
`include_smoke_evidence(directory)` seals an already completed explicit smoke and
its raw history, preserving the pre-smoke manifest to which the report was bound.
It checks raw identities, all 80 ordered turns, 240 measured actual callbacks,
deadlines and source hashes; it performs no new game or callback.
`make_zip(directory, fresh_archive)` includes only the sealed payload, excluding
later local play history, snapshots and caches. Read-back verification checks
every archived byte. Failures preserve the fresh output and error report; no
automatic retry or overwrite is provided. Source guards run before and after the
build. The selected source is never flattened, rewritten or regenerated.

CLI examples (replace caller-owned inputs):

```powershell
python -m deadline_release.packager build --selected chosen.py --sha256 <64hex> --testers-json testers.json --output portable --note "See saved final decision" --decision-json decision.json --evidence-json evidence.json
python -m deadline_release.packager verify portable
python -m deadline_release.packager seal-smoke portable
python -m deadline_release.packager zip portable portable.zip
python -m unittest deadline_release.test_packager
```

Final branch consolidation/publication is owned by the root agent after the
selection decision. This tool performs no Git mutation. No selected-body strength
evidence is inferred from a successful package build.

On Windows systems without long paths enabled, use a short extracted location
such as `C:\ZoneRush`. Deep nested folders can exceed Windows' path limit when
the simulator creates its SHA-named source snapshots. The original simulator and
test sources are retained unchanged.
