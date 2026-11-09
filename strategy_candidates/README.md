# Public-memory correction candidate

`blocker_public_memory.py` is a standalone, unpromoted candidate generated from
the exact original Blocker (SHA-256
`1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5`).
It changes no archived tester, registered architecture-study arm or production
file. Its current SHA-256 is
`f5e870cd8bb56024c579d1251943c656daf62d2652c5eba44aee530ba1160405`.

The original observer can mistake a rival's backfired Shield for the landowner's
Shield, even when the landowner visibly moved, the owner is the focal player and
its own accepted action was not Shield, or an eligible stationary focal player
on that owner's land demonstrably escaped freezing. That false attribution
invents a cooldown and can suppress real own capture progress.

The correction applies those public consistency constraints, uses ownership
before the work phase when attributing catches, and counts own raid progress
from observed movement/freeze status and the accepted own action. Actual owner
Shield would already freeze an eligible own STAY; a guessed owner Shield cannot
override that observation. Blocked moves count as STAY.

Nine tests pass. The original five scenario tests replay legal 25-turn scripts in both referees,
including the original bug, a blocked move, a moving owner and a known own
non-Shield. An indistinguishability test compares two legal worlds with identical
focal public histories but different hidden cooldowns, requiring identical
candidate inference and decisions. Referee truth is used only by test observers.
Three independent tests additionally cover own-Shield immunity, an already
frozen observer, and 24 complete legal histories checking own progress,
reconstructed scores and unchanged public inputs against both referees.
These scripts isolate memory tracking by recording the scripted accepted own
action. They do not claim the unmodified planner itself chose that path.

A separate 500-seed mechanics probe checked 162,000 public observations and
20,952 legal Shield actions, with no own-progress mismatch or referee divergence.
Its preserved script, stdout and exact source hashes are recorded in
`evidence/independent_review.json`. The probe supplies accepted scripted actions
to the observer; it does not evaluate planner decisions, playing strength or
the candidate's heuristic rival-cooldown accuracy. All checks grant zero primary
or strength credit. The probe was not rerun when preserving its evidence files.
The tracked stdout is `evidence/public_memory_probe_500.txt`; the local `.log`
copy is ignored by Git. Run the recorded reproduction command from the repository
root so its package imports resolve.

The correction is deliberately limited: remaining genuinely ambiguous rival
Shield events still use the original heuristic point estimate. It is not a full
posterior, proof of optimality or playing-strength improvement. It needs a new
fresh-map controlled study after the frozen four-policy comparison; adding it
as a fifth arm after registration would change that experiment.

```powershell
python -m strategy_candidates.build_public_memory
python -m unittest strategy_candidates.test_public_memory strategy_candidates.test_independent_memory -v
```
