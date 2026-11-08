# Useful compute sharing: current limits and proposed GPU research queue

This is a design under review, not a released worker or a new validation claim.
Existing Batch 2 packages and their full CPU return verification remain unchanged.

## What the measured pilot establishes

The RTX 5070 Ti Batch 2 return contains eight public positions, 46,080 simulated
paths and 276,480 future turns. Its reported function time is 19.515 seconds:
17.553 seconds for scalar CPU verification, 0.914 seconds for the tensor
policy/physics phase including trace transfers, and 0.602 seconds for tensor
setup/transfer. The owner then repeats the complete calculation on the CPU.
This is useful correctness evidence, but it is a poor sustained GPU architecture.
It neither executes the current Python policy for full matches nor offloads the
primary campaign. A larger copy of this job preserves its verification bottleneck.

## Immediate real workload

The current production policy uses Python history inference and branching route
search. CUDA physics alone does not port that policy. Source-pinned workers can
execute the actual existing match tasks on helper CPUs. For the extra four-policy
study, a different declared physical helper then regenerates every actor decision
and checks both referees; the owner checks all physical records, authenticated
coverage and preregistered canaries. This offloads both original play and most
actor regeneration under an explicit cooperative-team trust model. HMAC does
not prove physical independence or prevent collusion. The older primary path
still performs its full owner audit: remote primary admission is not implemented.
The separate `distributed_campaign/` implementation documents these boundaries.
No synthetic search path may be counted as a primary match.

## Before allocating hours of GPU search

The existing GPU diagnostic samples common open-loop plans against simple
responding rival models. Many sampled continuations can be poor, and their
nonterminal projected-income rank is a heuristic. More samples can reduce
sampling variance without fixing model error or missed plans. Observation-tree
search in `tree_coach/` addresses a different limitation, but is currently CPU
reference code. Neither is a demonstrated stronger policy.

First run a bounded usefulness experiment: choose public positions from accepted
training games using a preregistered, balanced schedule. Give the coach only the
opening view, own accepted past actions and subsequent own public views. Evaluate
its recommendation by reconstructing actual controller histories and playing
complete counterfactual continuations, with every rival responding to changed
boards. Recorded future actions must never be replayed after a deviation.
The evaluator may inspect referee truth; the coach must not receive it.

Such an experiment measures hindsight performance against those sampled rival
instances, not Bayes-optimal play or fresh-map strength. Teacher suggestions
remain research proposals. A deployable change needs fresh complete-game
controls, strict runtime checks and independent confirmation.

## Candidate sustained GPU protocol

If that usefulness gate passes, use a persistent process, chunked offline queues,
atomic per-task results and resumable manifests. Reuse the existing verified
PyTorch environment and CUDA context. Inputs remain bounded public prefixes;
the queue never carries executable commands, actual rival seeds or future tapes.
Plan useful task counts and durations from measured throughput, rather than
artificially repeating completed work to keep GPUs busy.

An alternative to repeating every calculation on the owner's CPU is deterministic
replication on two different helper slots, plus independent CPU audits selected
unpredictably after both returns are committed. Matching source, input, numeric
and trace fingerprints would grant a **replication-checked provisional teacher
label**, not full independent CPU verification. A mismatch quarantines the task
and its containing returned batch. The original unverified inner result must
retain its unverified flag. This would be a distinct protocol and assurance tier;
it must not be accepted by the existing full-verification reader.

Replication detects disagreements but does not prove independent logical
correctness: both replicas share code, and collusion is outside this cooperative
team trust model. Post-commit random CPU audits can bound the chance of missing
a specified fraction of incorrect tasks, not guarantee zero errors. The exact
sample, population, sampling seed commitment and acceptance rule must be
registered and reported. Source/physics parity tests, periodic canaries and
quarantine remain required. Primary match acceptance must retain its full audit.

This document does not implement a GPU assurance change or a large GPU queue.
The separate `gpu_tree_coach/` prototype now tests actual observation-branching
tensor search and optional CUDA Graph execution against exact scalar trees.
That parity and measured throughput do not establish better decisions. The
earlier eight-position causal usefulness probe found no pairwise improvements,
so a sustained teacher allocation still needs a stronger usefulness result.

## Other architecture choices

* A faithful tensor port of the existing policy could accelerate its real
  decisions, but must reproduce history inference, planning branches, tie rules
  and full action histories. Physics parity does not establish policy parity.
* A learned policy trained on GPUs is a new candidate. Public-only features,
  history handling, imitation error, runtime, single-file packaging and fresh
  playing-strength validation need their own evidence. It cannot be called the
  existing bot running on CUDA.
* CPU match distribution plus separately validated GPU coaching is the practical
  incremental architecture. It preserves current-policy fidelity while testing
  whether additional search or learned candidates merit more compute.
