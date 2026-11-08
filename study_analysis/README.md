# Frozen architecture study reporting

This separate tool reports the completed four-arm V2 architecture study. It executes no matches, actor callbacks, physics replays, audits, qualification, tuning or promotion. It grants zero primary and BMCTS credit.

The tool refuses partial results, including the eight gold/qualification originals. Before computing any ranking or interval it requires:

1. The exact frozen V2 registration, SHA-256 `b5ffb74f5c8ad1c7a984a54d41d86efb26cb99ae2318a8b7d5a631d23ad24eb9`, and its original source/map/fixture/statistical validation.
2. Owner-master authentication of the fixed canonical study-acceptance pointer, accepted controller result, original plan and study binding, with their exact hash/path/campaign/role/count relationships.
3. Accepted complete physical replay and independent declared-slot peer-audit assurances, exactly 32,768 extra originals, the eight gold cases counted once, and zero primary/BMCTS/promotion/qualification-replica credit.
4. The exact authenticated `games.jsonl` hash and every unique registered map/source/field/seat/token/opponent fixture once. It checks the complete 80-turn action shape, final integer score-derived pairwise result, fault-free status and callback timing structure. A missing, duplicate, foreign, reassigned, malformed, torn, faulted or changed row rejects the entire report.

Authentication uses the existing private owner registry. No key is copied into jobs, outputs or metadata. HMAC authenticates the trusted owner's acceptance; it is **not** cryptographic proof of computation or physical-host independence. This tool relies on the already completed actor/two-referee audit rather than repeating it. It does not freshly prove a transcript's physics or decisions. The owner acceptance binds the exact streamed bytes that are analyzed.

Use a fresh report path, after the canonical study has been completely accepted:

```powershell
python -m study_analysis --registration .cache/confirmation/architectures_v2_001/registration.json --registry OWNER_PRIVATE_REGISTRY_PATH --output .cache/study_reports/architecture_v2_report.json
```

No real study report has been generated during implementation. The tests use an isolated, deliberately synthetic unit authority and fake score/action rows. They do not access real V2 outcomes or execute the archived bots. Their test-only registration digest and source-validation stubs cannot authorize a different registration in the production entry point.

## Preregistered arithmetic

The result reports all four arms in registered order, all four fields per arm, each worst-field mean, integer pairwise histograms, raw focal scores, zero accepted faults and recorded timing. It reports all six first-minus-second contrasts; there is no automatic winner selection.

Pairwise wins award 1 for beating a rival and one half for tying. Internally every game is an integer numerator 0..6. Observed means and differences, raw-score means and bootstrap endpoints are reduced exact rational fractions, with decimal conveniences alongside. Complete balancing makes the overall mean equal to the equally weighted map/field/seat/token mean.

The frozen plan specifies 60,000 whole-map bootstrap replicates, seed 202611091740 and descriptive Bonferroni tails at zero-based indices 249 and 59749. Each replicate draws 128 map indices with replacement using `random.Random(seed).randrange(128)`, in registered map order, and uses **the same map draw for all six contrasts**. It preserves all fields, seats, tokens, rival parameters and all four focal arms together. Integer replicate contrast sums are sorted before selecting the fixed tails. The report records a digest of the shared draw sequence and the explicit algorithm.

“Worst-field contrast” can describe two different quantities, so both are reported: the difference between each arm's worst-field mean, and the minimum of their four paired field differences. Every individual field difference is also shown. Field comparisons are descriptive point estimates; no extra simultaneous field-interval claim is added.

The intervals are approximate descriptive map-cluster bootstrap intervals, not a finite-sample familywise guarantee, universal superiority proof or release authorization. Recorded timings span owner/helper hardware and changing process/load allocation; they are not a hardware-normalized policy-speed ranking.

## Verification

```powershell
python -m unittest study_analysis.test_report -v
```

Tests include a full synthetic 32,768-row acceptance, partial/role/credit/assurance corruption, real HMAC wrong-owner/purpose/tampering, canonical-pointer/binding mismatches, missing acceptance, duplicate/missing/foreign/malformed rows and exact rank/timing checks. Arithmetic examples use the full 60,000-replicate procedure and verify exact shared-map cancellation, known anticorrelated-map tail endpoints and the two worst-field definitions. All testing executes zero real games.

The report is written only after all checks and statistics succeed. Original campaign registrations, acceptance files, controllers, bots, source freezes and public handoffs are read-only.
