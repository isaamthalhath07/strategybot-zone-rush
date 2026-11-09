# Portable public-history GPU coach

`gpu_batch.py` is a working offline CPU/CUDA worker. It reconstructs a belief
from a complete public prefix, evaluates sampled common open-loop plans against
responding public-only rival models, and independently replays the resulting
actions and final states with the standard-library reference engine. It never
changes the deployed champion. Its trajectories count as **zero primary games**.
This is not full BMCTS or a proof of optimality.

## Run a job

Use a Python environment whose PyTorch build actually runs a CUDA kernel on
the target GPU. Device detection alone is insufficient. The local working
environment is `.venv-rl` with PyTorch 2.11/CUDA 12.8; the default local Python's
older CUDA build cannot execute kernels on the RTX 5070 Ti. No global package
or driver changes are required by this worker.

```powershell
python -m search_coach.gpu_batch --input job.json --output result.json --device cuda
```

For a CPU contributor, select `--device cpu`. Input JSON contains either one
strict job or a batch envelope. The worker performs a real CUDA smoke kernel
before accepting CUDA work. It writes the result atomically after verification.
The optional `--skip-independent-verification` flag is for throughput diagnosis;
its result is prominently unverified and must not be accepted as remote work.

Single-job keys are exactly:

```json
{
  "schema": 1,
  "kind": "public_history_gpu_coach",
  "job_id": "unique-assigned-id",
  "initial_observation": "THE REAL INITIAL FOUR-FIELD OBJECT",
  "transitions": [
    {"own_action": "EAST", "observation": "THE NEXT FOUR-FIELD OBJECT"}
  ],
  "search": {
    "seed": 317,
    "horizon": 3,
    "plans_per_root": 8,
    "rollouts_per_plan": 16,
    "support_cap": 512,
    "income_tail": 12
  }
}
```

The quoted observation placeholders above describe objects; the actual job
must contain the serialized board, bot ID, own priority flag and own legal
actions. Cells use the public order occupant, owner, upgraded, home, frozen,
base. All initial observations and transitions are validated by `PublicBelief`.
Mid-game cold starts, hidden fields, joint future actions, actual controller
identities and actual opponent seeds are not accepted. Search options are
optional and use the defaults shown, except the default seed is zero.

A batch has exactly `schema: 1`, `kind: "public_history_gpu_coach_batch"`, and
`jobs: [...]`. The batch permits 1–64 unique job IDs and at most 65,536 synthetic
trajectories. `--max-trajectories` controls chunk size from 1 to 8,192. Different
effective horizons are grouped separately. The horizon is clamped at the end
of the 80-turn game. Input files are bounded to 128 MiB.

## Information and action boundaries

The model receives `PublicPolicyBatch`: one row per player, with only its board,
bot ID, own priority Boolean and own legal-action mask. The board contains the
frozen Boolean, never the remaining frozen counter. Cooldown, work progress,
scores, actual controller state and future actions are absent from this policy
input. The trusted referee adapter is the only code that converts simulated
private state into those public fields. The integer model operates independently
on each row; another player's private legal mask cannot affect that row.

Rollout model families and random draws are generated from the public prefix,
explicit diagnostic seed and sample index. They are hypothetical models, not
the real opponents' seeds or IDs. Integer counter noise and canonical tie breaks
make decisions reproducible across CPU and CUDA. All players decide from the
same pre-turn board and rivals respond afresh after counterfactual deviations.

Every focal plan is a single requested action sequence shared across its sampled
belief states. A publicly illegal future request becomes STAY. Plans are scored
after aggregation over trajectories; the planner does not pick a different
continuation for each hidden state. This avoids giving the focal player hidden
state knowledge through strategy fusion. Uniform support sampling remains an
uncalibrated possibility mixture, and a capped support can discard truth.

## Objective

The worker optimizes Round 1 pairwise points: one point for beating a rival,
half for tying and zero for losing. At terminal states it compares final scores
exactly, without an income tail. Before termination it explicitly uses a proxy:
score plus a bounded income tail for each player, then the same pairwise ranking.
The proxy assumes current incomes persist during that tail and can be wrong.

Each plan returns an integer `value_numerator_sum` and `value_denominator`
equal to twice its rollout count. A single trajectory's numerator is 0–6;
mean points are 0–3. The field `mean_projected_pairwise_points` is a heuristic
model average, not a calibrated probability of winning. A regression verifies
that `[101,100,100,100]` earns three wins and outranks `[200,201,202,1]`, which
earns only one, despite the latter's larger margin over the average rival.

This differs from the older CPU `beam.py` diagnostic's margin-based cutoff.
That historical prototype and its pinned evidence remain unchanged. Neither
diagnostic is promoted automatically or treated as stronger than the champion.

## Verification and remote acceptance

By default, every trajectory is replayed through the independent reference
engine. A separate standard-library implementation reconstructs every rival
decision from public observations and checks the full joint-action trace,
final owners/upgrades/homes/positions/freeze/cooldown/progress/score/income/token,
and pairwise utility. Verification failures abort the job.

The result includes input hashes, algorithm source hashes, trace digest,
independent replay counts, support truncation status, root values, chosen common
plans, environment details and timing. Per-job input hashes use SHA-256 of
`json.dumps(job, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()`.
Source hash paths use forward slashes for portability across operating systems.

A source hash or a worker's claimed verification flag does not prove execution.
The receiving coordinator must bind each result to its assigned job ID/input
hash, reject duplicates and unknown IDs, check the pinned source catalog and
independently recompute the expected CPU values before accepting the result.
Elapsed time and device names are measurements, not integrity proofs. Remote
work contributes teacher diagnostics; all outputs retain `primary_campaign_games:
0`, `full_bmcts: false` and `deployed_policy_changed: false`.

Required local source modules for a portable bundle are:

- `search_coach/__init__.py`, `belief.py`, `beam.py`, `gpu_batch.py`
- `training_gpu/__init__.py`, `batch_game.py`
- `tests/__init__.py`, `reference_engine.py`

Pin every bundled file in the transport manifest, including import modules,
and verify that manifest before execution. Jobs contain data, never executable
Python, arbitrary module paths, pickles or shell commands. This worker opens
no network listener and performs no network scan or firewall changes.

## Measured validation

Eight tests pass, including actual CPU/CUDA action/value parity, row-local
policy isolation, input immutability, chunk-size invariance, rejected hidden
fields, duplicate IDs, public-history invariance under different actual rival
cooldowns, pairwise-objective regression and zero terminal income tail:

```powershell
python -m unittest search_coach.test_gpu_batch -v
```

A measured batch used 20 public prefixes from archived champion games at turns
12, 34 and 60, depth 3, eight common plans per legal root and 32 rollouts per
plan. It produced 28,416 trajectories and 85,248 independently checked turns.
CPU/CUDA root values, common plans, recommendations and every joint action
matched exactly. The full trace digest was:

`8e7b5c8224e617560b7778e444f4a265ce5cf41c53ac587e6fa032904b1e732b`.

Measured on the local RTX 5070 Ti Laptop GPU and one PyTorch CPU thread:

| Work | CPU | CUDA |
| --- | ---: | ---: |
| Public policy + physics + trace transfers | 1.772 s | 0.495 s |
| Independent standard-library replay | 7.535 s | 7.516 s |
| Entire in-process worker function | 10.772 s | 9.726 s |

The CUDA core was about 3.58 times as fast in this batch. The complete verified
worker was only about 1.11 times as fast: independent CPU replay dominated the
elapsed time. Total function
time includes prefix reconstruction, tensor setup, transfers, synchronization,
public policy, physics and independent replay. It excludes process launch,
PyTorch import, JSON input parsing and final file serialization. Peak PyTorch
GPU allocation was 252,325,376 bytes, about 241 MiB; display/driver allocations
are separate. Other machines and smaller batches can favor CPU execution.

The measurement used `gpu_batch.py` SHA-256
`1a15460f1ba38b31a701322683423d642f1e9d358a92a398238cac1683bbbc8b`.
Its 20-job canonical input-list hash was
`b0642b8b2d8738a78822bcf3a64e6a9f2ce350c88df58f8e82ec2c8c972ceac9`.
The inputs were generated by selecting archived `stay_guarded_resilient` row
`(i*29) % count` for `i=0..19` from `validation/official/followup_results.json.gz`
and exposing only the focal prefix before the selected turn. No future tape or
opponent metadata was included in a worker job.

The verifier copies each trusted reference-produced public board once per turn
and shares its immutable cells across four player views. Incoming job data still
undergoes complete validation. This avoids redundant validation without exposing
private fields to the scalar policy. Its optimization preserved the complete
action trace and every value from the earlier, slower verifier.
