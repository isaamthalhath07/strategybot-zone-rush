# Zone Rush: STAY-only Shield release

`bot.py` is the standalone submission: one standard-library file exposing
`act(state)`. It uses only the four documented public inputs and remembered
public history. It includes the selected economic planner, inferred scores and
work/cooldowns, valid same-owner-cell Shield feints, input guards and recovery
when public evidence proves a requested Shield was replaced with STAY.

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

Python 3.10 or newer is sufficient. The release passes **133 Python tests** and,
when Node is installed, six offline interface logic groups. These include both
historical and current physics, 48 complete independent-engine differential
games, exact public-history oracles, real-worker recording/replay and privacy,
request races, fallback recovery and a downloaded folder without Git.
Visual-harness testing is optional under the user's instruction.

## Current selection evidence

The new **STAY-only** comparison contains **5,832 games and 1,866,240 timed
callbacks**, with zero worker faults. It screened 70 admissible archived policies,
then compared 12 balanced candidates, six frozen finalists and two recovered,
fixed-genome alternatives on twelve further fresh boards. Each final follow-up
policy played 576 common fixtures: all 16 corner/priority combinations in three fields.

| Latest fresh follow-up | Mean opponents outscored / 3 | Worst callback |
|---|---:|---:|
| **Selected guarded Transfer** | **1.7300** | **2.02 ms** |
| Guarded research alternative | 1.4991 | 1.48 ms |

The paired difference is +0.2309, with 12-map clustered 95% bootstrap interval
[-0.0243,+0.4939]. The interval includes zero: this is the best measured option
in that follow-up, not proof of universal superiority. The research settings led
the earlier eight-map round, while Transfer led balanced development and the
separate follow-up. Both strategic genomes were historical, frozen settings;
no coefficients were fitted after observing final outcomes.

The recovery-only revisions matched their original versions on **61,440 exact
public-action pairs** from all 768 recorded finalist games, and received their
own fresh process-isolated follow-up. No private acceptance acknowledgement is
invented: an externally substituted action that is observationally identical to
an accepted one cannot be uniquely diagnosed from the four-field interface.

[Current validation](validation/official/REPORT.md),
[exact rule clarification](validation/official/rule_contract.json),
[release fingerprints](release_manifest.json).

## Focused repository

- `bot.py`: final already-flattened submission; no build step or extra weights.
- `tester_bots/`: eight standalone alternatives and specialist controls.
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
versus 1.7300 for the selected release, with zero worker faults. It is retained
as a tester and has not replaced the validated root bot. Its original architecture
tests include historical False-mode fixtures; those are not current-rule proof.

This research branch also contains [evolution experiments](evolution/README.md),
an [independent validity overseer](evolution/OVERSIGHT.md), a
[mathematical strategy review](evolution/GAME_THEORY_REVIEW.md), and
[portable shared-GPU diagnostic jobs](compute_share/SHARED_GPU.md). These offline
tools keep the validated root bot unchanged. GPU research uses a separate PyTorch
environment; the submitted bot remains standard-library-only. The requested
two-million-game primary campaign is separate from these completed control games.
