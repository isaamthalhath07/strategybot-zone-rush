# Unchanged-evidence integrity cache

This new package is inactive until the root owner explicitly publishes and seals its prospective amendment. It edits no frozen module and does not run a callback or GPU operation during import. Real authority/certificate operations require separate operator authorization; development tests use only synthetic data and an in-memory fake MAC.

The API is `publish_amendment(campaign, authority)`, `IntegrityCache(campaign, authority).create(stage_name)`, `cache.read(registration, stage_directory)` and `run_phase(cache, action)`. Supported phase actions are `freeze`, `development`, `final` and `fallback`; there is no training adapter. Stage names are exactly `train_NNN`, `development` or `final`. Cache objects and authority objects remain in the root process and never enter worker commands or source archives.

After source review/publication and explicit owner authorization, the operator can use the existing Python environment:

```text
python -m deadline_finalization.cache amend
python -m deadline_finalization.cache certify --stage train_000
python -m deadline_finalization.cache certify --stage train_001
python -m deadline_finalization.cache freeze
python -m deadline_finalization.cache development
python -m deadline_finalization.cache certify --stage development
python -m deadline_finalization.cache final
```

Certify every completed TRAIN generation before cached freeze. Certification performs the original complete validation once; it does not reuse an unverified claim. An owner can advance certificates as each generation completes while the original training process continues. Certify the completed DEV panel before invoking cached FINAL. Every fresh cohort still uses the untouched original `_execute` and its full verifier. There is no automatic recreation of missing or failed certificates.

`python -m deadline_finalization.cache profile-tree --stage train_000` only scans proof bytes and prints counts/digest. It does not load an owner key or create a certificate. Optional analysis reports may be added without changing proof inputs; any other unexpected stage member or failure receipt requires operator investigation.

Certificates and the amendment reside under the existing campaign's `finalization_integrity` folder. The original manifest, registrations, accepted receipts and execution artifacts are never rewritten. Once the amendment is sealed, adapter non-test source files must remain unchanged. A missing, altered or foreign certificate raises an error. Use the original complete validation path or the already validated fallback according to the unchanged phase rules; never consume a partial cache.

The source and method contract is detailed in `AMENDMENT.md`. Unit tests confer no execution, qualification, admission or promotion credit.
