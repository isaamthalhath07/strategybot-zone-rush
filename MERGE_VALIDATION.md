# PR #11 integration validation

This merges `main` at `641b9ac` into the PR at `9df9497` without incorporating
uncommitted changes from the user's original working directory.

## Conflict decisions

- Keep main's fused `bot.py` and default fusion build, including its stuck-job
  and arbitrary-corner safeguards. Rebuild the standalone export from the merged
  planner sources. The economic primary and fusion controller are unchanged.
- Preserve the PR's completion-income, route-progress and observed-home fixes
  alongside main's final-turn Shield opportunity-cost comparison.
- Keep both ranking APIs: `round_number`/knockout ranks and `round2` compatibility.
  All engine code outside ranking remains unchanged from both parents.
- Preserve the PR's v8 policy and original engine as exact frozen sources under
  `baselines/`. Research imports and replay checks identify those sources
  explicitly. Historical registrations, results, measured exports and saved
  replay data are not rewritten or attributed to the new root export.
- Keep the human simulator's separate presence-based Shield model and selected
  release. Its export and vendored referee remain byte-identical to the PR head.

## Checks on the merged tree

- Human arena: 125 tests; browser logic: six groups.
- Shared harness: 62 tests, one intentionally skipped. Windows discovery fixtures
  now create genuinely byte-identical duplicate files; production source hashing
  is unchanged.
- Engine: 70 checks. Planner: 13 tests, including actual-game comparisons of
  final-turn productive STAY against Shield. Tracker: 3,200 turns, with exact
  positions, progress, scores, freezes and token; cooldown ambiguity stays within
  its documented tolerance.
- Research and historical replay integration: 43 tests; rebuilt forward export
  agrees on 640 public actions across eight games.
- Three retained-safeguard regressions cover failed-home escape, all 24 seat/corner
  assignments and resetting a reused module on a different starting assignment.
- Competition export acceptance: all checks pass, including all 11 interface
  variants, fallback isolation, module reuse, cooldown gates and direction
  calibration. Live-clock maximum was 17.2 ms over 24 games.
- Four economic/fusion export comparisons: 1,920 identical turns each.

These are integration and behavior checks, not a new playing-strength study.
Historical source-locked final validators still reject changed source trees;
use commit `9df9497` to reproduce their original reports. Current-code forward
exports must be built separately and need fresh registered data before any new
strength claim.
