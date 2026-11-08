# Focused simulator review

The new `simulator/` retains the tested human-game engine, history recorder,
on-screen/keyboard controls and Standard/AI views, while removing Git branch
selection and research-directory dependencies. It runs from a downloaded folder
with Python 3.10+ and no third-party package or account. The default new port is
8778; the existing 8775 server and its current game were never touched.

## Source and rule integrity

The active root `bot.py` is the default. Only named `tester_bots/*.py` files are
also selectable. Final `release_manifest.json` uses format
`zone-rush-consolidated-release/1`, `bot_sha256`, a `tester_bots` array of
`path`/`label`/`sha256` objects, and a `recommendation` string. A changed release
cannot silently inherit the recorded recommendation. Each started match resolves
to a hash-named immutable source snapshot, independent of later file edits.

All four bundled vendor Python files and their provenance JSON retain the exact
original bytes. Bootstrap verifies them and temporarily scopes their original
absolute imports rather than contaminating other tools' module aliases. Their
unused Git source helper stays bundled only to preserve the pinned harness;
the application never constructs its repository class or calls Git.

New human matches explicitly select `catch_requires_stay=False`. Movement
resolves first; an eligible rival anywhere on the shielder's land is caught,
including arrivals and moves between cells of that owner. Existing frozen
players remain ineligible. Mutual shields remain active, productive progress
resets, freezes force the next two game turns, and cooldown is separate. Old
histories keep their actual complete rule flags and hashes.

## Input, failure and recording contract

Each bot receives an independent pre-action copy of exactly four fields: board,
seat, priority flag and legal actions. Neither pending human action nor private
counter/referee data reaches the callback. Each seat has a separate worker and
module memory; regular turns enforce 200 ms and opening turns 2,000 ms. A failed
seat becomes STAY without re-running the other accepted callbacks. Illegal,
stale and concurrent duplicate human requests cannot advance twice.

Accepted turns are fsynced before their response is produced. Damaged records
are rejected or skipped without breaking the saved-match list; recording errors
pause further turns. AI view retains only the four-field observation envelope
and hides observer history, counters and results. The local observer's download
is deliberately richer than a playing bot's callback.

## Verification

71 Python regressions pass, covering the real worker interface and cleanup,
deadline fallbacks, strict views, request concurrency, full 80-turn replay,
recording durability/corruption, Shield geometry and exact source pinning. One
integration test copies the package into a folder without Git, forbids command
runner dependencies and completes/records an isolated 80-turn match with zero
bot faults. The separately preserved independent engine is tested against the
vendored referee on 24 randomized complete games under the clarified rule;
public observations, effective actions and every private physical counter agree.
The oracle remains exact source from main d385e00, with its own provenance.
Six offline browser logic groups also pass, including keyboard
activation, delayed history/download privacy and freeze/thaw controls.

The final manifest is pinned and the selected bot also completed an automated
80-turn recorded human-play pipeline test with three real workers and no faults.
At the user's request, visual-harness testing is optional. No game was submitted
to the user's existing live server during this packaging work.
