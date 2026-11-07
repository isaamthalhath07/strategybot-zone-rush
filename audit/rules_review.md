# Rules review and corrections

The detailed source checklist and fair-play review are in [rules_audit.md](rules_audit.md). The official [starter README](https://github.com/RedPokerJoker123/StrategyBot/blob/main/README.md) and skeleton were fetched directly through the GitHub connector on 2026-11-07; their content hashes are recorded in that report. PDF pages 4, 5, 6, and 8 were rendered and visually checked.

## Ranking correction implemented

`engine.Game.places(round_number=1, round1_ranks=None)` now defaults to Round 1: equal final scores share a place even if final cell counts differ (PDF page 6, section 3.2). Existing tournament, paired measurement, and head-to-head calls use this correct default without changing their call sites.

`round_number=2` applies score then final cells (PDF page 8, section 5.3). Omitting `round1_ranks` implements Pool Stage shared places. Supplying four lower-is-better Round 1 ranks implements the final Semi-final/Grand Final tiebreak. Round 1 ranks never override a score or cell-count advantage. This helper ranks one game; it does not implement the separate pool-standings tiebreak chain in section 5.4.

Regression coverage includes the rulebook's page-9 412/380/380/201 example with unequal and equal cell counts; equal-score pairwise draws; shared pool points; four-way shared ties; knockout ranking; and invalid format rejection. `test_engine.py` also now exits nonzero on any failed check so automated verification cannot accept a printed failure as a passing process.

Validation: `python -X utf8 test_engine.py` reported 63 passed, all checks pass. This includes the existing 400 randomized invariant games. Correcting the ranking changes interpretation of rare tied-score games and makes old results numerically nonidentical to measurements with the corrected code.

## Submission boundary review

The shipped file exposes `act(state)`, imports only `time` and `collections.deque`, and parses only documented public fields. No engine import, filesystem/network access, referee-state access, or external communication was found in that file. Tracker estimates use board history; keeping such globals is explicitly permitted by the current official README. The bot copies board attributes into local arrays instead of mutating the supplied board.

`audit/test_input_contract.py` adds a direct shipped-file check using public-interface-only views for four complete games, canonical and extreme flat maps, four seats sharing a module, actual shipping timing guards, and input snapshots before/after every action. It asserts legal output, no state or legal-action mutation, and the 200ms/first-turn-2s execution limits.

The check passed all 1,280 calls with no mutation or illegal/late output. Worst observed call in this run was 14.033ms; this is local machine evidence, not a guarantee about slower grading hardware.

## Remaining limits

- An observed-home rather than assumed-seat geometric frame is advisable; the official public material does not fix the clockwise seat/corner assignment.
- The public starter currently publishes only README and skeleton, not an official referee implementation. A local visual harness demonstrates the local model. It should be labeled accordingly.
- The private organiser answer about frozen forced STAY giving no work progress is reported in the local README but not independently verifiable from the public sources reviewed.
- `gpuenv.py` belongs to the rejected RL track and has a separate legacy ranking implementation applying cells. It was outside this correction's scope and should not supply fresh Round 1 ranking evidence until fixed separately.
- No game-policy exploit or prohibited information channel was found. This is a concrete boundary review, not proof of global strategic optimality or a guarantee about unknown opponent policies.
