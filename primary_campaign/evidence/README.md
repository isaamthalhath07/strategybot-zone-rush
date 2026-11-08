# Primary campaign evidence

`accepted_stages_000_001.json` records the first **40,000 independently accepted
actual games**, out of the planned 2,000,000. The `train_000/` and `train_001/`
folders contain byte-for-byte copies of the sealed summaries, audits and their
fingerprints. Across those two stages, all **12,800,000 actor callbacks** were
regenerated and every physical turn was checked in two referees. Audit replays
are not added to the actual-game count. Neither stage promotes a policy.

Complete registrations, action transcripts and individual actor-audit logs
remain in `.cache/primary/campaign_v1_20261109/`. Their hashes are bound by the
copied audits; the small published receipts do not replace those raw logs or
independently reproduce them. The existing `primary_campaign` audit commands
validate the complete local evidence before later training uses its fitness.

The top-level `primary_train_000_summary.json` is an earlier compact presentation
summary. For the exact source summary and its checksum, use
`train_000/summary.json` and `train_000/summary.sha256`. The live review and
next-generation review describe their stated snapshots, not the latest run
completion status.

The incumbent led both completed stages by the registered standardized pairwise
metric. These comparisons use fresh, unpaired rival instances. They are training
results; they do not establish superiority on the reserved development/final maps
or across all possible opponents. The production bot remains unchanged.

The 800-game mechanics archive tests the executor and its failure handling. It
has zero primary credit. GPU diagnostic receipts and runtime performance tests
are separate evidence and also grant zero primary or full BMCTS credit. Full
BMCTS and the heldout executors remain unfinished.
