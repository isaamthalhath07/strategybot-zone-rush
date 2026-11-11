# Does `bot.py` fit the server's rules?

Checked against the organisers' starter repository
(<https://github.com/RedPokerJoker123/StrategyBot>, commit `975b643`, README and
starter `bot.py`). The shipped bot is `zr6`, SHA-256 `8b87bf82…44cb`, unchanged by
this audit.

Three questions, in order: does the bot obey the submission rules, does the engine we
measure on resolve a turn the way the README says, and what happens where the README
leaves something open or the server turns out to differ.

## 1. Submission rules

| README rule | Status | How it is checked |
|---|---|---|
| Standard library only | holds: the file imports `time` and `random`, both lazily | `tests/test_root_bot.py`, first test |
| One file named `bot.py`, `act(state)` signature unchanged | holds | same test |
| Never modify `state` | holds on all 1,280 self-play callbacks | `tests/test_root_bot.py`, second test |
| Return exactly one string from `state.legal_actions` | holds: the answer is taken from the server's own list, and replaced by `STAY` if it somehow is not in it | 0 illegal answers in 10,240 + 8,832 test games and in every row of `lab/robust.py` |
| 2 s for the first call, 200 ms after | load 12 ms, first call 4 ms, later calls median 1.4 ms, worst 7.3 ms over 4,800 calls against the busiest opponents | `python3 lab/timing.py bot.py 60` |
| A crash counts as `STAY` | the bot never lets one reach the server: any exception inside falls back to a small stateless policy for that turn | `tests/test_root_bot.py`, fallback test |
| Memory lives in the bot's own globals; `state` is the truth | every turn starts from `state`; memory only adds what a single board cannot show (turn number, progress, cooldowns) and is rebuilt if it disagrees | tracker graded against the referee's hidden counters, below |

No file access, no printing, no `exec` / `eval`, no network (same test).

Python version: the README does not say which one the Arena runs. The file is plain
ASCII, uses no syntax newer than Python 3.5 (it parses with every `feature_version`
from 3.5 up; no f-strings, no walrus, no annotations) and no standard-library call
newer than that. Self-play under 3.11, 3.12 and 3.13: 0 illegal answers.

Time headroom: a server 27 times slower than the development machine would still get
every answer in time. If one call ever takes more than 60 ms the bot narrows its own
search for the rest of the game.

## 2. Turn resolution, sentence by sentence

Our measurements run on `simulator/vendor_harness/referee.py`. Each line of the
README's "Game Rules" against that referee and against what the bot's tracker assumes:

| # | README | Referee | Bot |
|---|---|---|---|
| 1 | 8 x 8 mirrored board, 80 turns, values 1 to 3 | same | counts its own callbacks for the turn number; reads values from the board |
| 2 | Corners are homes, permanently owned, cannot be captured | same | never plans to take a home; finds homes from `is_home` and from where bots stand on the first board, not from a fixed seat order |
| 3 | Simultaneous actions; order: moves and shields, then captures / upgrades / freezes, then scoring, then the token passes 1 to 2 to 3 to 4 | same order | token cycle reconstructed exactly from its own flag |
| 4 | A cell occupied at the start of the turn cannot be entered; contests go to the cell's owner, else token order; a failed move counts as `STAY` | same (`lost_contest_is_stay`) | never plans through an occupied cell; treats a blocked or lost move as a stay for progress and for being caught |
| 5 | Arriving is not a stay; 1 stay takes a neutral or level-1 cell, 3 stays an upgraded one; a taken cell is level 1 | same | same counts |
| 6 | Raid bonus 8 x base x previous level | same | same |
| 7 | 3 stays on your own level-1 cell upgrade it | same; progress restarts after a claim (`claim_resets_progress`) | plans 1 + 3 stays for claim and upgrade |
| 8 | `SHIELD` protects all your cells, freezes for 2 turns every eligible rival **staying** on your land including your home, backfires if it catches nobody, 4 turns of cooldown; moving, shielding or being frozen resets progress; `SHIELD` is not a stay | same (`catch_requires_stay`); caught on turn t means frozen on t+1 and t+2; cast on turn t means unavailable t+1 to t+4 | same; its side-steps rely on "staying", see section 3 |
| 9 | Income at the end of every turn, doubled if upgraded; equal totals share a place | same | own score book exact |

Tracker accuracy against the referee's hidden state, `python3 lab/check_tracker.py bot.py 120`
(38,400 turns): turn number and scores 100%, rivals' progress 99.99%, rivals' cooldowns
99.88%. The remainder is not on the public board (section 17 of `PROGRESS.md`).

## 3. Where the README is silent or the server might differ

For each, the bot was played under the other reading (`python3 lab/robust.py bot.py`).
"errors" counts answers that were illegal, raised, or were wasted on a wall.

| Open point | Reading the bot was built on | Played under the other reading |
|---|---|---|
| `state.board`: README says 8 x 8 lists, the starter file's docstring says "list of cells" | either | flat list, tuples, named tuples, dicts, bare 6-tuples, everything as strings: identical play, 0 errors |
| Type of `bot_id`, flags and actions | ints, bools, upper-case strings | strings, 0/1, lower case, Enum-like objects, `is_priority_token` missing: identical play, 0 errors |
| Does `legal_actions` list a cooling `SHIELD`? | no | listed anyway: the bot never picks it, 0 errors |
| Does `legal_actions` list walls and occupied cells? | walls no, occupied yes | **all six always listed** (new row), also when frozen (new row), occupied cells left out: 0 errors, never walks into a wall, answers `STAY` when frozen |
| Order of `legal_actions` | any | reversed: identical play |
| Which seat sits in which corner (README: "one per seat") | read from the board | **seats 2 and 4 swapped; every seat in the opposite corner** (new rows): 0 errors, normal scores |
| Can a home cell be upgraded? | yes | no: the bot notices the upgrade did not happen and drops that job for the game; 0 errors |
| Are homes shown as owned? | yes | shown unowned: identical play |
| Does `SHIELD` catch a rival that only stands on your land, or one that stayed? | stayed (the README's word) | catch by presence: the bot sees a mover get caught, stops side-stepping onto the same owner's land; 0 errors, score -2% |
| Does a claim reset progress? Does a frozen turn count as a stay? Is a lost contest a stay? | yes / no / yes (README) | each flipped: 0 errors |
| Is a frozen bot asked for an action at all? (README: "a frozen bot can only STAY", so yes) | asked | **not asked** (new row): 0 errors; the bot's turn count then runs 2 behind per freeze, score -4% |
| Game length | 80 | **60 and 100 turns** (new rows): 0 errors |
| How globals are cleared between games | new module | same module reused for a second game; one module serving all four seats; a fresh module on every single turn; joining at turn 30: 0 errors each |

All 34 rows: zero errors, none degraded past its threshold.

## 4. What this audit cannot show

- The real server has not been played against. If its game record ever disagrees with
  the README, the record wins, and the fix is a new row here first.
- Two things would cost real points and are not in the bot's control: a server so
  slow that answers pass 200 ms (27 times slower than here), and a server that runs
  several games through one copy of the module at the same time under the same seat
  number. The README rules out the second ("cleared when a new game starts").
