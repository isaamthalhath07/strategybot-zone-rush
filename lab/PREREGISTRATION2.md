# Pre-registration of the second out-of-sample test (EXT2)

> **Status: in force.** Committed before any EXT2 test game was played. The commit that
> adds this file is the timestamp. Nothing below may be changed after results are
> seen; anything done differently will be listed under "Deviations" in
> `lab/PROGRESS.md`.

## Why

`zr6` is the shipped root `bot.py`. Its own out-of-sample test (EXT1, section 8 of
`lab/PROGRESS.md`) showed it level with the best older bots against strong unseen
opponents. Generations 3 and 4 (`lab/PROGRESS.md` sections 10 to 13) were built to
fix that. Every number for them so far comes from opponents that have been seen.
EXT2 is the only opponent set nobody has looked at. This test decides whether the new
candidate replaces `zr6`, and it also reports the `zr6` replication that the first
pre-registration deferred.

## Frozen candidate

`lab/cand/zr8.py`, SHA-256
`4b472af34b2a7109b91122dba0e90ae872e108b0eb68a66d63e91c14559f5be0`.
Built by `python3 lab/build.py zr8 gen=4` from `lab/cand/_head4.py` and
`lab/cand/_tail4.py`.

What it changes relative to `zr6`, all developed on seen opponents only:

1. Generation 3 (`zr7h`, section 10): the risk on an un-upgraded cell is a constant
   rate per rival once that rival is in range, with a per-rival posterior over three
   raider types; "claim and upgrade without leaving" is one job.
2. The home cell carries no raid risk (section 12).
3. The Shield decision prices a turn without crediting stays already banked, and does
   not charge a lost cell to a backfire in the last four turns (section 13).

Tried and left out because fresh development seeds showed no gain: value-aware
routes, pricing a claim as exposed for a fixed lag, a softer penalty after a
side-step, casting a stay early to save a banked stay.

Before freezing, `zr8` passed all 27 rows of `lab/robust.py` and `lab/audit.py`
(no exception, no illegal action, worst call 8 ms).

## Focal bots (identical fixtures for all)

`zr8` (candidate), `zr6` (shipped), `zr7h` (generation 3 without the section 12 and
13 changes; reported, takes no part in the rule), `a_novel_b_racer`,
`a_novel_b_blocker`, `cur_e8` (the release before `zr6`).

## Opponents: EXT2 and the second half of the stress bots, never used for anything

Fields as built by `final_test.test_fields("EXT2", "zr8")`:

| Field | Bots | What |
|---|---:|---|
| `ai_pasted` | 10 | pasted ChatGPT and Gemini bots |
| `generated` | 27 | generated families EXT1 never showed, and rival types |
| `other_designs` | 8 | the strong unseen designs |
| `stress` | 7 | the stress bots not used in EXT1 |
| `unseen_mixed` | 52 | all of the above, mixed |
| `with_candidate` | 12 | the strong unseen designs plus four copies of `zr8` |

The only earlier contact with any of these bots is the single timing game recorded
under "Deviations" in section 8 (one EXT2 bot, `zr6`, no decision taken from it).

## Maps, seats, rules

Exactly as in the first test: 48 maps per field, 4 fixtures per map (192 games per
field per bot), map families alternating between the seven used in development and
the seven added for testing, fixture seed 6203 + field index, the confirmed rules
everywhere plus the five alternative rule readings on `unseen_mixed` (16 maps each).

Command:
`python3 lab/final_test.py --set EXT2 --focals zr8,zr6,zr7h,a_novel_b_racer,a_novel_b_blocker,cur_e8 --out lab/results/test_ext2.json`

## Measures

Rivals outscored per game (0 to 3). Differences are paired on identical fixtures with
95% bootstrap intervals that resample whole maps. "Pooled" is the five disjoint fields
`ai_pasted`, `generated`, `other_designs`, `stress`, `unseen_mixed`.

## What development predicts (written down so the result can be compared with it)

On seen opponents, `zr8` minus `zr6` on fresh seeds: strong +0.37 (seed 1900; the
generation 3 draft gave +0.10 and +0.32 on seeds 1200 and 1900), mid +0.02,
weak -0.04, mixed +0.01. The known price of generation 3 is a few hundredths against
passive farming bots, because it raids their exposed land less. So the expectation
is a clear lead on `other_designs`, about level elsewhere, and a small pooled lead.

## Shipping rule

`zr8` replaces root `bot.py` only if all of these hold:

1. **The purpose:** on `other_designs`, `zr8` minus `zr6` has its lower bound above 0.
2. **Overfitting check:** that lead is at least +0.13, half of the mean development
   lead on the strong field over fresh seeds ((0.10 + 0.32 + 0.37) / 3 = 0.27).
3. **No overall loss:** pooled, `zr8` is not significantly below `zr6` (upper bound of
   the difference at or above 0).
4. **No large local loss:** in no field is `zr8` below `zr6` by more than 0.08 with
   the upper bound below 0.
5. Pooled, `zr8` minus Racer and `zr8` minus Blocker both have lower bounds above 0.
6. Zero faults by `zr8`, zero games that failed to run; under each alternative rule
   reading zero faults and not significantly below `zr6`.

If any of 1 to 6 fails, `zr6` stays as `bot.py`. EXT2 is then spent: a later candidate
would have no untouched opponents to be judged on, and that will be said plainly.

## Also reported, whatever it shows

- The deferred `zr6` replication: `zr6` minus `cur_e8`, Racer and Blocker on every
  field and pooled.
- `zr8` minus `zr7h`, the out-of-sample value of the section 12 and 13 changes.
- `with_candidate`, known and new map families, and each rule reading.

## Not allowed

- Changing `zr8` after seeing EXT2 and reporting EXT2 again as if it were clean.
- Dropping a field, a map family or a focal bot after seeing its result.
- From this run on, EXT2 and all stress bots count as seen.
