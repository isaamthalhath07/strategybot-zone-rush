# Progress log

Running record of what was done, what was found and what it means. Newest entries
at the bottom. Every number here is reproducible from files in this repository.

Score used throughout: **rivals outscored per game, 0 to 3** (ties count half).
1.5 is break-even among equals.

---

## 1. Every bot in the repository's history, ranked (2026-11-10)

Files: `lab/history_ranking/` (`RANKING.md` is the readable report,
`full_ranking.csv` the full table, the `.py` files are the scripts).

- 595 distinct playable `act(state)` files recovered from all 60 commits on all 13
  branches, including 470 found only inside source archives committed in history.
- 35,616 games on the pinned referee under the confirmed STAY-only Shield rule, one
  process per seat, 200 ms per turn enforced.
- Result: **Racer** (`tester_bots/racer.py`) 2.36 and **Blocker**
  (`tester_bots/blocker.py`) 2.32 were the best existing bots; the shipped root
  `bot.py` scored 1.99 and placed 19th of 20 finalist files. Racer minus `bot.py` on
  identical games: +0.36, 95% interval [+0.22, +0.52].
- Caveat that matters for everything below: that ranking used four to six fixed
  opponent line-ups on one map generator. Which bot is "best" depends on the field.

## 2. Review of commit 5031014 (lab harness and candidate `zr4`)

What the commit contains: an in-process harness (`lab/sim.py`), a 123-bot opponent
pool with a development / hold-out split (`lab/fields.py`), and a new candidate bot
in `lab/cand/` (`zr4` = `_head.py` + `_tail2.py`). Its hold-out was never run.

Reproduced its development numbers exactly (`python3 lab/suite.py --ref cur_e8
a_novel_b_racer a_novel_b_blocker zr3 zr4`, 2,850 games):

| Focal bot | elite | mid | weak | mix | self |
|---|---:|---:|---:|---:|---:|
| current `bot.py` (`cur_e8`) | 1.82 | 2.27 | 2.58 | 2.24 | 1.48 |
| Racer | 1.77 | 2.18 | 2.85 | 2.33 | 1.41 |
| Blocker | 1.81 | 2.27 | 2.85 | 2.31 | 1.58 |
| `zr3` | 2.30 | 2.48 | 2.81 | 2.59 | 1.78 |
| **`zr4`** | **2.37** | **2.53** | **2.83** | **2.56** | **1.84** |

`zr4` minus `cur_e8`: elite +0.55 [+0.39, +0.70], mid +0.26 [+0.05, +0.47],
weak +0.25 [+0.15, +0.35], mix +0.32 [+0.19, +0.46], self +0.35 [+0.07, +0.61].

Head to head on 600 development games (`lab/h2h.py`): `zr4` outscores every
development opponent more often than not; its closest matchups are UltimateBot
(0.54), research_correctness (0.58) and Blocker (0.60).

Timing in isolated worker processes (24 games): mean 1.4 ms per call, worst
9.9 ms, no faults. The limit is 200 ms.

### Findings from the review

1. **These are all in-sample numbers.** `zr4` was designed against the development
   fields, so its lead there says nothing yet about overfitting.
2. **The lab hold-out is not independent of development.** `HOLDOUT_ELITE` contains
   Feint (same code base as Racer and Blocker, which are development bots) and
   `v2_bot_191059b37141` (byte-for-byte Blocker with one seat reseeded). A pass on
   that split alone would be weak evidence.
3. **Racer and Blocker do not dominate in the lab's fields.** In section 1 they beat
   `cur_e8` by 0.3; on the lab's development elite field they are level with it.
   Different maps and opponents, different order. This is the reason the final test
   below spans several unrelated opponent sets and map families.
4. **492 bots in the repository's history were never in the lab pool**, so the
   candidate has never met them. They include the 20 bots pasted from ChatGPT and
   Gemini, 12 procedurally generated opponent families the pool has no member of,
   the six "human-like" exploiters and Zenith from the Apex work, and independent
   challengers written from the rulebook. These form the external test.
5. **Engineering gaps in `zr4`** to close before it can ship: one module-level
   memory shared by all seats (breaks if a server runs two seats in one process),
   it returns plain strings even if the server hands it action objects, and its
   fallback on an internal error is STAY rather than a working policy.

## 3. Protocol for the rest of the work

The requirement is the best bot that does **not** overfit, in a field where every
other team also used AI. So:

- **Development set** (already used): `fields.DEV_*`. All design and tuning
  decisions use only this.
- **Test sets** (not touched until the candidate is frozen and the plan is
  committed): the lab hold-out, plus the external bots from finding 4, split once
  by seeded shuffle into a test half and an untouched reserve half.
- Test games use fresh maps, map families never used in development, all four
  seats and token starts, and the referee's alternative rule readings.
- The candidate, the current `bot.py`, Racer and Blocker all play the identical
  fixtures, so differences are paired.
- The shipping rule is written down and committed before the test is run.

## 4. Hardened candidate `zr5` (same decisions, safe to deploy)

`zr5` = `zr4` plus deployment fixes only. On the documented interface it is
**move-for-move identical** to `zr4`: 160 games, 12,800 decisions, zero differences
(`python3 lab/equiv.py zr4 zr5 --maps 40`).

What changed:

- one memory per seat instead of one per module, so a server that runs several seats
  in one process cannot mix their histories;
- it answers with the server's own action object (lower-case strings, Enum members)
  instead of always returning an upper-case string;
- cells may be bare 6-tuples; homes the server reports as unowned are attributed
  to their seat;
- an internal error no longer returns STAY: that seat's memory is dropped and
  rebuilt from the board, and a stateless greedy policy plays the turn;
- a turn that runs longer than 60 ms narrows every later search (never triggered in
  testing: mean 1.4 ms, worst 9.9 ms).

Robustness matrix (`python3 lab/robust.py zr5 zr4 cur_e8 a_novel_b_racer`, saved
in `lab/results/robust.txt`): 22 input or rule variations and 4 deployment modes,
four full games each.

| Bot | Conditions passed (of 26) | Fails on |
|---|---:|---|
| **`zr5`** | **26** | none |
| `zr4` | 21 | lower-case actions, Enum actions, bare-tuple cells, homes unowned, one module for four seats |
| current `bot.py` | 25 | bare-tuple cells |
| Racer | 16 | flat boards, dict cells, string `bot_id`, lower-case and Enum actions, missing token flag, dict state, bare tuples, **second game in the same module** |

Finding: **Racer cannot be shipped as it is.** It plays a second game in the same
process with the first game's memory and collapses, and it breaks on most input
variations. Its strength numbers in section 1 hold only on the exact documented
interface with a fresh process per game.

A development-only sensitivity sweep (`lab/sensitivity.py`) is running; results in
the next entry.
