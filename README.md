# Zone Rush: submission and lab

`bot.py` is the standalone submission: one standard-library file exposing
`act(state)`. It uses only the four documented public inputs and its own memory of
earlier public boards. It is the lab candidate `zr6` (`lab/cand/zr6.py`, byte for
byte): an exact public-history tracker, a route planner that discounts land by the
measured chance of losing it, a per-rival model of Shield habits, and Shield and
raid decisions made on expected points.

The previous release is kept as `tester_bots/guarded_transfer.py`.

## Confirmed rule

Moves resolve first. Shield catches eligible rivals whose **effective action
is STAY** on the shielder's land. A successful move escapes, even between two
cells owned by the shielder. A blocked or lost-contest move counts as STAY.
Using Shield is not a STAY. Already-frozen rivals remain ineligible.

Caught or backfired on turn 10 means frozen on turns **11 and 12**. Shield used
on turn 10 is unavailable on **11 to 14**, and can next be used on **15**. Catching
nobody eligible backfires. Other capture, income and work rules are unchanged.

This explicit clarification supersedes the earlier territory-presence
interpretation. Your original turn-34 transcript is correct: Red moved D4 to
C4, escaped Blue's Shield, and Blue backfired. All 34 recorded transitions replay
exactly. Old recordings keep their actual rules, sources and hashes.

## Play and test

```powershell
python simulator/server.py
```

Open http://127.0.0.1:8779/. Arrows/WASD move, Space stays, Q shields;
on-screen controls do the same. Recording is automatic. The AI view shows the
same four public observation fields as the bot. [Simulator details](simulator/README.md).

```powershell
python tools/check_release.py
```

Python 3.10 or newer is sufficient. The release passes **142 Python tests** and,
when Node is installed, six offline interface logic groups. `tests/test_root_bot.py`
holds the root bot's own contracts (legal and timely on the independent reference
engine, input never mutated, exact own score, progress and cooldown books, interface
variations, a working fallback if the planner raises). The tests written against the
previous release's internals now run against `tester_bots/guarded_transfer.py`.

## Why this bot: the out-of-sample test

The candidate was frozen and the test plan committed before any test game was played
([plan](lab/PREREGISTRATION.md), [full log](lab/PROGRESS.md)). It then played
10,240 games against opponents it was never developed on, on fresh maps (half from
map families that did not exist during development), next to the previous release
and the two best existing bots on identical fixtures. Score is rivals outscored per
game, 0 to 3.

| 1,344 pooled games | Score | New bot minus it (95% interval) |
|---|---:|---|
| **New `bot.py` (`zr6`)** | **2.575** | |
| Previous release | 2.313 | +0.262 [+0.20, +0.33] |
| Racer | 2.478 | +0.097 [+0.04, +0.16] |
| Blocker | 2.472 | +0.102 [+0.04, +0.16] |

Zero faults in every test game. All six pre-registered shipping conditions held.

What the test does **not** show: a lead against strong bots. On the two fields of
strong unseen opponents the new bot is level with Racer and Blocker (differences
+0.01 to -0.02, intervals about +/-0.3) and its lead over the previous release
(+0.14 and +0.07) is not established. Its margin is made against weak and
mid-strength opponents. The development figures had suggested +0.55 against strong
bots; that did not carry over, and [the log](lab/PROGRESS.md) explains why. Work on
that gap continues in `lab/`.

## Repository map

- `bot.py`: the submission; no build step, no data files.
- `lab/`: the harness, opponent pools, candidates and the running log this bot came
  from. Start with `lab/PROGRESS.md`.
- `tester_bots/`: nine standalone alternatives, including the previous release.
- `simulator/`: the human simulator with immutable bot snapshots and saved history.
- `tests/`, `tools/`: release checks, an independent reference engine, replay helpers.
- `validation/`: evidence for the previous release (`validation/official/`) and older
  presence-rule evidence. Those scores are not pooled with the lab's.
- `evolution/`, `*_campaign/`, `intent_*`, `gpu_*` and similar folders: earlier
  research, kept unchanged.
- `ultimate.py`: an earlier experimental engine, kept as a tester.
