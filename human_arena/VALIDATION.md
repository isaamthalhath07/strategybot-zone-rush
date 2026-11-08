# Human-play checks

Verified 7 November 2026. This app is local; it is not the official Arena.

- All 14 backend/protocol/worker tests passed using `python -m unittest discover -s human_arena -p 'test_*.py' -v`.
- Checks cover simultaneous public observations, hiding pending choices, duplicate/stale/cross-game rejection, immutable views, Round 1 score ties, frozen human turns, legal actions, AI execution limits, independent processes, and cleanup on replacement or game completion.
- The real browser accepted ArrowRight to move from cell 0 to 1; the Stay button claimed that cell; Q caused a legal shield backfire, four-turn cooldown, and forced-STAY state. A movement key while frozen did not advance the turn; Space advanced the forced stay.
- A real human-seat match completed all 80 turns against three subprocess copies of the recommended evolved AI. There were no recorded AI faults. Final scores were 232, 2427, 2472, 2220; the result display and disabled end-game controls matched the final state. The human deliberately stayed for most of this test; it is not a strength experiment.
- Starting a fresh match reset turn and scores. The live game was left at turn 1 for the user.
- The board rendered all 64 cells and six controls at desktop width and the browser's minimum tested viewport of 501 pixels, without horizontal overflow.
- The picker exposed eight unique policies across six remote branches, grouping identical files by SHA-256 and preserving source commit/path/hash details.

The separate [branch screen](branch_screen.json) used 60 games and 19,200 calls, with no faults, input mutation, or timeouts. Its default research policy led that small panel. Three maps and a limited opponent panel cannot establish a universal champion. The alternative research files in the picker were not all included in the root-submission screen.

## AI-view checks

The separate AI-view server runs on port 8771; the original port-8770 match was
not restarted or acted on during this change.

- All 18 current tests passed, including exact equality between the strict
  observation and the fields received inside a real isolated bot worker.
- Strict state/new/action responses contain only game ID, turn bookkeeping,
  completion status, and the four-field observation. No scores, history,
  progress, cooldown counters, faults, or result totals appear in that payload.
- Live browser checks confirmed 64 visible cells, hidden observer panels,
  cleared score text, exactly four raw-input keys, and no browser-console errors.
- Moving, claiming, and upgrading worked in AI mode. An upgraded base-one cell
  displayed `1` plus a separate `×2` flag, matching the input attributes.
- Standard/AI switching preserved the same game ID and turn. Standard restored
  scores; AI discarded that richer state and restored the exact observation.
- ArrowRight still moved correctly after focusing the AI-view switch. The new
  version was left in AI mode at the start of a fresh match.
- The pre-game board is explicitly marked as a preview with no observation yet.

The display shows current public input, not a policy's private memory. A bot can
retain history and infer quantities that are absent from the current input.
