# Separate official-generator release check

This new package freezes a metadata-only panel before DEV, then permits exactly
one separate release check after the unchanged primary final decision. It edits
no existing runtime or evidence. It never fits a source, changes parameters,
extends a sample or grants old primary/BMCTS credit. See `METHOD.md` for the
fixed conditional-orbit interpretation, gate and availability rule.

The frozen public map artifact is `evidence/maps_001.json`, SHA-256
`37c54f68d6b78694d7cb7abab106c04c58e3ee9ae9030629daffc7e24119cc2e`.
It contains 64 official-generator maps accepted after 113 deterministic seed
attempts, excluding 10,218 prior/reserved orbits. The exact generator source,
all metadata input hashes, per-member consumed-spec hashes and complete
accept/reject ledger are recorded. No actor calls or outcomes were involved.

Only the root owner may run the following stages. `amend` and publication
authorization must both precede DEV; the actual comparison follows primary
FINAL. The root must review and publish the exact tool/plan before authorizing.
There is no automatic invocation, key generation or remote capability. The
existing owner authority is loaded only by explicit CLI commands and is never
sent to actor or audit workers.

```powershell
python -m deadline_official_check.experiment amend
# Root reviews/publishes this method, map artifact and sealed owner plan.
python -m deadline_official_check.experiment authorize-publication --published-commit <40hex>
# After the original primary final decision, use its exact selected source:
python -m deadline_official_check.experiment prepare --selected-path <source.py> --selected-sha256 <64hex>
# Only after root explicitly launches the separate check:
python -m deadline_official_check.experiment execute
python -m deadline_official_check.experiment verify
```

All commands accept `--campaign`; it must be the existing canonical primary
campaign with its exact existing owner authority. Library equivalents take `(campaign, authority)` and `prepare` also
takes the exact `{path,sha256}` source entry. `registration`, `availability` and
`endpoint` expose the pure metadata/synthetic-test interfaces. Importing the
package runs no actor, CUDA physics, source callback or actual study.

The generic frozen CUDA pipeline and read-only durable verifier remain unchanged.
The plan is a new format/role and labels new official map origins explicitly;
it does not masquerade as a reserved old cohort. Every original retains full
320 callbacks, 80 turns, both CPU referees and a fresh independent 320-callback
replay. Failed claims are never resumed or automatically retried. Source drift,
incomplete coverage and altered owner roles/receipt hashes reject admission.

If the selected body is already e8, no redundant games run. If a complete 8192
match comparison plus all audits cannot fit the fixed timing bound, 600-second
setup/admission headroom and additional 900-second primary-proof reserve
(1500 seconds total) by 10:58:00 UTC, no callbacks run and the primary validated source stays
selected with official-generator-unconfirmed scope. Once started, failed,
incomplete or late work falls back to old e8. Complete work uses the fixed
whole-map bootstrap gate; partial outcomes never choose a smaller panel, retry,
extension or source edit. The primary final receipt is never rewritten.
Only the normal fully authenticated primary DEV/FINAL path enables this
extension. Emergency primary fallback records extension unavailable and retains
that fallback with unconfirmed scope. The key-free historical anchor reader
pins the published public quad report; it never opens an old private registry.
Primary reconstruction reuses unchanged cache/full durable validation without
adding actor replay coverage. Its elapsed setup and ending admission cost is not
treated as free or replaced with kernel-only throughput.

Author tests are metadata and synthetic-score/receipt checks. Passing them is not
execution, qualification, empirical strength or admission evidence.
