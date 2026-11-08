# Independent pre-scale review

**Decision:** the corrected pipeline passed pre-scale review for one bounded
training generation with one owner process and its mandatory independent audit.
This establishes tested readiness for that stage, not zero bugs, completed primary
games, BMCTS coverage, GPU acceleration, or a stronger deployed bot. Development
and final execution remain unimplemented and reserved.

Reviewed runtime source:

- `core.py`: `6d0de2dae757a4db821bddbb6bad1978bd6f6ac4d612ac60946b2ff01412d6fa`
- `run.py`: `bcaeeba986b4cdfd663be0a34bd507a93ee45db3f24ee4c80c8b60a4b1b7e98b`

Changing these files invalidates this source-specific review and existing
campaign guards until a new version is explicitly reviewed.

## Blockers found and corrected before a 20,000-game run

1. **False audit aggregates could bypass the barrier.** The old gate checked
   flags, hashes and declared totals but did not derive actual transcript and
   actor-audit coverage. Self-consistent empty files could claim approval and
   unlock another generation. The corrected gate reads every unique task,
   replays physical outcomes, recomputes fitness, checks individual actor-audit
   bindings and exact coverage, and derives credited counts from those records.

2. **A field label did not prove its rivals were correct.** Changing a planner
   into a weak wanderer, or changing seeds, styles or genomes, could pass after
   merely recomputing identity hashes. The corrected validator reconstructs each
   complete expected rival specification from its immutable campaign context and
   compares the actual specification with that recipe.

3. **Catalog labels could disagree with their scope.** A coherently resealed
   mechanics catalog could claim a full-primary profile or swap held-out and
   training phase labels. The corrected loader derives profile, counts and
   generations from the shape; checks campaign identity and required sources;
   verifies phase order/index/seed derivation; and reproduces every map.

Eight independent adversarial regression tests pass. They execute **zero campaign
games**. Their deliberate false claims are disposable test inputs and must never
be admitted as games. Reproduce with:

```powershell
python -m unittest primary_campaign.test_audit_review -v
```

## What is verified

The full plan has 8,000 training, 1,000 development and 1,000 final maps, each with
200 episodes. Maps are unique under rotation as well as by exact contents, use
mirrored 1–3 values, and are separated from known historical boards. Their custom
distribution is not a claim about the organizers' unknown sampling probabilities.

A standard training generation assigns 100 maps × 200 episodes **once**, rather
than taking an eight-candidate cross product. Each of eight immutable candidates
gets 2,500 games. Every candidate covers all 64 field/corner/token cells 39 or 40
times; fitness gives those cells equal weight. All candidates visit all maps.
An independent planning probe found 24–26 games per candidate per map, with small
map-family exposure differences. Map and family uncertainty therefore remains;
the fitness does not also normalize by map family.

Rival assignment is shuffled independently from public actor input, with three
fresh context-bound rival instances per episode. Different parameters and seeds
are not different algorithms. The finite league contains related architectures,
so these games cannot establish universal strength against unknown entrants.

Actual decisions use the existing public-only evaluator: a fresh namespace per
actor/game, independent copies of exactly four public inputs, simultaneous
pre-action observations, legal-action checks, deadline measurements and
post-decision referee-only memory checks. Private counters validate decisions
afterward; they are not policy features. No Torch policy or GPU proxy is used.

Each completed generation must regenerate every actor decision and compare every
turn in two referees before its fitness can breed another generation. Individual
audit records bind the exact task, candidate, row hash, source versions and
callback count. Promotion is disabled. Training rank selects research parents,
not a production replacement; source logic outside numerical CONFIG is fixed.

Checkpoints preserve an interrupted final append before retrying its task.
Malformed complete records, duplicate tasks, changed sources, wrong assignments
and incomplete stages fail acceptance. Completed resume revalidates existing
evidence rather than resubmitting work or rewriting its results.

The corrected small-profile integration test executed **800 actual games** and
regenerated all **256,000 decisions** in two referees. Its immutable audit credits
**zero primary games** because it is a mechanics test. Completed resume submitted
no work and changed no evidence; the next generation was prepared only after
approval. Its evidence is under `.cache/primary-executor-mechanics-7955xgkj/`.

## Conditions and remaining work

- Use one generation owner at a time. There is no exclusive execution lock;
  concurrent invocations can duplicate work and later fail closed on duplicate
  records. That wastes compute even though the results cannot be accepted.
- Freeze and archive the exact reviewed sources before a long stage. Partial
  records are not accepted primary counts; a completed independent gate is
  required. Audit replays are not additional primary games.
- Local actor-audit checkpoints are outputs of the trusted independent runner.
  External laptops must not be allowed to supply pre-approved audit claims.
  Returned games require independent owner-side action regeneration and referee
  checks before acceptance; primary distributed ingestion is not implemented.
- Report performance by map family, rival behavior, corner and token, as well as
  the aggregate. Selection noise and repeated adaptive search are expected in
  training. Reserve untouched evaluation after the final choice and do not keep
  sampling until a favorable significance result appears.
- Final generalization should include withheld opponent implementations and
  adversarial exploiters, not just fresh weights on familiar controllers.
- Development/final execution, complete campaign accounting and BMCTS audits are
  pending. A two-million-game schedule is not two million completed games.
- The measured 800-game test used four CPU workers: approximately 31.9 seconds
  for play and 37.8 for independent audit. Its roughly 48.4-hour full-run linear
  projection excludes unimplemented stages and BMCTS and is not a completion
  promise. Measured stage storage projects to roughly 12.3 GB before additional
  retained versions and backups. Recheck actual throughput, disk space and
  deadline violations as worker counts or hardware change.

The production incumbent remains unchanged. No new candidate is declared best
or promoted by this review.
