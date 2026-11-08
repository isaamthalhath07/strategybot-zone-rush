# Evolving the existing champion

The production `bot.py` remains the verified STAY-only guarded Transfer bot,
SHA-256 `e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5`.
These tools are offline research. They never deploy a candidate or change the
production file. The final submission still needs only Python's standard library.

## Architecture choice

Start with a population of numerical variants of the current economic planner.
Keep its public-input normalization, Shield rules, legal-action handling and
history accounting intact. Preserve several discovery elites and an archived
strong genome; breed sparse mutations, grouped mutations, crossover and archive
restarts. Each export changes only the existing bounded `CONFIG` assignment.
The three boolean correctness/planning guards are excluded from the genome.

| Approach | Benefit | Main limitation | Current role |
| --- | --- | --- | --- |
| Existing planner with evolved values | Reuses measured strength; small, auditable, fast exports | Cannot invent missing planning features; noisy selection can overfit | First implementation |
| Diverse league and historical specialists | Exposes weaknesses and reduces adaptation to one rival | A finite league is not a Nash-equilibrium certificate | Actual controls plus fresh instances |
| Public-history opponent forecasting | Can model future movements and targets | Wrong confidence can be worse than a simpler estimate | Next architectural experiment |
| Belief-aware tactical search | Tests move/Shield interactions and competing plans | Hidden-state correlation, model error, branching and 200 ms budget | Offline prototype in `search_coach/` |
| Full neural reinforcement learning | Could learn representations and use GPUs efficiently | High sample cost; transfer and standard-library export need proof | No replacement justified yet |
| Best-response or adversarial optimization | Finds exploitable habits and non-transitive matchups | Three omniscient coordinated rivals would model the wrong game | Independent specialist challengers |

League training is motivated by prior work such as
[AlphaStar's diverse league](https://deepmind.google/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/).
This implementation is a bounded evolutionary experiment, not AlphaStar or a
complete policy-space response-oracle solver. No architecture establishes an
absolute best bot against every possible opponent.

## Running and verification

From the repository root:

```powershell
python -m unittest evolution.test_evolution evolution.test_league -v
python -m evolution.league --directory .cache/evolution/my_league --rounds 4 --population 8 --discovery-maps 8 --confirmation-maps 32 --workers 6
```

Use a fresh directory initially; repeat the exact command to resume. Registered
code, populations, seeds and completed evidence are immutable. Interrupted final
JSONL appends are preserved before retry; complete-line corruption is rejected.
On this Windows machine multiprocessing and local process checks require normal
host process access; restricted execution can stall and is not evidence of a
policy failure. Stop only the identified test process before rerunning.

Each generation executes actual 80-turn games. Every player receives a private
copy of exactly the four starter fields, and every game has fresh module memory.
Rivals comprise varied bounded planners, independent racing/blocking policies,
and simpler wandering/farming/raiding/feinting behaviors. New instance IDs and
seeds mean new instances, not infinitely many new algorithms.

All decisions use the same pre-turn board. Private referee counters are used
only by an auditor after decisions, never by an actor or fitness feature.
Every candidate is checked for illegal output, input mutation, deadline
violations and hidden fallback. Public-history tracking is compared against
the referee after each call.

Before discovery can select parents, and before confirmation can produce a
challenge decision, `league.independent_gate` synchronously calls the separately
implemented overseer. It replays **every turn through two referees**, regenerates
**every actor decision**, checks source hashes and recomputes outcomes. A failed
audit stops the league before further breeding. See [OVERSIGHT.md](OVERSIGHT.md).

Discovery results alone determine the next generation. A selected challenger
faces fresh content-distinct maps and fresh rival instances; its confirmation
outcome never changes future mutation seeds or parent fitness. Every holdout is
consumed once. A positive descriptive confidence interval only creates a
reviewable challenge. Multiple rounds require a separate final untouched test
after the overall choice, plus process-isolated validation and a reviewed
decision. Production promotion is disabled.

Maps have 64 cells, values 1–3, and horizontal/vertical reflection symmetry.
The registered mixture mostly favors the centre, with labeled uniform/rich-home
stress strata. It satisfies the documented constraints but does not establish
the organizers' unknown probability distribution. Content hashes exclude boards
from earlier stages, including all previous official comparisons. Over four
maps every field gets all sixteen seat/token combinations.

## First completed experiment

Eight candidates played 128 common fixtures each: **1,024 discovery games**.
The selected crossover changed depth from 3 to 2 and late-upgrade weighting from
4.5 to 3.3705. It scored 2.3828 opponents outscored versus 2.3516 for the
incumbent in discovery. This apparent gain was not confirmed:

| Fresh confirmation, 512 games per policy | Mean opponents outscored / 3 |
| --- | ---: |
| Original incumbent | 2.2500 |
| Discovery winner | 2.2451 |

The paired difference was -0.00488, with a 32-map descriptive 95% bootstrap
interval [-0.06348, 0.05273]. The challenger was rejected. These figures belong
to this particular opponent distribution and are not directly comparable with
older campaign means.

The independent overseer validated all **2,048 games, 163,840 turns and 655,360
regenerated decisions**. A separate matched-input process check reproduced 32
games / 10,240 callbacks exactly, covering all four fields. Its corrected proof
records actual watchdog/load settings. Earlier failed/superseded verification
artifacts are retained, not rewritten.

## Counting and the two-million-game plan

These paired selection and confirmation games are **extra research controls**.
They contribute zero to the primary two-million-game campaign and zero BMCTS
audits. Replayed games, unit-test games and synthetic GPU physics probes also
receive no primary credit. Completed primary games and completed search audits
must be tracked separately.

The requested primary budget remains **10,000 distinct seeded maps × 200 games**.
The map generator and scheduling tests cover that size, content uniqueness and
balanced seats/tokens. The distributed execution/search pipeline still needs
an end-to-end worker and independently verified returned results. Infrastructure
readiness must not be confused with completion of that campaign.

The first shared-compute tools are in `compute_share/`; GPU physics validation
is in `training_gpu/`. The current Python policy is not a tensor policy. Physics
throughput alone cannot predict current-bot or BMCTS throughput, and a surrogate
policy cannot be counted as this bot without demonstrated action equivalence.
