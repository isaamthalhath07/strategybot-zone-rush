# Held-out executor design

This package adds evaluation without changing any frozen primary/evolution
runtime. It must not execute live held-out games during implementation/testing.

## Fixed protocol

1. Require every scheduled training stage, not the latest completed stage.
   The full profile requires all 80 × 20,000 actual accepted games. Call
   `primary_campaign.core.validated_audit` for every stage and additionally bind
   its directory index to registration/summary/audit generation, exact catalog
   slice and globally disjoint tasks, maps and rival identities. A copied stage
   must not count twice.
2. Take exactly the eight registered candidates, in registered order, from the
   final scheduled training stage. Preserve the incumbent. No manual shortlist,
   cross-generation ranking, new mutation or post-development adaptation is
   allowed. Verify each body equals `GenomeSpace.export` of its audited genes,
   which preserves all non-CONFIG policy logic. Seal the shortlist and metric
   before creating a development registration.
3. Development uses only the catalog's 1,000 development maps: 200,000 actual
   games, 25,000 per candidate. Split into ten 100-map stages, reusing the balanced
   assignment/field recipe. Carry occurrence offsets across blocks so whole-phase
   corner/token/field counts remain balanced. Generate rivals with the original
   campaign identity and global map index; they are disjoint from training.
4. After every development stage is complete and independently audited, aggregate
   all development results by the 64 corner/token/field cells. Choose exactly one
   winner by equal-cell pairwise mean, then raw mean score, then ascending source
   hash. Seal this choice before creating any final registration.
5. Final uses only the catalog's 1,000 final maps: 200,000 games for that one frozen
   policy. Final outcomes never alter selection, policy or deployment. There is
   no automatic promotion. Mechanics profiles use their declared smaller phases
   and always grant zero primary credit.

Each phase stage executes the existing public-only `runner.play_game`. Acceptance
requires complete unique actual task coverage, legal/deadline records, physical
replay, exact recomputed summaries and fresh regeneration of all four actors in
two referees. Partial files and declared aggregate flags never grant credit.
Append recovery preserves an interrupted tail; source drift, complete corruption,
foreign tasks, opponent substitutions and incomplete audits fail closed.

## Local evaluator authority and cached gates

Deep replay of all 1.6 million training games on every resume would be excessive.
Admission therefore deep-validates once, then authenticates a complete artifact
manifest with a fresh 32-byte HMAC key held only in the owner's ignored `.cache`.
The key is exclusively created, restricted to the current owner, never logged,
passed to workers, committed or bundled. The signed payload binds every raw
training registration, summary, audit, game log, actor-audit log, policy export,
catalog/manifest and sidecar, exact shortlist, source/runtime pins and stage index.

Every block/resume verifies the MAC with constant-time comparison and re-hashes
every bound raw file; it does not trust sizes, modification times or a rehashed
unsigned approval. The cache is a local trusted-evaluator attestation, not an
independent third-party proof. Local owner access is the trust boundary.

Missing keys or invalid caches stop execution. Explicit recovery must deep-validate
all source evidence again and reproduce the same immutable shortlist/selection
before creating a new key/gate version. Prior keys and gate artifacts are never
overwritten. No silent key replacement may bless an old approval. Final selection
gets an equivalent authenticated binding to all audited development evidence.

## Test scope

Targeted tests will reject missing/forged/copy-repeated training stages, unsigned
or rehashed gates, lost/replaced keys, changed raw files, foreign/drifted policies,
phase/map/rival substitutions, early final execution, empty/tampered results and
non-idempotent completed resume. Small control-flow fixtures may mock expensive
training admission, explicitly giving no primary-game credit; real bounded actor
checks remain separate. No new 800-game or live development/final run is required
until the design has been independently reviewed.
