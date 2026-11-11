# Zone Rush: submission and lab

`bot.py` is the submission for StrategyBot Zone Rush (AFKAR 2026): one
standard-library file exposing `act(state)`. It is the lab candidate `zr6`
(`lab/cand/zr6.py`, byte for byte, SHA-256 `8b87bf82…44cb`).

It has been tested on 3,520 games against opponents it was never developed on, across
two separate sets, and led every reference bot on both. It has not yet played on the
organisers' server.

## How it plays

- **Tracker.** From the public board alone it keeps the turn number, every score, and
  each rival's capture progress and Shield cooldown (scores and turn exact, progress
  99.99%, cooldowns 99.9% against the referee's hidden counters).
- **Planner.** A search over sequences of claims, upgrades and raids, with land
  discounted by the chance of losing it. It takes three-point cells early.
- **Rival model.** Per rival, how it uses Shield and how readily it raids, learned
  from every stand-off anyone has with it.
- **Tactics.** Shields on expected points, sometimes a stay early. When raiding an
  upgraded cell it expects the owner to shield at the last moment, steps onto a
  neighbouring cell of the same owner so the shield hits nobody, and takes that cell
  while the owner is frozen and its shield is recharging. Switching this off costs
  0.35 rivals outscored per game ([study](lab/zr6_hybrid_20261111/README.md)).

## Play against it

```powershell
python simulator/server.py
```

Open http://127.0.0.1:8779/. Three copies of `bot.py` play against you; tester bots
can be chosen instead. Arrows or WASD move, Space stays, Q shields. Games are
recorded automatically, and the AI view shows exactly the four inputs a bot gets.
[Simulator details](simulator/README.md). Python 3.10 or newer.

## Does it fit the server's rules?

Checked sentence by sentence against the organisers' starter repository
(<https://github.com/RedPokerJoker123/StrategyBot>): [`lab/RULES_AUDIT.md`](lab/RULES_AUDIT.md).

- Standard library only, one file, `act(state)` unchanged, `state` never modified,
  answer always taken from `legal_actions`.
- Worst call 7 ms against the 200 ms limit; first call 4 ms against 2 s.
- No syntax newer than Python 3.5; runs clean under 3.11, 3.12 and 3.13.
- Where the README is silent or the server might differ, the bot was played under
  the other reading: 34 variations (board and action formats, seats in other corners,
  every action always listed, homes not upgradable, Shield catching by presence, not
  being called while frozen, other game lengths, module reuse). Zero illegal or
  wasted actions in all of them.

```powershell
python lab/robust.py bot.py
python tools/check_release.py
```

The release check runs 142 Python tests and, with Node installed, six interface
groups.

### The Shield rule the bot relies on

Moves resolve first. Shield catches eligible rivals whose **effective action is
STAY** on the shielder's land. A successful move escapes, even between two cells of
the same owner. A blocked or lost-contest move counts as STAY. Using Shield is not a
STAY. Caught or backfired on turn 10 means frozen on turns 11 and 12; Shield used on
turn 10 is next available on turn 15. This matches the official README's wording
("each eligible rival staying on your territory"). If a server catches by presence
instead, the bot notices the first time a mover is caught and stops side-stepping.

## Evidence

Score is rivals outscored per game, 0 to 3. In both tests the candidate was frozen
and the plan committed before any game was played, every bot played identical
fixtures, and the maps were new: 13 map types, 7 of them never used in development,
each map played from all four seats.

**First test** ([plan](lab/PREREGISTRATION.md), 10,240 games, zero faults):

| 1,344 pooled games | Score | `zr6` minus it (95% interval) |
|---|---:|---|
| **`bot.py` (`zr6`)** | **2.575** | |
| Previous release | 2.313 | +0.262 [+0.20, +0.33] |
| Racer | 2.478 | +0.097 [+0.04, +0.16] |
| Blocker | 2.472 | +0.102 [+0.04, +0.16] |

**Second test**, on opponents kept aside from the first
([plan](lab/PREREGISTRATION2.md), 8,832 games, zero faults):

| 960 pooled games | Score | `zr6` minus it (95% interval) |
|---|---:|---|
| **`bot.py` (`zr6`)** | **2.709** | |
| Later candidate `zr8` | 2.676 | +0.034 [-0.02, +0.09] |
| Previous release | 2.386 | +0.323 [+0.26, +0.39] |
| Racer | 2.529 | +0.181 [+0.12, +0.24] |
| Blocker | 2.510 | +0.199 [+0.14, +0.26] |

The lead is the same on map types the bot was never developed on (+0.27 and +0.32
over the previous release) as on familiar ones (+0.25 and +0.33).

### What the tests do not show

- **A lead against strong bots.** Against the strong unseen designs `zr6` is level
  with Racer and Blocker in the first test and 0.07 to 0.09 ahead in the second,
  neither established. Its margin is made against weak and mid-strength opponents.
- **Near-uniform maps.** In the first test it trailed Racer and Blocker slightly on
  flat, rich and edge-heavy maps (84 games per type, not established).
- **The real server.** Everything here ran on this repository's referee.

### The candidate that was not shipped

`zr8` (`lab/cand/zr8.py`) upgrades land before leaving it. In development it looked
0.37 better against strong bots. On the second test it showed no lead against the
unseen strong designs and was 0.16 worse against generated bots, failed three of its
six conditions, and was not shipped. Its lead had been fitted to the strong bots
already in this repository.

Measured afterwards on every opponent group (all of them seen by then): `zr8` is 0.25
to 0.45 better against two of three strong groups, level against the third, 0.05 to
0.15 worse against bots that do not raid, and level on the mixed population. Bots
that play `zr6` first and turn cautious later are the same trade, weaker. Choosing
`zr8` is a bet that other teams' strong bots raid un-upgraded land; `zr6` is the one
that held up twice. [Log, sections 11 to 19](lab/PROGRESS.md).

No untouched opponents are left. A later candidate needs new bots from outside this
project before it can be tested the same way.

## Repository map

- `bot.py`: the submission; no build step, no data files.
- `lab/`: harness, opponent pools, candidates, results and the running log.
  Start with `lab/PROGRESS.md`; rules in `lab/RULES_AUDIT.md`.
- `tester_bots/`: standalone alternatives, including the release before `zr6`
  (`guarded_transfer.py`).
- `simulator/`: the human simulator with bot snapshots and saved history.
- `tests/`, `tools/`: release checks, an independent reference engine, replay helpers.
  `tests/test_root_bot.py` holds the submission's own contracts.
- `validation/`: evidence for the release before `zr6`; not pooled with the lab's.
- `evolution/`, `*_campaign/`, `intent_*`, `gpu_*` and similar folders: earlier
  research, kept unchanged.
- `ultimate.py`: an earlier experimental engine, kept as a tester.
