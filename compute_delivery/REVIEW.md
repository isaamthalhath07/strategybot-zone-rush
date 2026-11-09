# Independent delivery review

Current status: **revised Windows extraction path independently passed all
42 tests in 10.321 seconds, with zero skips**. A later root reproduction had
found intermittent Windows `WinError 5` in the previous directory-publication
implementation. Earlier passing runs below are historical. Their exact source
and receipt are preserved in
`evidence/history/outer_delivery_v1_before_rename_retry.zip`; the new source
version and reviewed delta are identified below.

Review scope: the new outer Windows delivery packaging only. The frozen
distributed controller, worker, authentication, policy files, actual plans,
qualification gold and private owner material must remain unchanged. Tests must
use explicitly synthetic mocked admission and execute zero actors or matches.

## Admission before packaging

A PLAY delivery must come from `distributed_campaign.control._load()` and a
peer-audit delivery from `_audit_plan()`. Those paths authenticate the existing
owner plan, exact registered study, qualified runtime, target helper, task
coverage and, for audit, the original creator and different physical auditor.
The outer builder must select one admitted shard rather than create a plan,
repartition a study, generate gold or retag a qualification bundle.

Both the selected inner archive SHA and its bundle-manifest SHA must match the
authenticated distribution. The archive is copied byte for byte. Displayed
work role, task count, source registration, shard ID and runtime must agree with
that selected bundle; PLAY means new assigned original matches, AUDIT means
replaying existing matches. Neither grants primary or BMCTS credit.

## Archive and filesystem boundaries

The frozen inner ZIP legitimately contains `bundle.json`, every path in its
`files` table, `bundle.sha256` and `RUN_INSTRUCTIONS.txt`. Reject additional
entries, missing entries, duplicate or case-insensitive aliases, absolute/drive
paths, traversal components, backslashes, Windows device names, trailing-dot or
space aliases, links/reparse points and excessive expansion. Validate the whole
archive before publishing an extracted job. Existing extracted content must
match its immutable job identity rather than be silently overwritten.

The outer package needs only its launcher, pinned wrapper files, public delivery
metadata and that one unchanged inner ZIP. It must not recursively copy an
owner folder, registry, credential, private key, another helper's bundle,
existing results or Python environment. Paths from a job are data; they cannot
select arbitrary executable commands or return-file destinations.

## Runtime and first setup

Find and probe an already installed interpreter. Exact approved runtime means
the frozen fingerprint of implementation, version, full version, executable SHA
and platform. Equal `3.12.x` text alone is insufficient; a virtual-environment
Python can have a different executable hash from the qualified global Python.
Failure should request requalification, not relax the fingerprint or reinstall
Python globally. CPU policy work requires no new CUDA/PyTorch installation.

The selected executable launches the inner package in its own directory.
Inherited Python import-path overrides must not select another checkout.
Credential setup uses the existing reviewed import/private-permission helpers
and caches only that helper's credential outside transferable results. It does
not read owner registry/key material, mint a replacement identity or put a
credential in a process-pool actor argument.

The worker's immutable signed header includes its worker count. Resume must
preserve that count for a job, along with the selected executable and identity;
silently recalculating concurrency can make a valid checkpoint incompatible.
Do not run two wrapper processes against the same job/results directory.

## Progress and results

Live progress must distinguish completed worker tasks from owner acceptance.
Only an allowlisted results archive is returned: `header.json`, `records.jsonl`
and `progress.json`, bound to the exact job. Credentials, `.cache`, `.venv`,
source code and unrelated files must never be swept into that ZIP.

An interrupted or failed worker is not a completed delivery. Preserve its
checkpoint for the same job's resume; do not invent successful records, shrink
the assignment or count retries as additional matches. A completed return still
requires the existing authenticated owner/peer validation. Packaging and a
passing synthetic wrapper test are not compute, physical independence or
playing-strength evidence.

## Revised extraction path

The review of the revised launcher found no remaining blocker within its
declared Windows scope. Instead of `os.replace`, source activation now uses
Windows `os.rename`, which refuses an existing destination. The wrapper makes
at most five attempts, with configured waits totalling one second, only for
native Windows errors 5, 32 or 33. These are retry candidates, not a diagnosis
that antivirus or a temporary lock caused every such failure.

Before every attempt, it rechecks path containment and link/hardlink/reparse
status, the authoritative ZIP and manifest, the exact fresh staging file and
directory set, every registered source hash, and all auxiliary file bytes. A
destination that appears before or during an attempt is preserved and rejected.
Source/auxiliary tampering and unexpected files stop activation. Permanent or
unrelated errors preserve the complete staging tree; they do not cause a
permission change, a silent repair, an unbounded retry or actor startup.
Production activation on non-Windows fails closed because the standard POSIX
rename primitive would not supply the same exclusive-directory guarantee.

The new regression controls include injected errors 5/32/33 followed by actual
native publication; source/auxiliary replacement and hard links during retry;
an existing or racing destination; permanent error limits; unrelated errors;
outside staging paths; and non-Windows no-retry behavior. Both control flow and
native filesystem behavior are exercised. The full run also repeated the prior
Windows CMD/PowerShell, header/context, runtime, sentinel and result-only checks.

Reviewed revised fingerprints:

| File | SHA-256 |
|---|---|
| `runner.py` | `c7c7dff3bd10fb2fdfa62d7f8bb374649d5ccc59111c0aa9d529502a42e08a5a` |
| `test_independent.py` | `7ef93d4df2ca3046cce963ecb32b85c60691226333c4e9d731c84915dc18aa9c` |
| `test_extract_retry.py` | `d31d5f49f639e4448a82e2fa2729837a40127bf6a65f4e53d9103dede55fd2e7` |
| `test_runner.py` | `5310d55c9b0bb93bf8c86f3e49e651ad8bcb1b90e984eeca02268681a0a1c8b8` |

The builder and launcher template fingerprints in the historical table below
are unchanged. The old `evidence/validation.json` is preserved byte for byte as
a historical run, not rewritten to claim the extraction fix was tested then.

```powershell
python -m unittest compute_delivery.test_runner compute_delivery.test_independent compute_delivery.test_extract_retry -v
```

This is a finite isolated wrapper test result, not a guarantee that every
future Windows filesystem error will recover. No real plan, job, qualification
gold, actor or private credential was created, executed or altered by the review.

## Earlier validation (historical)

**An earlier bounded local review passed after fixes.** That combined run passed
all **25 tests in 7.133 seconds**, with no skips: seven implementation checks and
18 independent adversarial checks. This includes actual Windows CMD/PowerShell
package preflight in a path containing spaces, `%` and `!`, positive startup and
nonzero failure propagation. No actual actor, game, owner plan, qualification
gold or private credential was executed, created or loaded by these tests.

The tests deliberately mock owner admission and use comments-only synthetic
worker files and fake local result authentication. They establish wrapper
behavior, not real cryptographic admission or a completed helper workload. Real
admission remains the unchanged authenticated controller/worker responsibility.

Findings corrected before the review passed:

- The first export implementation could truncate an unrelated file at its
  expected return filename. Returns now use content-addressed names, reject
  links/hardlinks/reparse points, publish atomically without overwrite, and
  reuse only identical bytes. A later valid progress snapshot creates a new
  return while preserving the previous archive.
- Signed header and progress context checks now cover role, campaign,
  generation, shard, expected/completed counts and zero primary/BMCTS credit
  before exporting. A correctly shaped but wrong-context signed result is not
  presented as complete.
- A stream/UI error previously left the child coordinator running. Owned
  worker processes now have a separate process group and are stopped/reaped on
  an exceptional stream exit. The isolated regression uses a fake process and
  verifies the cleanup path; no game task was started.
- Lock paths reject link aliases. Nested slot metadata is validated before it
  forms a private-cache path. Exact LF and CRLF SHA sidecars are both accepted
  without relaxing the authoritative archive/manifest hash.

The independent suite additionally verifies selected PLAY versus peer-AUDIT
admission, unknown shards, qualification relabel attempts, byte-changed inner
ZIPs, path traversal, Windows aliases, duplicate/casefold entries, link headers,
expansion caps, altered extracted sources, exact runtime fingerprints, rehashed
runtime overrides, credential/environment exclusion and immutable existing
return sentinels. The final Windows run exercised real hard-link rejection;
the earlier restricted run had skipped that filesystem operation and is not
the result used for this approval.

Reviewed source fingerprints:

| File | SHA-256 |
|---|---|
| `builder.py` | `66c1e1369b785c90198f65362ac55e8f11d38f2ca593ec8acc7079eba37ab478` |
| `runner.py` | `852fd8a4e0d10fd9cdd35276cd25814de161a0575093edc9a564ca12071d50c0` |
| `START_HERE.cmd` | `a1c9a3ff4f9164fd80556f827a462623c4085f47ffa74ff34582a0e4dc2cab01` |
| `START_HERE.ps1` | `124ff56a495bcc30194d6438470b8318bb777fa12fc96633691782bff88b3d14` |
| `test_independent.py` | `743f5fd19691dd59ef1244a781fc4bfadddfd2910c83314af84e0d4e1b05c1bd` |
| `test_runner.py` | `c2cd51e4c8fcf076accc0717f7607a3070343b49f467d1451b2d0589caa4c2da` |

Reproduce with normal local Windows file/process permissions:

```powershell
python -m unittest compute_delivery.test_runner compute_delivery.test_independent -v
```

The earlier pass did not expose the subsequently reproduced directory-activation
failure; it is not the final qualification of the revised launcher. Neither the
earlier checks nor the new review issue a real assignment or bypass qualification,
different-slot peer audit, owner acceptance or a root review of the concrete
handoff. Helpers still need the owner's authentic package and published archive
fingerprint. No Internet service, actual remote workload or strength result is
established here.
