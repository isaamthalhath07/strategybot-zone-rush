# Independent rules and interface audit

Audited 2026-11-07. Sources: local `StrategyBot_RuleBook.pdf` (9 pages), official [starter README](https://github.com/RedPokerJoker123/StrategyBot/blob/main/README.md), and [starter bot](https://github.com/RedPokerJoker123/StrategyBot/blob/main/bot.py). Official README content SHA: `851cfa673f2f7856457aa5867ab79af098179769`; starter bot content SHA: `a67deb6112d9e0377458389b72c262cbc0c7ca69`. Pages 4, 5, 6, and 8 were rendered and visually inspected as well as extracted.

## Definite defect in the initial local harness

`engine.Game.places()` ranked equal scores by end-game cell counts. PDF page 6, section 3.2 explicitly defines Round 1 equal final scores as a draw. The cell-count tiebreak belongs to Round 2 only (page 8, section 5.3). `arena.py`, `measure.py`, and `h2h.py` all derive pairwise outcomes from `places()`, so this changes their Round 1 outcome in tied-score games.

Reproduction before correction: set scores `[100,100,0,0]` and ownership counts `[2,1,1,1]`. Initial `places()` returned `[1,2,3.5,3.5]`; Round 1 requires `[1.5,1.5,3.5,3.5]`. Preserve an explicit Round 2 cell-count ranking option rather than applying the tiebreak to Round 1.

## Interface and allowed computation

- One file named `bot.py`, standard library imports only, unchanged `act(state)` signature; output exactly one of the actions in `state.legal_actions` (PDF page 5 section 2.8, official starter rules).
- Current shipped bot imports only `time` and `collections.deque`, has signature `act(state)`, and reads only documented board/cell fields, bot ID, token Boolean, and legal actions. No filesystem, networking, engine imports, reflection into referee state, or other-team code access was found in the submission.
- Official starter forbids modifying supplied input. A fresh-game runtime check found neither board/cell nor legal-action mutation. Wider game tests should retain this check.
- Globals are expressly allowed during the 80 turns and reset by the server for a new game. Inferring scores, turns, progress, and cooldowns from public history is within this interface. Inferred quantities are beliefs and must defer to observed state when ambiguous.
- The interface is an 8x8 row-major list of Cell objects. NORTH subtracts one row. STAY is always legal, and a frozen bot can only STAY.
- Per-turn limit is 200 ms, first turn 2 s. Crash, late result, or illegal action becomes STAY. Testing with deadlines disabled measures policy strength only; separate shipping tests must use real timing guards.

## Rule checklist

| Topic | Required behavior | Source |
|---|---|---|
| Setup | Four bots, 8x8 mirrored map, values 1-3, one owned uncapturable home each; other cells neutral; 80 turns | PDF pp2-3, 2.1 |
| Order | Simultaneous choices; movement/shields, then capture/upgrade/freeze, then income, then next token seat | PDF p3, 2.2 |
| Occupancy | Initially occupied cells closed even if occupant leaves; no swaps | PDF p3, 2.3 |
| Contest | Moving owner wins; otherwise earliest moving bot in cyclic token seat order wins; losers stay | PDF p3, 2.3 |
| Blocked movement | Counts as STAY, so can cause capture/upgrade | PDF p3, 2.3; official starter game rule 4 |
| Capture | Arrival gives no progress; 1 stay for neutral or rival level 1, 3 for rival level 2; never rival homes | PDF p4, 2.4 |
| Raid | One-time 8 * base value * previous level; captured cell becomes level 1 | PDF p4, 2.4-2.5 |
| Upgrade | 3 stays on own level-1 cell; doubles income; own homes are not excluded | PDF p4, 2.5; starter game rule 7 |
| Reset | Moving, shielding, or being frozen zeroes progress | PDF p4, 2.4, 2.6 |
| Shield | Protects all own cells; catches eligible rivals staying on own land including home; resets them and freezes next 2 turns | PDF p4, 2.6 |
| Backfire | No eligible caught rival freezes shielder for 2 turns; already-frozen rivals ineligible | PDF p4, 2.6 |
| Cooldown | Cannot shield next 4 turns after shield; shield action gives no work progress | PDF p4, 2.6 |
| Income | Score every owned cell after updates, doubled if upgraded, including newly acquired/finished work this turn | PDF p3 order and p5, 2.7 |
| Round 1 | Pairwise final-score comparisons, ties draw | PDF p6, 3.2 |
| Round 2 | Score, then final cells, then shared pool places or Round 1 rank for knockout ties | PDF p8, 5.3 |

## Remaining assumptions and cautions

1. The local README says organisers directly confirmed frozen forced STAY gives no work progress. Neither PDF nor current public README states this answer explicitly. The default local engine follows that reported clarification; the audit cannot independently authenticate the private answer. The rulebook states freeze resets progress, and official server is authoritative.
2. Capture resets progress is the natural reading of the separate capture and own-cell upgrade requirements, and current public README matches that reading. It is not given as an explicit counter-reset sentence. Runtime rule detection is permissible but does not establish server equivalence by itself.
3. `CANON[seat]` originally assumed the clockwise seat-to-corner order `(0,7,63,56)`. Neither public starter nor PDF explicitly fixes that assignment. Tracker already reads actual homes; geometric tie-breaking should also use the actual observed home, or be tested across seat permutations. This is a performance assumption, not an exploit.
4. Only README and skeleton `bot.py` are published in the official starter repository. No official reference engine or visual arena URL was present there. A locally reimplemented visual harness is evidence about the local model; identify it as such and do not imply it is the official referee.
5. Four-fold mirrored maps with integer values 1-3 are guaranteed. The local random map distribution and canonical 28-income quadrant are local test choices, not a probability distribution promised by the official rules. Stress flat/edge-heavy/centre-heavy mirrored maps as well.

## Fair play

PDF page 6 section 3.4 expressly permits the skeleton, public documentation, and AI coding assistants. It forbids code sharing between teams, collusion, game-bug exploitation, interference with game or opponent code, and entering multiple bots. Page 9 provides disqualification penalties. Public-history inference, ordinary legal raids, baiting shields, and optimizing the one submitted bot are ordinary game strategy. The current submission showed no forbidden information channel. This audit cannot certify private provenance or predict an organiser's ruling on a future discovered exploit; discovered server bugs must be reported rather than exploited.

## Scope of confidence

The checklist supports concrete compliance claims; it does not prove the local engine is the official server or the policy is optimal. Unknown opponent policies and finite testing preclude a truthful claim of perfection. Compare independently designed opponents, preserve held-out tests, report paired uncertainty, and judge the shipped file with its actual time budget enabled.
