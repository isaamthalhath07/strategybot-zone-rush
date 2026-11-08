# All-branches frozen bot audit

Snapshot: 8 November 2026. All policies and opponent draws were frozen before their registered panels. No weights were trained or fitted in this campaign.

## Result

**Best measured: Novel B Feint** (`f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94`).
**Conservative promotion decision: retain Current main: Guarded Transfer** under the preregistered uncertainty threshold. A larger sample mean alone does not establish superiority.

| Frozen finalist | PW / 3 | League | Novel economy | Novel dynamic | Focal faults | Worst callback ms |
|---|---:|---:|---:|---:|---:|---:|
| Novel B Feint (`bot_f95dc9fc2266`) | 2.1155 | 1.4688 | 2.3984 | 2.4792 | 0 | 5.902 |
| Novel B Blocker (spatial denial) (`bot_1bb70109a75e`) | 2.1063 | 1.6641 | 2.2786 | 2.3763 | 0 | 2.822 |
| research/evolution-2026-11-07 (`bot_1dca0c916af4`) | 2.0477 | 1.3906 | 2.5417 | 2.2109 | 0 | 1.466 |
| Ultimate (`bot_a8f7a74e7ed3`) | 2.0308 | 1.2708 | 2.4961 | 2.3255 | 0 | 2.229 |
| Current main: Guarded Transfer (`bot_e8b3682d8b39`) | 1.9627 | 1.6094 | 2.2057 | 2.0729 | 0 | 2.063 |

PW is the number of opponents outscored (0 to 3); ties count one half. It is the pairwise outcome used by the event, not an absolute Elo rating.

| Challenger minus current main | Difference | Simultaneous 95% interval | Novel-only difference (ordinary 95% interval) |
|---|---:|---|---|
| Novel B Feint | +0.1528 | [-0.0816, +0.3698] | +0.2995 [+0.1419, +0.4642] |
| Novel B Blocker (spatial denial) | +0.1437 | [-0.1806, +0.4418] | +0.1882 [-0.0410, +0.4147] |
| research/evolution-2026-11-07 | +0.0851 | [-0.1372, +0.2943] | +0.2370 [+0.0638, +0.3971] |
| Ultimate | +0.0681 | [-0.1372, +0.3003] | +0.2715 [+0.1003, +0.4466] |

Intervals resample complete map groups, keeping every seat, priority-token and field crossing together. The aggregate intervals adjust across all final challengers with Bonferroni. Promotion also requires a positive ordinary 95% novel-only interval and a nonnegative mean difference in both novel fields. Per-field intervals are descriptive. This is finite sampled-field evidence, not a proof against all competitors.

## Every remote branch head

Every distinct passing remote root `bot.py` received the same 96-game development panel. These are selection scores, not independent confirmation results. Equal hashes mean the same bot appears in more than one branch. Archived policies and other exports are listed in COVERAGE.md.

| Branch | Pinned commit | Root SHA | Development PW / 3 |
|---|---|---|---:|
| claude/rulefix-stuck-home | `ed708f30105c` | `b2de2f334e88` | 2.1302 |
| codex-audit-and-robustness | `3e787a9828e8` | `cefe2fa7bce1` | 1.2708 |
| codex/consolidated-champion | `36275b7102cf` | `fc00af81fdf7` | 1.6979 |
| codex/fresh-opponents-and-adaptation | `13cd21568347` | `720e5a3daf7b` | 2.1302 |
| codex/official-stay-shield | `bf3440f19c17` | `e8b3682d8b39` | 1.7917 |
| hardened-field-and-fixes | `961e729a3073` | `aa49608fe334` | 1.3438 |
| main | `d81136b2d246` | `e8b3682d8b39` | 1.7917 |
| research/evolution-2026-11-07 | `0796039f42f0` | `1dca0c916af4` | 2.1302 |
| shaunakbr1 | `9b7432bc4037` | `f7b40080a522` | 1.2083 |
| shaunakbr2 | `4baf23937475` | `f7b40080a522` | 1.2083 |
| v7-independent-field | `c7cbaa97e226` | `31965e1412c6` | 1.3542 |
| visual-harness | `7fa9b73affed` | `f7b40080a522` | 1.2083 |

## Coverage and protocol

- 12 live remote branches and 25 local/remote references were pinned; 352 unique Python sources parsed with zero syntax errors.
- 93 exact-byte standalone exports plus 33 class builds were inventoried. Class builds matched their originals on 10,560 public callbacks. The NN export embeds the existing frozen weights; its training-side Torch self-test is removed.
- Independent per-seat processes receive only board, bot ID, priority-token flag and legal actions. Input fingerprints detect mutation. Diagnostic games sample caught exceptions; strength games use the actual 200 ms limit (2 seconds first turn).
- Only current effective-STAY Shield rules are used. Moving successfully escapes Shield; a blocked or lost move counts as STAY; frozen STAY does not advance work.
- Boards are rejected by actual contents if present in earlier validation JSON. Final boards and four final challenger decision families are separate from screening/development.
- Generated challengers use fresh per-map configurations without testing those settings against a candidate. Every candidate gets the same fixtures. Historical policies remain in the league field for evaluation only; there is no training on them.
- Each final policy plays 1,152 games: 24 fresh boards x 4 seats x 4 priority-token starts x 3 fields. Mean weights the three fields equally.

| Panel | Candidates | Games | Callbacks | All worker faults |
|---|---:|---:|---:|---:|
| contracts | 93 | 372 | 117808 | 13 |
| contracts_extra | 25 | 100 | 32000 | 0 |
| screen | 116 | 3712 | 1187840 | 0 |
| development | 15 | 1440 | 460800 | 0 |
| outsiders_contract | 8 | 32 | 10240 | 0 |
| outsiders_screen | 8 | 256 | 81920 | 0 |
| final | 5 | 5760 | 1843200 | 0 |

**Total: 11672 games, 3733808 callbacks.**

Contract games diagnose safety, not playing strength. The incomplete `agent_new.py` fragment crashes because `PARAMS` is missing. `opp_buggy_01.py` intentionally returns diagonal illegal actions and is a negative control. Neither is eligible for promotion. Other deliberate negative controls (slow, oscillator and Flaky) can return legal actions while deliberately playing poorly; legal execution is distinct from strategic correctness. Original sources and failures are preserved instead of silently rewriting their history.

Eight class-only outsider controls were discovered in the final coverage review. They were frozen, checked for exact build equivalence, and tested against the original contract and screen fixtures before final outcomes were opened. None met the original eighth-place screen threshold, so the frozen final pool stayed unchanged. See inventory_outsiders.json, outsiders_selection.json and outsiders_equivalence.json.

## Challenger families

| Stage | Families and decisions |
|---|---|
| Screen | District rate rewards nearby free income; time discount penalizes long travel; turn budget balances upgrades and claims; local pairs values a second nearby job. |
| Development | Return schedule commits to capture plus upgrade; capture deadline anticipates races; sector bids values neighborhood resources and congestion; sampling portfolio randomizes among valuable jobs. |
| Final | Boundary cluster works near enemy borders; periodic switch changes between inner and outer priorities; cooldown feint steps away from a ready landlord; chase income attacks projected leaders. |

These are distinct decision rules using shared parsing and pathfinding, not independently authored AI submissions. Novel families reduce dependence on the historical zoo; they cannot establish that overfitting is impossible.

## Reproduce and inspect

Run `python tools/unpack_sources.py`, then `python tools/check_release.py`. The source archive manifest checks every restored file. Specs, registrations, compressed full trajectories, per-panel summaries and `decision.json` are retained here. Sources and runner/referee hashes were checked before and after each panel.

To rerun a panel, use `python tools/audit_run.py --spec validation/branch_audit/final_spec.json --out .cache/recheck.json.gz --workers 8`. Use a new output path. `--resume` only accepts an identical registration and code. Some historical policies use unseeded global randomness or wall-clock throttling; reruns need not reproduce their exact moves. Raw recorded actions preserve what actually happened.

[Complete policy coverage](COVERAGE.md). [Decision and intervals](decision.json). [Pinned branch/source inventory](inventory.json). [Class exports](inventory_extension.json).

## Limits

All branch tips and known archived standalone builds are covered, plus listed class defaults from the historical audit branch. This is not an enumeration of every historical commit, every possible parameter combination, or every training checkpoint. Early stages are selection data; their scores are not pooled with final scores. Zero observed faults is not proof of bug-free code. Timing is measured on this machine. No official server simulator is available; the independent-engine release tests check the local interpretation.

The best measured frozen source is exported as [`audit_best_measured.py`](../../audit_best_measured.py), byte-identical to its tested snapshot. `bot.py` and the existing release manifest retain the initial merged release under the stricter promotion rule; this audit is on a separate branch. See [release checks](release_checks.txt) and [independent replay](independent_replay.json).
