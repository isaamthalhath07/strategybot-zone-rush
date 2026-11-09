# Independent validity and overfitting oversight

This reviewer is separate from candidate generation and selection. It does not
edit the champion or choose a replacement. A failed audit blocks promotion; a
passing audit establishes the listed checks for recorded games, never a promise
that all bugs or all possible counterstrategies have been eliminated.

Run the independent audit from the repository root:

```powershell
python -m evolution.oversight .cache/evolution/discovery_001 .cache/evolution/confirmation_001 --workers 6 --output evolution/evidence/oversight_001.json
```

The default checks every game and regenerates every actor decision. The optional
`--physics-only` mode omits decision regeneration and reports that lower count;
it must not be represented as a complete actor audit. This tool reads result
data and pinned local source files, never executes commands supplied by results,
and never modifies the evaluated policy or its results.

## What the independent audit checks

- Registration fingerprints; pinned candidate, rival, evaluator, and referee
  sources; unchanged incumbent; exact candidate logic outside numerical CONFIG.
- Strict JSON parsing, no duplicate keys or non-finite numbers, complete unique
  candidate/fixture task coverage, three properly assigned rivals per game,
  unique opponent instance identities, and content-hashed mirrored 1–3 maps.
- All corner/token crossings per map and field/corner/token balance across maps.
  Discovery and confirmation must have disjoint map contents and rival IDs.
- Every recorded action is legal in both separately maintained referees. All
  private physical state, incomes, legal action sets, and final scores agree
  after every turn. Round 1 pairwise outcomes and group summaries recompute.
- Every actor is rebuilt in a fresh private namespace. All four choose from the
  same pre-action turn, each receiving an independent copy of exactly the four
  documented public inputs. Every action must reproduce the recorded action.
- Input mutation and silent failure fallbacks invalidate a game. For supported
  memory trackers, the independent auditor checks exact own progress/scores and
  retained feasible cooldowns after each public decision. Referee truth is used
  only by this check and is never given to an actor.
- Recorded callbacks must be complete and finite. Recorded first-turn and normal
  decision maxima must meet 2,000 ms and 200 ms. This fast evaluator measures
  trusted code after a call; it cannot stop a hung call. A separate real worker
  process check is required before promotion.

These are additional evolutionary controls. Neither the original trials,
independent reruns, GPU physics probes nor worker equivalence checks receive
credit toward the planned two-million-game primary campaign or BMCTS audits.

## Initial selection decision

Discovery tested eight immutable versions on eight fresh boards. Its selected
mutant scored 2.3828 opponents outscored, compared with 2.3516 for the incumbent.
On 32 independent confirmation boards it scored **2.2451**, compared with
**2.2500** for the incumbent. The paired confirmation difference was −0.0049,
with a 32-map clustered descriptive 95% interval [−0.0635, +0.0527].

**Promotion is blocked.** The confirmation does not establish an improvement.
The discovery advantage was selection evidence, and the later reversal is
precisely why the champion must survive independently of the mutation winner.
The confirmation set is now consumed and must not become a reusable final test.
Further mutations may learn from it only as development data; a new finalist
then requires new untouched confirmation data.

The first full audit passed **2,048 games / 163,840 turns in both referees** and
regenerated **655,360 actor decisions** exactly. The original audit and its exact
auditor source are retained in `evidence/`. Its addendum independently recomputes
all paired statistics and verifies the corrected 32-game process proof. The
addendum supersedes an outdated original blocker saying no mutant had received
a worker test: the mutants did receive that mechanics check, but their strength
was not confirmed. Both records retain the **blocked promotion** decision.

The current custom map mixture is an explicitly registered test distribution,
including rich-home and uniform stress maps. It satisfies the mirrored 1–3
constraints; it does not prove the distribution matches the organizers' unknown
map-generation probabilities. Similarly, fresh rival instances and seeds do not
mean every rival has a novel algorithm. Several share implementations, and
performance against this finite league is not universal exploitability evidence.

## Matched-input process checks

The fast reference engine and vendored referee expose the same legal action set
in different orders. The rules do not specify that order. A seeded random rival
can legitimately select different actions if the list order changes. Exact
reproduction therefore requires matching all public inputs, including order;
changing only the order is a separate robustness experiment.

The isolation helper explicitly matches the original fast evaluator's action
order and samples all four fields. These repeated fixtures check execution
mechanics, not fresh strength or generalization. An early helper recorded default
load/watchdog metadata instead of its actual overrides; that artifact must remain
historical, and corrected proof must record actual settings and source pins.

## Ongoing stop conditions

Stop and quarantine a trial if its registration changes, any record is missing
or duplicated, referees disagree, an actor action cannot regenerate, a hidden
input reaches the policy/search model, a deadline or legal-action check fails,
or a candidate relies on private opponent identities, seeds or future actions.
Investigate an apparently large gain by field, map, corner, token, opponent family,
and timing before believing it. Preserve failures and abandoned evidence instead
of overwriting them. Repeatedly checking a holdout consumes it; repeated adaptive
selection requires fresh data and appropriately cautious statistical conclusions.
