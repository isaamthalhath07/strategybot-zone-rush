# Independent local analysis integration review

Seven bounded independent CPU tests pass. Review and fixtures read no actual
study outcomes, partial game files, rankings or private registry. They invoke no
CUDA probe, actor, controller, qualification or original-match execution.

Review caught a blocking producer/consumer mismatch: the frozen CUDA runner
adds `source_closure_sha256` and `registration_snapshot_sha256` to each row's
proof, but the initial analyzer rejected those fields. The correction changes
only this analysis package. A regression derives the complete proof field set
from the frozen runner's source AST and accepts the exact current schema.

The analyzer now binds those hashes to the correct selected batch snapshot,
runner source closure, sealed header and summary. It checks accepted rows
against the raw batch games file and all 80 recorded action/hash-link events.
The selected snapshot contains only that batch's ordered fixtures and preserves
the full original schedule's separate count/hash; it is not mislabeled as the
unchanged complete registration. An actual-plan metadata-only regression checks
all 32,768 registered identifiers, skips the eight noncontiguous gold identifiers
exactly, and verifies the frozen batch size of 256: 127 full batches and one
248-lane batch, for 128 batches. No outcome file is opened by that check.

Source review confirms qualification and acceptance field names match the
current frozen controller. Analysis checks owner HMAC purposes, the canonical
binding/output, exact registration/source/runtime/qualification links, all
eight exact authenticated CPU-original gold rows, all 32,760 CUDA-original
proofs, per-row owner audit hashes and complete ordered unique coverage.
Original candidate arms, backend attribution and source-specific oracle counts
are checked. A copied registration, changed authority, rehashed protocol drift,
incomplete admission or missing row cannot authorize partial reporting.

The runtime's 49-file source recipe is reproduced by static source reads,
without importing CUDA or either execution controller. Tests reject wrong
fixture arms, Boolean/float coverage substitutions and malformed proof hashes.
A partial synthetic games/audits pair never reaches bootstrap arithmetic.

All six comparisons use the unchanged old pure map-bootstrap implementation:
60,000 shared draws, fixed seed, registered map order and zero-based percentile
indices 249 and 59,749. An analytic two-map constant-offset test independently
checks every contrast's mean and interval endpoints. The complete-cohort
denominator is twice 8,192 games per arm; each field denominator is twice 2,048.
Field contrasts and differences between worst-field means remain distinct.

This is a new local owner-admission report adapter. HMAC authenticates trusted
owner declarations; it does not certify host honesty, GPU execution or physical
independence. The analyzer performs no new physics/actor replay. Reports remain
descriptive, grant no new primary or BMCTS credit and perform no promotion.

Validation: `python -m unittest local_cuda_analysis.test_independent -v` passed
all seven tests in 0.760 seconds with no skips. The reviewed report source is
`acfb40e28abb83a4a0ef16c37ec39022a46b974a860d46d38c2e7ab4195e9598`.
Actual complete-study evidence remains required
before an actual report can be produced.
