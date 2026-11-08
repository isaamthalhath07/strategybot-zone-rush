# Planning with conditional futures

This directory preserves the historical forward-planning experiment against v8.
Its frozen comparator now lives at `baselines/v8.py`; the active root `bot.py`
follows main's fusion policy. Historical results, registrations, and the measured
`submission/bot.py` remain unchanged. Source integration edits invalidate the old
locks: use commit `9df9497` to reproduce the original measurements and release
verification. New runs record `baselines/v8.py` explicitly and require new locks.

For a separate current-code behavior check, without replacing the measured export:

```powershell
python -m futurelab.build --candidate one_job --out futurelab/submission/rebuilt_bot.py
python -m futurelab.verify --artifact futurelab/submission/rebuilt_bot.py --quick
```

This check establishes export equivalence, not a fresh playing-strength result.

The previous planner searched a walk of several work cells but largely priced
each job using today's ownership. A target could be neutral in its search and
already claimed or upgraded by the time the real bot arrived. This experiment
adds an explicit forward game model and tests the difference between predicting
future boards and successfully acting on those predictions.

## What the planner now considers

1. Reconstruct a hypothetical current game from the public board and remembered
   observations: positions, ownership, upgrades, income, accumulated scores,
   progress, freeze counters and cooldown estimates. No actual referee object,
   opponent parameters, secret actions or future state reaches the policy.
2. Propose several work choices using the original route search. Alternatives
   must be reachable through its candidate set; this is not exhaustive search.
3. Sample six joint opponent hypotheses. Generic economic profiles cover
   expansion, investment, central travel, perimeter travel and raiding. Sparse
   public-action evidence can update their weights, with tempering and forgetting.
   This is approximate inference, not identification of an opponent's source code.
4. For each alternative first action, simulate all four bots simultaneously.
   Rivals can claim, upgrade, raid, shield and block one another. A target that
   becomes upgraded requires three raid STAYs. Its capture resets the upgrade
   and awards the correct bounty. Frozen turns do not accrue work.
5. Prescribe just the next work commitment, then use a flexible economic
   continuation. The real policy executes one action and replans from its next
   real observation. It does not blindly execute a long guessed future.
6. Compare outcomes across the joint hypotheses. A variance penalty and a small
   minimum gain discourage overrides based on one optimistic imagined world.
   When computation runs out, incomplete batches are discarded; too little
   evidence returns the original planner's chosen action.

The default horizon varies across particles around 24 turns (20, 24 and 28).
This reduces a single cutoff's influence on unfinished investments. After the
simulated horizon, current income is projected through turn 80. That terminal
heuristic is approximate: it does not prove the land will be retained or that
no later investment will occur. Replanning limits, but does not remove, that risk.

The simulator's physical rules are the tested reference engine. Accuracy is
conditional on the reconstructed hidden state and the actions chosen by our
opponent models. Opponent strategy changes, inaccurate cooldown inference and
unmodelled responses to our own policy can still make a forecast wrong.

## What failed, and the correction

The first version prescribed long fixed walks during simulation while the real
bot changed its mind after every capture. A capture followed by an immediate
upgrade could therefore be underpriced, and repeated reranking could change
plans too frequently. On discovery it lost 1.375 PW/3 to v8. Better ownership
forecasts did not rescue an inconsistent decision model.

The corrected version evaluates one work commitment followed by a flexible
continuation. It gained 0.4063 in discovery and 0.2813 on unused development
scheduling rules. A version committing to finish the job also gained, but its
small development advantage was uncertain. We chose the simpler version with
no extra job-lock state, rather than treating an uncertain difference as proof
of equivalence. This is a structural correction supported by the new results,
not a claim that all causes of the initial loss have been individually isolated.

The matched prior-only version also improved in development. The learned
version's additional +0.0558 had interval [-0.0596, +0.1712]. The evidence supports
the whole forward-planning policy more strongly than a separate claim that
within-game opponent learning itself increases playing strength.

See `RESULTS.md` for every recorded comparison, including all rejected versions.

## Prediction checks

In 56 diagnostic games played by the unchanged baseline, forecasts were recorded
before the future public boards arrived. Future boards supplied labels only.
Errors were averaged per game so repeated cells/turns were not treated as
independent samples. Five-class ownership Brier losses were:

| Turns ahead | Keep current ownership | Simulated futures |
|---|---:|---:|
| 4 | 0.0991 | 0.0482 |
| 8 | 0.2006 | 0.1189 |
| 16 | 0.4006 | 0.2331 |

These are discovery-distribution diagnostics, comparing against persistence.
They are not evidence of calibrated probabilities against actual competition
entries, nor proof that learning outperforms every simpler forecasting method.
They also evaluate the original baseline-route forecast rather than secretly
using the real bot's later actions as input.

## Avoiding another field-specific improvement

- Every paired task draws three fresh opponent parameter sets. No old zoo bot,
  competitor implementation, prior submission or bred counter is an opponent.
- Four discovery scheduling rules are reused only as discovery, with new seeds
  when correcting the policy. Three different development rules select the
  candidate. Four further rules are reserved for the locked final test.
- The final test adds two map distributions absent from discovery. Every map
  crosses all seats and starting priority tokens. Maps always stay mirrored and
  within values 1–3.
- Four additional newly authored schedulers test the actual bounded runtime.
  They include action-level beam search, an expiring-opportunity portfolio,
  relative bids, and stochastic work blocks. They were not fitted to our policy.
- Candidate, source hashes, seeds, sample sizes and criteria are written before
  each final comparison. All outcomes and subgroups are published. A consumed
  final set must never become a tuning set still described as held out.

These are fifteen new scheduling rules, not fifteen independently authored
implementations. They share public-state parsing and work bookkeeping. Every
measured gain is conditional on synthetic distributions; no finite experiment
ensures universal non-overfitting or optimality against arbitrary AI competitors.

## Runtime and the single-file artifact

`bounded.py` checks deadlines inside candidate generation, every simulated
player turn and every opponent-model update. Work planning uses an internal
budget; foresight stops around 125 ms and model updates around 150 ms. These are
targets with finite check granularity, not a hard real-time operating-system
guarantee. Unfinished batches contribute no score. If too few complete batches
remain, the policy returns the original work choice.

`build.py` generates `submission/bot.py`. It combines the benchmark, reference
physics and forward policy with distinct global prefixes. The generated file
uses only the standard library and has `act(state)`. It contains no project
imports, external data files, dynamic execution, training framework or network
access. The v8 benchmark remains byte-identical at `baselines/v8.py`.

`verify.py` compares the export against the measured policy with clocks disabled,
then exercises the actual public entry point with runtime guards enabled. The
shared-module tests cover four seats, repeated games, flat and tuple boards,
legal output, input immutability and actual timing. Its release report binds the
artifact hash to both final result files.

## Files

| File | Purpose |
|---|---|
| `models.py` | Generic economic hypotheses and censored public-history likelihood updates |
| `rollout.py` | Hypothetical state reconstruction and original joint rollouts |
| `agent.py` | Route proposals and the rejected fixed-walk experiment |
| `alternatives.py` | Corrected single-job continuation, locking and conservative controls |
| `bounded.py` | Interruptible runtime equivalent to the selected policy when time is unlimited |
| `opponents.py` | Discovery, development and final scheduling families |
| `confirmation.py` | Four further opponents and independent runtime confirmation |
| `evaluate.py`, `evaluate2.py`, `protocol.py` | Frozen experiment protocols, retained so earlier failures remain reproducible |
| `prediction.py` | Ownership prediction on fixed baseline trajectories |
| `build.py` | Standard-library-only artifact generator |
| `verify.py` | Export equivalence and actual entry-point checks |
| `report.py` | All outcomes and descriptive subgroup tables |
| `results/` | Raw paired tasks, specifications, source hashes and scores |

Reproduction from this experiment's Git revision:

```powershell
python test_futurelab.py
python -m futurelab.report
python -m futurelab.build --candidate one_job
python -m futurelab.verify
# Use new output paths to preserve the recorded evidence:
python -m futurelab.protocol --split final --games 864 --seed 893741 --workers 8 --variants baseline one_job --lock futurelab/final_registration.json --out futurelab/results/reproduced_final.json
```

Wall-clock native runs can differ slightly with machine load. Deterministic
policy comparisons explicitly disable truncation; exact action equivalence is
checked separately from deadlines. Full tournament claims should not be inferred
from correctness tests or self-play alone.
