# Pre-registration of the out-of-sample test

> **Status: in force.** The candidate is frozen at the hash below. No test game had
> been played when this was committed.

Written and committed **before any test game was played**. The commit that adds this
file is the timestamp. Nothing below may be changed after results are seen; anything
done differently is listed under "Deviations" in `lab/PROGRESS.md`.

## Why

Every number for the candidate so far comes from opponents it was designed against.
The question this test answers is whether its lead survives against bots, maps and
rule readings it has never met. In the real competition every opponent will be a bot
some other team built with an AI assistant, and none of them is in this repository.

## Frozen candidate

`lab/cand/zr6.py`, SHA-256
`8b87bf8221c5937fc3bd51562850a6ac550a0cec49681640332b19c4ea0144cb`.

Built by `python3 lab/build.py zr6` from `lab/cand/_head.py` and `lab/cand/_tail2.py`.

What this session changed relative to the previous session's `zr4`, using
development opponents only:

1. Deployment safety (`zr5`): move-for-move identical to `zr4` on the documented
   interface, passes all 27 rows of `lab/robust.py`. See `lab/PROGRESS.md` section 4.
2. One setting (`zr6`): `hazard` 1.0 to 0.8. The development sweeps show the score is
   flat from 0.6 to 1.0 and falls steeply above 1.0, so 1.0 sat on the edge of a
   cliff. 0.8 is inside the plateau and is no worse on any development field on a
   fresh confirmation run. The reason is robustness, not a development gain. See
   `lab/PROGRESS.md` sections 6 and 7.

Nothing else was changed. In particular the prior over landlords' Shield habits was
left as the previous session set it, although the sweep shows it is worth about 0.3
against strong development bots: whether that prior carries over to strong bots
outside development is exactly what the `holdout_elite`, `other_designs` and
`stress` fields test.

## Reference bots (play the identical fixtures)

- `cur_e8`: the shipped root `bot.py`.
- `a_novel_b_racer`, `a_novel_b_blocker`: the two best existing bots in the
  history-wide ranking.
- `zr5`: the candidate before the hazard change. Reported so the effect of that one
  change can be seen out of sample; it takes no part in the shipping rule.

## Opponents: none used in development

| Field | Who | Origin |
|---|---|---|
| `holdout_elite` | 5 bots | `fields.HOLDOUT_ELITE`, drawn by the previous session before design. Not independent: includes Feint and a Blocker seed clone. |
| `holdout_rest` | 14 bots | `fields.HOLDOUT_MID` + `HOLDOUT_WEAK`. |
| `ai_pasted` | 10 bots | Pasted from ChatGPT and Gemini (`opponents/` on the `combined` branch). Never in `lab/pool`. |
| `generated` | 21 bots | Six procedurally generated families the pool has no member of, plus three evolution-league rival types. |
| `other_designs` | 9 bots | Zenith, three human-like exploiters built to beat Apex, four "outsider" designs written from the rulebook, one independent farmer. |
| `stress` | 7 bots | Written for this test (`lab/stress_base.py`): landlords that never shield, shield on sight, a stay early or at random; raiders that feint, swarm level-1 land, wait for cooldowns or strike only late. |
| `unseen_mixed` | 47 bots | All of the external and stress bots above, mixed. |
| `unseen_all` | 66 bots | `unseen_mixed` plus the lab hold-out. |
| `with_candidate` | 18 entries | The strong unseen bots plus four copies of the candidate: what if another team built something like it. |

The external bots are `lab/ext/` (85 files, `index.json` records each origin and hash).
`lab/make_ext.py` split them once with seed 20261111 into **EXT1** (40 bots, used here)
and **EXT2** (45 bots, a reserve nobody looks at until EXT1 is decided). Generated
families were split whole, so EXT2 holds six families EXT1 never shows. Before the
test, each external and stress bot played smoke games against development bots only,
to confirm it loads and never faults; the candidate was not in those games.

## Maps, seats, rules

- 48 maps per field, 4 fixtures per map (one per seat, token start rotating):
  192 games per field per bot.
- Maps alternate between the seven families used in development and **seven new
  families added for this test** (`flat`, `centre`, `edges`, `stripes`, `checker`,
  `sparse`, `rich`). All map seeds are new (fixture seed 5101 + field index).
- Rule readings: the confirmed rules everywhere, plus five alternative readings of
  the referee's flags on the `unseen_mixed` field (16 maps each).
- Opponent triples, maps, seats, tokens and opponent random seeds are identical for
  all focal bots, so every comparison is paired.

Command: `python3 lab/final_test.py --set EXT1 --out lab/results/test_ext1.json`

## Measures

Score: rivals outscored per game, 0 to 3. Differences are candidate minus reference
on identical fixtures; intervals are 95% bootstrap intervals that resample whole maps.
"Pooled" means the seven disjoint fields `holdout_elite` to `unseen_mixed`.

## Shipping rule

The candidate (`zr6`) replaces root `bot.py` only if all of these hold on EXT1:

1. Pooled, candidate minus `cur_e8`: lower bound above 0.
2. Pooled, candidate minus Racer and candidate minus Blocker: both lower bounds above 0.
3. No field in which the candidate is significantly below any reference (upper bound
   below 0).
4. Candidate minus `cur_e8` is positive on the known map families and on the new ones.
5. Zero faults by the candidate and zero games that failed to run.
6. **Overfitting check:** the pooled lead over `cur_e8` is at least half of its
   development lead on the mixed development field (+0.32, so at least +0.16).
   A lead that shrinks by more than half out of sample counts as overfitted.

Then:

- All six hold: ship `zr6`, and run the identical plan on EXT2 as a replication.
  Report EXT2 whatever it shows.
- 1 holds but 2 fails: the candidate beats the current bot but not the best existing
  ones. Ship whichever focal bot has the highest pooled score and passes every row of
  `lab/robust.py` (wrapping it if needed), confirmed on EXT2.
- 1 fails: do not ship the candidate. Any redesign is judged on EXT2 only.

Under the alternative rule readings the candidate must record zero faults and must not
be significantly below `cur_e8` in any of them.

## Not allowed

- Changing the candidate after seeing EXT1 and reporting EXT1 again as if it were
  clean.
- Dropping a field, a map family or a reference bot after seeing its result.
- Re-running with other seeds until the numbers look better.
