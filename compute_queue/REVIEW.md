# Independent queue review

The local diagnostic prototype passed eight independent boundary/retry tests
after the implementation's own nine tests. Reviewed `queue.py` SHA256:
`314e00e643a21b5cb8240be0180343ee18367ad30b2c9895f603cec8e3c600f2`.

**Scope:** localhost functional readiness only. The coordinator binds to
`127.0.0.1`; no public HTTPS host, tunnel, remote installation or real WAN path
was created or tested. This is not evidence that automatic sharing across your
friends' separate networks is ready. Existing offline remote diagnostics are a
separate workflow.

## Findings corrected before this review passed

- `Store.claim()` previously allocated a second task when a lost response caused
  the same worker to retry. That could strand leases and starve another worker.
  It now renews and returns that worker's existing live lease with the same nonce
  and payload. A second worker can still claim a different queued task.
- Prefix reconstruction previously ran before heartbeat renewal began. A valid
  expensive prefix could outlive its lease before computation started. Renewal
  now covers source checks, prefix validation and numerical execution.
- Malformed task/lease JSON types could reach SQLite and become HTTP 503 retries.
  Exact hexadecimal identity checks now reject them as HTTP 400 before binding.
  The implementer also tightened worker credential/configuration validation and
  rejects unknown top-level result fields before storing them.

## Checks that passed

The independent suite covers claim retries, cross-worker and stale-lease access,
malformed identifiers, actual localhost bearer authentication, strict JSON,
hidden/executable job fields, unexpected result fields, heartbeat timing, and
an intentionally forged numerical result. The forged value was quarantined only
after the real default owner-side CPU evaluator recomputed the task with full
independent scalar verification. The heartbeat test uses a mocked transport only
to test control flow; it does not certify a computed result.

Source pins cover the coordinator and imported project algorithms. Jobs contain
bounded public opening histories, own accepted actions and search settings.
There is no remote enqueue/admin endpoint, executable command, source download,
module selection, file destination or path used from an incoming job. Labels
such as job IDs are data, not filesystem paths. SQL uses bound parameters.

Assignments require the authenticated worker and its lease nonce. Accepted and
quarantined results remain bound to their assignment. Semantically identical
result retries are idempotent; conflicting returns cannot replace an accepted
result. An expired lease cannot overwrite a reassigned task. SQLite transactions
serialize assignment, and verification is performed by one owner thread.

Each proposed numerical result is recomputed on the owner CPU before acceptance.
Values, policy/source metadata, traces and counts must match; worker-reported
device descriptions and timings are not hardware or performance proof. The
public-only integer rollout model responds to counterfactual boards and keeps
focal plans common across hidden support samples. It remains an open-loop
diagnostic with an uncalibrated support distribution, not full BMCTS or an
optimality certificate.

All queue accounting explicitly grants **zero primary campaign games** and
**zero full-BMCTS games**. No accepted diagnostic is automatically ingested into
training or deployed. No protected primary/evolution runtime file was changed by
this review or its fixes.

## Reproduction and remaining conditions

Run with the verified PyTorch environment:

```powershell
python -m unittest compute_queue.test_review -v
```

The Windows tool environment required approved loopback access for the HTTP
tests; the restricted first attempt failed with WinError 10013. With local socket
access, all eight checks passed. This was an execution permission issue, not an
accepted test failure or a code correction.

The implementer's real integration additionally used two persistent local
processes, CPU and CUDA, handling two tasks each and independently verifying all
four results. It is a functional check, not a distributed throughput benchmark.
Full owner recomputation can be the bottleneck and does not establish a speedup.

Use one coordinator process per database. Public hosting needs a separate
reviewed HTTPS deployment, connection/timeout/rate limits, credential handling
and a real remote test before being represented as WAN-ready. Do not expose the
stdlib server directly or share one worker configuration among several laptops.
