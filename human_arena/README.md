# Play Zone Rush yourself

Open the [updated human simulator](http://127.0.0.1:8775/). It runs one human
against three independent copies of the selected bot. The recommended version
is pinned by its exact file hash, using the recorded comparison in
[PRESENCE_VALIDATION.md](PRESENCE_VALIDATION.md). Earlier tabs, including port 8773,
keep their older server processes and rule flags; use port 8775 for the post-movement shield version.

To launch it later from the project folder:

```powershell
python human_arena/server.py
```

The default port is 8775. No packages or account are required. Choose your
opponent, corner, and seed, then start. Each match keeps its original source
even if a branch, candidate file, or recommendation changes afterward.

| Control | Action |
|---|---|
| Arrows or W/A/S/D | Move |
| Space | Stay: claim, raid, or upgrade |
| Q | Shield, when available |
| On-screen buttons | The same actions |

Arriving does not capture a cell. One productive stay claims neutral or rival
level-one land. Three productive stays upgrade your level-one land or capture
rival level-two land. Each holding pays income after every turn. Homes cannot
be captured. Moving, shielding, and becoming frozen reset work progress.

## Freezing and thawing

A successful shield checks the board **after movement** and catches eligible
rivals anywhere on its owner's land, including new arrivals and moves between
that owner's cells. Moving completely off that owner's land escapes. Rivals
already frozen at the start of the turn are ineligible. A shield catching
nobody eligible backfires on its user. In either case, the
affected player must stay for the **next two game turns**, with no work
progress. Stay advances the whole game; waiting in real time does not thaw you.

Standard view now shows the exact `2 â†’ 1 â†’ 0` countdown and tells you when
movement returns. A shield has a separate four-turn cooldown. After thawing,
remaining on an upgraded enemy cell can let its owner recharge and catch you
again before your third productive stay. Leave that owner's land when this raid is being
repeatedly defended. [The uploaded B5 example](analysis/a4897686/freeze_review.md)
replays all 80 turns and explains the successive freezes.

New matches explicitly use `catch_requires_stay: false`. Older running matches
and downloaded histories keep their original rule flags. Historical replays
must use the flags saved with that match; their outcomes and hashes are not
rewritten. The vendored referee source remains pinned to its original hash.

## Recording

Every accepted turn saves locally under `human_arena/history/<match-id>.jsonl`
before the server confirms it. **Download match** exports the current game;
**Saved matches** keeps previous games after replacements and restarts.
Records include public observations, requested and accepted actions, resolved
events, board states, scores, timing, and source/rule hashes. A recording error
stops further turns rather than silently losing history. Old unrecorded games
cannot be reconstructed.

## AI view

The **Standard / AI view** switch changes the same match without a turn or
reset. [Open directly in AI view](http://127.0.0.1:8775/?view=ai).

Bots see all 64 cells: occupant, owner, upgraded/home/frozen flags and base
points. Their other direct inputs are their seat, priority-token Boolean and
legal actions. They may remember earlier public observations. They receive no
human pending action, private progress, exact cooldown, referee object or
opponent source code.

AI view hides observer scores, turn counts, work/cooldown/freeze counters,
history and numeric results. Its inspector contains exactly the four public
observation fields. Base values and upgrade flags are shown separately.

This simulator implements the published rules locally; the organiser's
competition server remains authoritative. Tests and visual verification are
recorded in [PRESENCE_VALIDATION.md](PRESENCE_VALIDATION.md).
