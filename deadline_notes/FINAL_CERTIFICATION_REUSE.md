# Reuse of a fully verified FINAL certificate

Read-only source review confirms that the existing reviewed
`deadline_finalization.cache.IntegrityCache` API supports the stage name `final`.
After an actual, complete, fully admitted normal primary FINAL stage, the root
may explicitly call `IntegrityCache(campaign, authority).create('final')` once,
before preparing the separate official-generator check. If DEV chose the anchor
and no FINAL stage exists, skip certification; the existing no-final-needed
branch does not request a FINAL proof.

Creation checks the exact canonical registration, candidate/rival bytes,
configuration and CPU runtime; fingerprints the complete proof tree before and
after; and invokes the unchanged full primary acceptance and durable-output
validation once. It adds no callbacks, physics steps, games or admission credit.
The authenticated certificate is written under `finalization_integrity/final.json`.
An existing certificate cannot be overwritten or automatically recreated, and
failed or changed evidence cannot be recovered through this operation.

The existing official-check `primary_context` detects that certificate and uses
`IntegrityCache.read` on subsequent reconstructions. Each read rehashes every
bound proof byte and checks the exact file/directory set, source/configuration/
environment, owner receipts and parsed summary/aggregate bindings. This avoids
reparsing the raw proof rows; it does not skip their byte-integrity checks or add
fresh actor replay coverage. The original primary decision remains unchanged.

Certification time is spent before the official-check preparation availability
decision and is therefore reflected in the remaining wall-clock time. The fixed
official availability rule, complete 8,192-game requirement, 10:58:00 UTC cutoff,
and 1,500-second reserve remain unchanged: 600 seconds for setup/admission/analysis
plus 900 seconds for ending primary-proof reconstruction and final read-only
verification. No rate, outcome, gate or policy parameter changes are authorized
by certificate reuse.

This is a prospective operational note about existing APIs, for publication
before DEV. This review performed no owner operation, certification, callback,
physics step or game and changed no runtime source.
