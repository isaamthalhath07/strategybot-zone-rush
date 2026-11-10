# Zone Rush: adaptive release

`bot.py` is the standalone submission: one standard-library file exposing
`act(state)`. It uses only the four documented public inputs and its own memory
of earlier public boards. It replaces the guarded Transfer planner, which is kept
byte-identical as `tester_bots/previous_release.py`.

## What changed and why

The earlier work tuned one planner's numbers against bots from the same family
and found nothing: after 100,000 campaign games the best variant led by 0.0003.
Measured against a wider field the reason is clear. The strong bots here are
economically identical, and an offline search puts the best possible score from
one quadrant at about 2,780 points, which they already reach. The remaining
edge is in how a bot reads and answers its opponents.

- **Exact tracker.** Turn, all four scores and the priority-token cycle are
  rebuilt exactly from public boards; rival work progress matches the referee on
  99.99% of seat-turns and shield cooldowns on 99.9% (the rest are publicly
  ambiguous).
- **Risk measured, not guessed.** An un-upgraded cell is lost within five turns
  23% of the time with a rival next to it, 4% at distance two and under 1% at
  three or more. The planner values every cell with those survival curves, so it
  claims freely while rivals are far and upgrades what becomes exposed.
- **Opponent model.** For each landlord it keeps a posterior over five shield
  habits (never, on sight, every imminent take, upgraded cells only, one stay
  early), updated from every stand-off anyone has with that landlord.
- **Raids that answer the landlord.** Strong bots shield 95-100% of the time on
  the exact turn a rival would complete a take. Stepping to a neighbouring cell
  on that turn makes the shield catch nobody: the landlord freezes for two turns
  and cannot shield for four. Against a landlord that never shields it simply
  stays; against one that shields on sight it steps aside at once.
- **Defence that cannot be timed.** It shields on expected value, sometimes one
  stay early at random, and stops trusting a raider that has dodged it before.
- **Safety nets.** A crash in the policy falls back to a simple working policy
  instead of idling; a turn slower than 40 ms halves the search; unreadable input
  answers STAY. A normal turn takes about 1 ms against a 200 ms limit.

## Confirmed rule

Moves resolve first. Shield catches eligible rivals whose **effective action
is STAY** on the shielder's land. A successful move escapes, even between two
cells owned by the shielder. A blocked or lost-contest move counts as STAY.
Using Shield is not a STAY. Already-frozen rivals remain ineligible.

Caught or backfired on turn 10 means frozen on turns **11 and 12**. Shield used
on turn 10 is unavailable on **11ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“14**, and can next be used on **15**. Catching
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
same four public observation fields as the bot. Existing older tabs retain
their old matches and rules. [Simulator details](simulator/README.md).

```powershell
python tools/check_release.py
```

Python 3.10 or newer is sufficient. The release passes **142 Python tests** and,
when Node is installed, six offline interface logic groups. These include both
historical and current physics, 48 complete independent-engine differential
games, exact public-history oracles, real-worker recording/replay and privacy,
request races, fallback recovery and a downloaded folder without Git.
Visual-harness testing is optional under the user's instruction.

## Evidence

Every comparison is paired: both bots play the same maps, seats, tokens, opponents
and opponent seeds, and intervals resample whole maps. The opponents are 123 bots
recovered from this repository's own history. Before the new bot was designed, 19
of them were split off at random with a fixed seed and never used until it was
frozen; they were then run once.

Mean rivals outscored out of 3, new bot against the previous release:

| Opponents | Previous | New | Paired difference (95% interval) |
|---|---:|---:|---|
| Development, 12 strongest | 1.80 | 2.25 | +0.45 [+0.26, +0.66] |
| Development, 14 mid-strength | 2.08 | 2.30 | +0.22 [+0.00, +0.44] |
| Development, 18 weak | 2.65 | 2.91 | +0.26 [+0.14, +0.38] |
| Development, all 44 mixed | 2.28 | 2.48 | +0.20 [+0.06, +0.33] |
| Development strong plus copies of the new bot | 1.57 | 1.99 | +0.42 [+0.12, +0.73] |
| **Hold-out, 5 strong** | 1.62 | 2.08 | **+0.46 [+0.29, +0.63]** |
| **Hold-out, 6 mid-strength** | 2.38 | 2.64 | **+0.26 [+0.13, +0.40]** |
| **Hold-out, 8 weak** | 2.73 | 2.88 | **+0.16 [+0.07, +0.25]** |
| **Hold-out, all 19 mixed** | 2.34 | 2.51 | **+0.18 [+0.07, +0.28]** |

The hold-out gains match the development gains, which is the check that the bot
was not fitted to the opponents it was built against. Further checks:

- It outscores every development opponent head to head more often than not.
- Against a table of three copies of itself no bot in the pool does better than
  it does, so it is not beaten by its own style.
- Under six alternative readings of the ambiguous rules it keeps its lead in
  five and is level in the sixth (shields that catch by presence instead of by
  STAY, which it detects during play and adapts to).

What this does not show: every opponent here was written inside this project.
Other teams' bots may behave differently, which is why the bot learns each
opponent's habits during the game instead of assuming them. Numbers, method and
commands are in [lab/README.md](lab/README.md).

## Focused repository

- `bot.py`: final already-flattened submission; no build step or extra weights.
- `tester_bots/`: the previous release plus eight standalone alternatives and controls.
- `lab/`: measurement harness, opponent pool, the new bot's source halves and results.
- `simulator/`: one human simulator with immutable bot snapshots and saved history.
- `tests/`: current regressions, a separate historical model and independent oracle.
- `tools/`: release checks, registered comparison and exact replay helpers.
- `validation/official/`: new STAY-only evidence, source additions and audit.
- Other `validation/` files: explicitly historical presence-rule evidence, unchanged
  raw results and source archives; these scores are not pooled into this ranking.

To reproduce a comparison without Git:

```powershell
python tools/unpack_sources.py
python tools/benchmark.py --spec validation/official/followup_spec.json --out .cache/repeat.json.gz --workers 8
```

Sources are restored only after archive/hash verification. Changed files and
consumed result paths are never overwritten. Retired experiment trees remain
in Git history. Existing live games and the separate uncommitted checkout were
not changed by this release.

The concurrently added `ultimate.py` is preserved as an experimental alternative.
On the same 576 STAY-only follow-up fixtures it scored 1.3446 opponents outscored,
versus 1.7300 for the previous release, with zero worker faults. It is retained
as a tester. Its original architecture
tests include historical False-mode fixtures; those are not current-rule proof.

This research branch also contains [evolution experiments](evolution/README.md),
an [independent validity overseer](evolution/OVERSIGHT.md), a
[mathematical strategy review](evolution/GAME_THEORY_REVIEW.md), and
[portable shared-GPU diagnostic jobs](compute_share/SHARED_GPU.md). These offline
tools never modify the root bot. GPU research uses a separate PyTorch
environment; the submitted bot remains standard-library-only. The requested
two-million-game primary campaign is separate from these completed control games.
