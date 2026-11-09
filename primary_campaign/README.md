# Primary campaign: actual current-policy games

This is separate from the paired evolutionary control experiments. The fixed
plan contains 10,000 seeded maps and exactly 200 games per map: 2,000,000 games.
The existing guarded bot and bounded mutations of its numerical CONFIG are the
actual focal players. No GPU proxy policy supplies results.

| Split | Maps | Games | Availability |
|---|---:|---:|---|
| Training | 8,000 | 1,600,000 | 80 independently audited generations |
| Development | 1,000 | 200,000 | Reserved; executor not implemented |
| Final | 1,000 | 200,000 | Reserved; executor not implemented |

The training runner is implemented. Full campaign completion cannot be claimed
until the reserved splits have their own frozen-policy executor and all requested
audits finish. BMCTS is not implemented here; its audit counter stays zero.

Each training generation has 100 maps, 20,000 actual games and eight candidate
files. Every candidate receives exactly 2,500 games, with 156 or 157 games in
each seat/token crossing. The field schedule also balances seat/token crossings
and gives every candidate all 64 field/seat/token outcome cells. Selection uses
the equal-weight mean across those cells, followed by mean score and source hash.
The comparisons use new opponents rather than paired opponents. Additional fresh,
paired controls remain necessary before promoting a candidate.

Every primary game gets three newly seeded rival instances with unique IDs bound
to campaign, map, episode and seat. These are varied instances of the registered
algorithm families, not millions of independently written algorithms. Opponent
identities, seeds and private counters never enter the actor's four-field view.
All four actions use the same pre-move state. A fresh module namespace is created
for every player in every game.

Catalog maps are distinct even under quarter-turn rotation, including across
training/development/final. Previous official and evolutionary control maps and
their rotations are excluded. The catalog records each map's reproducible seed,
distribution family and content hash. Stress distributions retain their labels.

Execution and independent acceptance are separate. A generation's actual games
are recorded with all 80 action lists, scores, timings and source identities.
An independent implementation then regenerates every player's decision and
compares every physical turn in two referees. The next generation cannot use
fitness until the actual complete transcript and individual audit coverage have
been verified. Audit replays are never added to the primary-game count.

All registration, transcript, summary and audit hashes must agree. Source edits,
missing tasks, duplicate tasks, changed opponents, score corruption, hidden
fallbacks and missed deadlines reject the stage. Only a torn final append can be
recovered; its original bytes are retained. Completed evidence is not overwritten.
This is a trusted local research evaluator. Process-isolated promotion checks and
independent review remain separate. The production bot is never modified here.

From the repository root:

```powershell
python -m unittest primary_campaign.test_core -v
python -m unittest primary_campaign.test_executor -v
python -m primary_campaign.run --directory .cache/primary/full_001 --initialize-only
python -m primary_campaign.run --directory .cache/primary/full_001 --prepare-only
```

The second test runs an explicitly labeled 800-game mechanics profile and 800
independent audit replays. It admits **zero** primary games and retains its
evidence and observed disk/throughput measurements under `.cache/`.

After independent review, a bounded training run can use:

```powershell
python -m primary_campaign.run --directory .cache/primary/full_001 --train-generations 1 --workers 6
```

This executes one of the 80 planned generations. Increasing the bounded generation
limit resumes prior stages and requires each previous stage's independent audit.
It never shrinks the two-million-game manifest or automatically promotes a bot.
Use one coordinator per campaign directory. Distributed CPU execution and remote
GPU coaching are not implemented by this runner.
