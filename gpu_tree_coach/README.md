# GPU observation-tree coach

An offline prototype that batches independent public-history MCTS roots. CPU and CUDA execute the same exact integer models; an independent scalar tree/referee checks complete outcomes. No bot or primary campaign is changed.

Use the repository's CUDA-compatible `.venv-rl` interpreter. On the current machine it is `C:\Users\LEGION\stratergybot\.venv-rl\Scripts\python.exe` (Torch2.11.0+cu128). The older default Torch installation does not support this GPU's kernels. No new dependency is required beyond that working PyTorch environment.

From this worktree:

```powershell
C:\Users\LEGION\stratergybot\.venv-rl\Scripts\python.exe -m unittest gpu_tree_coach.test_tree gpu_tree_coach.test_cli -v
C:\Users\LEGION\stratergybot\.venv-rl\Scripts\python.exe -m gpu_tree_coach roots.jsonl fresh_receipt.jsonl --device cuda --verify-reference
```

Add `--cuda-graph` to use the tested single-step CUDA Graph mode. Its setup is included in reported timings. On this machine ordinary eager CUDA was slower than CPU in every tested batch; graph mode was faster than CPU tensor on the small measured panel. The independent scalar engine still won at 1 and 8 roots. See [RESULTS.md](RESULTS.md) for exact timings and limitations.

The input is JSONL, one strictly validated root per line:

```json
{"schema":1,"kind":"public-observation-tree-mcts/1","root_id":"unique-label","initial_observation":{"board":"REPLACE_WITH_PUBLIC_8_BY_8_CELLS","bot_id":1,"is_priority_token":true,"legal_actions":["EAST","SOUTH","STAY","SHIELD"]},"transitions":[],"search":{"seed":91,"simulations":24,"horizon":5,"beam_width":6,"max_nodes":256,"support_cap":512,"income_tail":12,"trace":true}}
```

The board placeholder must be replaced with the real serialized public board: 64 cells, each `[occupant,owner,upgraded,home,frozen_boolean,base_points]`, or an exact six-field public cell dictionary. The initial observation must be from the actual opening. Every subsequent transition is exactly `{"own_action":"STAY","observation":NEXT_PUBLIC_OBSERVATION}`. Only accepted own actions and observations belong in the prefix. Cold midgame snapshots and private referee snapshots are rejected.

Output has `root_result` records and a final summary containing source fingerprints, unsupported-root counts, timings and zero game-credit fields. A result contains the complete compact tree, optional traces, the inferred-support summary and explicit approximations. The sink streams records to a temporary file; an input error or exact-reference discrepancy prevents publication. Existing output files are never overwritten.

Default budgets are 256 roots/chunk, 4096 inferred states/chunk, 65536 reserved tree nodes/chunk and 16384 total input roots. A single root exceeding a chunk budget is rejected, never silently assigned fewer nodes. CLI line size is limited to 2 MiB. `--verify-reference` runs a full independent scalar search and can dominate execution time; this cost is reported separately. End-to-end speed comparisons must include inference, tensor setup, CPU tree work and observation transfers.

See [DESIGN.md](DESIGN.md) for the exact information boundary, utility, UCT, fixed beam-pruning limitation, timing contract and next validation steps. This prototype makes no optimality, playing-strength, 200 ms-runtime, BMCTS-audit or completed-game claim.
