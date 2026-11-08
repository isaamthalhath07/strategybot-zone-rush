# Proposed primary continuation

[ADR-001](ADR-001.md) specifies a new protocol for the same original two-million-match goal. It preserves the existing 100,000 admitted matches and exact catalog, supports source-family-aware evolution after the four-arm result, and separates new primary admission from the EXTRA-control transport.

This directory contains design and read-only planning checks. It has no executor, live MAC authority, candidate exporter, architecture selection, development gate or deployment action.

The remaining allocation is 75 training stages / 1,500,000 matches, followed by the original 200,000 development and 200,000 final matches. The exact last eight registered candidates of global stage 79 form the development shortlist. Development freezes one final candidate; final outcomes never tune it.

`contract.py` checks the unchanged ten-thousand-map catalog, closed-form slot assignment, source identity, prospective rival-seed uniqueness and cross-version slot conflicts. It recognizes the four exact reference sources only. It grants neither mutation/runtime approval nor primary credit. A fresh focal instance is not a claim that the original focal policy was secretly reseeded.

Run the bounded checks with:

```text
python -m unittest primary_migration.test_contract -v
```

Validation passed 13 tests in 4.234 seconds. It compared all 100,000 existing fixture assignments and 300,000 legacy rival seeds, validated catalog bytes, checked lossless seed indexing above 64 bits, and checked development/final **planning descriptors**, without executing any actor or match. Adversarial checks reject a rehashed replacement catalog, copied/gapped legacy declarations, assignment substitutions, hidden planning fields, reused catalog slots and unregistered source bodies. Local evidence tests skip explicitly in a clean checkout without ignored campaign artifacts; pure planning tests still run.

The evidence snapshot records existing artifact hashes and declared original admissions. It is not a new actor replay or authenticated admission receipt. An actual bridge requires independent review, original receipt/provenance checks, the canonical campaign lease, a terminal-owner handoff and a separate owner evaluator authority.

The next live work remains the frozen four-arm EXTRA study and its source-specific qualification. No stage 5, heldout outcome or architecture choice is triggered here.
