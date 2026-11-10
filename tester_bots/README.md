# Retained tester bots

Each file is standalone and pinned by the release manifest. The actual simulator
enforces STAY-only catches; a tester's historical internal assumptions do not
change the physics. No deliberately broken control is retained.

| File | Role |
|---|---|
| `guarded_transfer.py` | The release before the lab bot (guarded Transfer, SHA-256 `e8b3682d…`). 2.313 rivals outscored over the 1,344 pooled out-of-sample games in `lab/results/test_ext1.txt`, against 2.575 for the current root bot. |
| `transfer_previous.py` | Strong repaired STAY-only baseline; matched the first guarded Transfer across the 128 balanced and 384 earlier frozen current-rule games. |
| `research_alternative.py` | Corrected guarded research genome: 1.4991 mean rivals outscored over 576 latest fresh current-rule games. Same implementation as the release apart from frozen strategic weights. |
| `ultimate.py` | Concurrent experimental engine: 1.3446 on the same 576 current-rule follow-up fixtures. Preserved unchanged; its rule inference remains approximate. |
| `fusion.py` | Historical fused economic policy, interface/cold-start safeguards and different fallback architecture; current-rule frozen control. |
| `apex.py` | Exact-copy counter-policy specialist. Useful predictability challenge; recognizing a near-copy is uncertain and its model assumptions limit generalization. |
| `racer.py` | PR10's income/capture-racing challenge. |
| `blocker.py` | PR10's obstruction/denial challenge. |
| `transfer_original.py` | Original economic control, retained to detect regressions against legacy task pricing and valid same-owner-cell feints. |

Current STAY-only results are under `validation/official/`. Earlier presence-rule
scores remain historical; do not pool or directly rank across different rounds.
All retained files had zero worker faults in their recorded comparisons.
Source commits, full hashes and selected comparisons are in the release manifest
and source registry. Testers receive no pending opponent action or private state.
