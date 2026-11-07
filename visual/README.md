# Local visual harness

This viewer plays recorded games from `engine.py`. It is **not the official
StrategyBot Arena**, and it cannot establish equivalence to the official server.
The public starter repository contained only its README and `bot.py` when checked
on 7 November 2026; its README names the Arena without providing a URL.

From the project directory:

```powershell
python visual_harness.py
python test_visual_harness.py
python -m http.server 8765 --bind 127.0.0.1 --directory visual
```

Open `http://127.0.0.1:8765/`, or open `index.html` directly. Choose a match,
press Play, step with the arrow buttons/keys, scrub the timeline, or jump to End.
Select a cell to see its ownership, level, value and occupant's work progress.

The five matches include strong unfamiliar opponents, raid/shield pressure,
four isolated copies of the submission, different AI architectures, and two
freshly authored challengers. These games are examples for inspection, not a
tournament estimate of strength.

Every submission seat loads a fresh module and calls its public `act(state)`.
Bots receive the documented `engine.View` only. The observer records engine
internals for display; the bot never receives them. A transparent observer around
`Agent.decide` reports swallowed planner exceptions while preserving `act`'s
fallback and timing guards. The harness also detects changed input, illegal
actions, escaped exceptions and local timeouts. An expired/illegal response is
substituted with `STAY`, matching the documented server policy.

`replays.json` is the inspectable evidence: all 81 board snapshots, all requested,
accepted and resolved actions, per-call times, failures, map seeds and rule flags.
SHA-256 hashes bind the bot source, engine source and action/state traces. The
viewer embeds this exact data, requiring no remote services. The tests replay the
accepted actions through the engine and require every board, score and resolved
action to match. Regenerating traces after editing either source is required.

Shipping time guards remain enabled, so regeneration can vary with machine load.
A saved trace replays exactly; a seed alone does not promise identical regeneration.
Local times do not establish timing on grader hardware. Placements follow the
local engine's default Round 1 scoring. Shield cooldown and freeze counters shown
in the observer are hidden from competition bots; their reconstruction may differ.

Use `--scenario 1` through `--scenario 5` to generate one match, `--bot PATH` to
select another single-file submission, and `--out DIRECTORY` for a separate output.
