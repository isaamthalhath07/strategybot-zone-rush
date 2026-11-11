# CUDA full-match physics review

`CudaPhysics` executes the unchanged integer `BatchGame` physics on actual CUDA.
Its graph contains physics operations only. It never invokes the diagnostic
toy policy, e8, an opponent or a search teacher. Exact existing actors remain
external CPU callbacks.

Every graph output returns to stable input buffers, including all rebound
state tensors. Two warm steps and one capture step are discarded; every state
field and the host clock are restored to the opening before accepted play.
Each explicit step advances the true host turn once. After 80 steps the clock
is 81 and another step is rejected. Eager CUDA has the same public API.

Accepted actions must be exact CPU integers with shape B by 4, range 0..5 and
current public legality. Booleans, floats, GPU inputs, malformed shapes and
illegal casts/moves fail before the underlying engine can normalize them.
Official blocked moves remain legal intentions and resolve to effective STAY.
Map values, mirror symmetry, priority tokens, rules and turn limits are checked.
CPU fallback is rejected, and construction executes a real CUDA arithmetic
probe. Frozen physics/adapter source hashes and the new module hash are retained.

Public snapshots contain only isolated CPU public cells, each player's legal
mask, and priority tokens. Full score/progress/cooldown state is available only
through the explicitly observer-only state method. The exposed batch belongs
to the trusted evaluator; this is not a hostile-code isolation mechanism.
Reported component times are synchronized host wall seconds, including setup,
uploads and downloads, rather than kernel-only timing.

Seven focused tests passed using Python 3.12, Torch 2.11.0+cu128 and the local
RTX 5070 Ti Laptop GPU. Both graph and eager paths independently ran four
synthetic lanes for all 80 turns, comparing every dynamic field, public legal
mask and clock against both reference engines after each step. Tests also
cover moving Shield escapes, blocked catches, simultaneous backfires, two
frozen future turns, cooldown 4 through 0, owner/priority contests, upgraded
capture bonuses, progress resets, upgrades, stable buffers, invalid inputs and
snapshot isolation. Test-body time was 1.397 seconds on this run.

No actual policy callback, registered gold fixture, cohort or primary campaign
ran in these tests. Warm/capture work and synthetic checks grant zero primary
matches, completed-game/BMCTS audit credit or playing-strength evidence. They
establish no end-to-end speedup for the CPU policies or independent actor audit.
