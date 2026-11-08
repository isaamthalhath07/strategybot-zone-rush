# StrategyBot — Zone Rush



A bot for **Zone Rush**, the four-player territory game used in StrategyBot

(ARC × Coding Club, AFKAR 2026, IIT Delhi — Abu Dhabi).



`bot.py` is the submission: one self-contained file, standard library only,

exposing `act(state)` exactly as the starter kit defines it.



Everything else here is the workshop that produced it — a rules engine, an

opponent zoo, a tournament harness, an evolutionary tuner, and a GPU self-play

track that was tried and rejected.



---



> **New here?** [`EXPLAINED.md`](EXPLAINED.md) explains the whole thing from
> scratch — the rules and the arithmetic behind them, every strategy anyone could
> play and what each one actually does, every file in the repository, and the four
> methodological lessons that decide whether any of the numbers below mean
> anything. This readme assumes you already know the game; that one does not.

## Latest round: four branches, one field, one fused bot

**`bot.py` now ships the fused bot**, not v7. The full critique, every
measurement and every fix are in [`CROSS_BRANCH_REVIEW.md`](CROSS_BRANCH_REVIEW.md).
In short:

- **All four branches were put on one field** (`crossfield/xfield.py`). It
  groups opponents by *author*, attributes pairwise credit per opponent inside
  mixed lineups, uses six map families from both generators and both
  `legal_actions` conventions, and scores ties the Round 1 way. The three
  independent rule implementations in the repository agree exactly over
  32,000 turns.
- **The research branch's evolved economic planner is the strongest decision
  policy here**: +0.215 PW over this branch's v7 on 1,200 fresh paired games
  (z = +8.0), and never worse against any author's opponents. The independent
  branch's v7 does worse than this branch's v7 on a neutral field, even against
  its own author's opponents.
- **Nothing tried on top of the evolved planner's decisions survived
  confirmation.** That covers symmetric tie-breaks, exact tracker cooldowns, the
  finalist genome, seven single-gene probes, and predicting exact copies of public
  bots (built, then rejected: near-relatives go unrefuted for 60–79 turns, so
  identification is unsafe).
- **What the evolved planner lacked was everything around it.** It has no
  exception handling at all. On five of eleven plausible server-interface
  variants it scores what the do-nothing skeleton scores. So does this branch's
  v7, and the independent v7 fails on six.
- **The fused `bot.py`** (`fusion.py` + `econ.py` + `mybot.py`, built by `ship.py`)
  plays move-for-move like the evolved planner on the documented interface. It
  keeps this branch's tracker and walk planner as a warm standby, and adds input
  normalisation, planner isolation, board-based new-game detection, a cold-start
  rescue, a shield-cooldown gate and online movement-convention calibration. It
  passes all eleven interface variants, holds 96% of its score if module memory
  is lost every turn, and holds 100% on a server with NORTH/SOUTH swapped, where
  every other branch's bot keeps 17–33%.
- **Ten fixes in `mybot.py`, `engine.py`, `ship.py` and `runtests.py`.**
  Among them: an off-by-one that valued a last-turn capture at nothing, a clock
  that reset in all-home openings, a flat-board parse that played STAY all game,
  shields burned on rivals standing on an uncapturable home, a crashing
  `python ship.py`, and Round 2 tie rules in every Round 1 number.

The sections below describe v7 and the work that produced it; the walk planner
they describe is the fused bot's standby.

## v9: forecasting rivals by Bayesian goal inference

**v9** is v8 plus one switch, `forecast: 1`. It is no longer the shipped bot. On
the twelve novel opponents described below, the research branch's evolved
planner, which the fused `bot.py` plays like, beat v9 by **+0.19 PW** over 700
paired games (z ≈ +3.5), and by +0.25 PW (z +3.6) on the peer field. On the
strangers field the two were level (−0.007). v9 stays as the forecasting work
and as a fallback; this builds it to `bot_route.py`:

```bash
python ship.py route v9_params.json
```

### The problem

Every earlier version sees the whole board but never asks where a rival is
*going*. Its opponent model was the tuning field itself: weights fitted against
bots written in this repository. That is overfitting by construction. It knows
how the bots it trained against behave, not how a stranger will.

### The method: infer each rival's goal from its own moves

`Forecaster` in `mybot.py` is inverse planning. Nothing in it is fitted to any
opponent pool; each rival's belief is learned from that rival's own moves, in
the current game.

- **Prior:** every cell's value as a target *from the rival's seat and
  position*, by the arithmetic the bot applies to itself: points the work earns
  per action-turn it costs.
- **Evidence:** a noisy-rational move model. Each step either brings the rival
  closer to a candidate goal, holds, or takes it further away.
- **Structure from the rules:** rivals re-plan every turn, so the belief is the
  *current* prior times recent evidence. A stay that finishes work starts a fresh
  goal; a stay mid-work marks the current cell as the goal.
- **Forecast:** each rival's likely destination and arrival turn, chained two
  targets further out.
- **Use:** the walk planner discounts any work on a cell a rival is forecast to
  stand on first.

The constants were fixed on principle before any measurement and never tuned:
β = 2, ρ = 0.9, κ = 3, a two-target chain.

### Can it see where rivals are going?

On the held-out field (eight outside designs plus the repository's strangers),
over 11,268 forecasts of moving rivals:

| forecast | finds the rival's next destination | position error 8 turns ahead |
|---|---|---|
| **goal inference** | **48.0%** (P(true) **0.088**) | **2.17 cells** |
| rule prior alone (no inference) | 48.1% (P(true) 0.081) | 2.18 |
| "it stays put" | 1.1% | 2.54 |
| "it keeps going the same way" | — | 2.86 |

Most of the forecasting power comes from planning *from the rival's point of
view*; watching its moves adds calibration. Building this exposed three modelling
errors, each fixed and documented in the code: an action-level likelihood (2.5%),
ten-turn goal persistence (19%), and reading every stay as continuing work (16%).

### Does using it win games?

Paired against v8 on identical games. Fields marked † were re-drawn on fresh games
and pooled, because a single draw's best result is biased upward:

| field | pairwise wins | points |
|---|---|---|
| **unknown: outside designs + strangers, mixed (1,000 games)†** | **+0.050 ± 0.016 (z +3.1)** | +8.0 (n.s.) |
| outside designs (1,000)† | +0.030 ± 0.018 (z +1.7) | **+16.6 ± 7.5 (z +2.2)** |
| never-shield opponents (300) | +0.030 (z +1.5) | −6.5 (n.s.) |
| 3× `x_jackal`, the hardest outside design (120) | +0.033 (n.s.); cells lost **−19%** | +18.2 (n.s.) |
| peer, the strongest (400) | +0.014 (n.s.) | +2.6 (n.s.) |
| realistic (500) | −0.007 (n.s.) | +6.1 (n.s.) |
| **strangers (1,200)†** | **−0.024 ± 0.014 (z −1.8)** | −13.3 ± 6.9 (z −1.95) |

The gain is largest on the field closest to Round 1, mixed lineups of opponents
the bot was never tuned against, which is the point of the method. It does not
hurt against the strongest bots. It does cost a little against the repository's
own strangers. And it wins *pairings*, not raw points, which is what Round 1's Elo
counts.

**Tested against completely novel opponents.** Four independent agents, never
shown any bot in this repository, wrote twelve opponents from four design
families (`strategy_audit/novel/`).

- **They exposed the overfitting:** v8 scores only **1.43 of 3** against them,
  below average, where it had scored 2.6–2.8 on fields built in this repository.
- **v9 is the largest gain measured anywhere in the project:** **+0.100 PW
  (z +3.45) and +31.7 points (z +5.6)** over 1,200 games on that field, confirmed
  on fresh games.
- **Head to head,** v9 beats v8 against 8 of the 12 novel bots, and against copies
  of v8 and of v9 directly.
- **One design beats both versions:** `nv_b_racer`, which forecasts rivals itself
  and races only where it wins.

Details in [`strategy_audit/README.md`](strategy_audit/README.md) §15.

**Defence was tried too, and is off.** `fc_defend: 1` uses the forecast to reach a
threatened level-1 cell before the raider and upgrade it (shields cannot save
level-1 cells). Against a decision rule fixed before measuring, it cut cells lost
by about 12% in every one of 12 runs and was never harmful, but gained no
measurable pairings: +0.006 PW (z +0.8) over 1,000 games on the unknown field,
where the rule required z ≥ +2. Details in
[`strategy_audit/README.md`](strategy_audit/README.md) §14.

**If you want the conservative choice,** v8 is on branch
`claude/strategy-audit-v8`, and `python ship.py route v8_params.json` rebuilds it here:
`forecast: 0` reproduces v8 move for move.

## v8: fixes from the strategy audit

v8 is v7's tuned weights, unchanged, plus ten corrections found by an
adversarial audit of v7 against the rulebook. v9 keeps all of them. The audit,
its method, and every number below are in
[`strategy_audit/README.md`](strategy_audit/README.md).

```bash
python ship.py route v8_params.json
```

### What changed

Every fix sits behind a switch in `mybot.PARAMS`, and `v8_params.json` switches
them on. When v8 shipped, every default reproduced v7; since the merge with the
cross-branch review the defaults follow that review instead (see *Merged with
the cross-branch review* below). `strategy_audit/check_v7_compat.py` checks that
the v7 values still play **identically** to the v7 `bot.py` read from git history.

| switch | finding | what was wrong in v7 |
|---|---|---|
| `shield_l1: 0` | B2 | It spent shields defending **level-1** cells. A caught raider is frozen 2 turns and then needs 1 stay, while the shield is down for 4 (2 + 1 ≤ 4), so the cell falls anyway: **79–89%** were lost to the same raider within six turns. Upgraded cells (2 + 3 = 5 > 4) are still defended. |
| `shield_home: 0` | B3 | A rival standing on the bot's **home** was priced as a capture threat. Homes can never be taken; with a 2-point home the shield fired on every turn. |
| `last_shield_value: 1` | B4 | On turn 80 it shielded against *any* intruder, even ones that could take nothing, and ignored what its own last stay was worth. |
| `turn_guard: 1` | C2 | If state survived into a new game whose first turn was missed, the turn counter ran past 80 and the **whole game was played as its last turn**: 156 points against rivals' ~2,700. v8 scores 2,584 in the same scenario. |
| `calibrate: 1` | C3 | The cooldown (4) and freeze (2) were assumed. v8 reads the cooldown off its own `legal_actions`, bounds it from rivals shielding twice, and takes the freeze length from observed freezes. |
| `penalty_undo: 1` | C1 | A Round 2 time-penalty freeze (3 turns, §4.4) was read as a shield, so the bot believed a ready rival could not shield. v8 withdraws that inference once the freeze outlasts a shield freeze. |
| `solver_retry`, `backfire_prod`, `contest_owner`, `canon_home` | C4 | Smaller model and tracker corrections. |

### What it measured

Paired against v7 on identical games, never-tuned-against fields included:

| field | pairwise wins (of 3) | points |
|---|---|---|
| strangers (600 games) | −0.002 (n.s.) | **+7.2 ± 1.8 (z +3.9)** |
| peer (400) | +0.000 | **+3.5 ± 1.3 (z +2.8)** |
| realistic (500) | +0.008 (n.s.) | **+4.3 ± 1.9 (z +2.3)** |
| unknown: outside designs + strangers (400) | +0.010 (n.s.) | +3.2 ± 2.2 (n.s.) |
| eight outside designs (400) | +0.005 (n.s.) | +2.6 ± 1.7 (n.s.) |
| never-shield opponents (300) | +0.007 (n.s.) | +4.5 ± 3.6 (n.s.) |
| standard referee (300) | **+0.013 (z +2.0)** | **+6.2 ± 2.9 (z +2.1)** |
| referee counting cooldown or freeze one turn differently (300 each) | −0.003 to +0.030 | **+14 to +36 (z +2.3 to +4.3)** |

Points are positive in all eleven comparisons and pairwise wins are never
significantly worse. This is a robustness release, not a strength jump: the
largest gains are under rule readings that differ from the engine's.

### What was deliberately not changed

- **`q_weight`, the raid-shield prior (B1).** Learning faster gains 48 points
  against never-shield opponents but costs **0.111 pairwise wins (z −3.9)** on the
  peer field, where placements are actually contested. It stays at v7's value.
- **The one-turn-short income horizon (B6).** Real, but the tuned weights absorb
  it (fix measured +0.4 ± 2.3); it needs a retune, not a patch.
- **Turn-80 raid pricing (B5).** Field-dependent; 78% of last-turn raids succeed
  against this field.
- **`risk_frozen`.** Implemented, correct in principle, measured slightly worse;
  left off.
- **The bot's edge still depends on how the server counts the cooldown and the
  freeze**: under a referee that counts either one turn differently, v8 is still
  0.15–0.24 pairwise wins below its own standard-rules result. Calibration fixes
  the tracker, not the tuned weights. Ask the organisers, or retune on an engine
  that matches the server.

### Merged with the cross-branch review

The cross-branch review on `main` (`CROSS_BRANCH_REVIEW.md`) audited the same
`mybot.py` independently. It found some of the same faults and fixed them its own
way, without switches. Both sets of fixes are now in `mybot.py`. Where they
overlap, one switch has a value for each, and the **default** is the review's,
because `fusion.py` runs this planner with the defaults as its warm standby:

| switch | v7 | v8 / v9 | default (review) |
|---|---|---|---|
| `shield_home`: a rival on my home | 1: a threat | 0: no threat, but still a body a shield catches | 2: ignored entirely |
| `last_shield_value`: the turn-80 shield | 0: any intruder | 1: B4's test | 2: the review's valuation |
| `solver_retry`: my SHIELD did not happen | 0 | 1 | 1 (the same fix) |
| `fresh_guard`: all-home openings keep the clock | 0 | 0 | 1 |
| `pay_fix`: a capture pays on the turn it completes | 0 | 0 | 1 (B6, which v8 left for a retune) |

`v8_params.json` and `v9_params.json` set every one of these, so they still
rebuild v8 and v9 move for move. Whether v9 gains from the review's two extra
fixes (`fresh_guard`, `pay_fix`) has not been measured.

## What the v7 round changed

This branch is the second pass over the bot, prompted by the organisers
answering three rule questions and by one blunt observation: every number in the
first pass was measured against opponents written for this project, so "my bot
beats the field" partly meant "my bot beats my own assumptions".

**The ruleset is closed.** All five rules that had to be guessed are now
resolved, and every one matched the default reading — see
[The ruleset is now settled](#the-ruleset-is-now-settled). The one answered by
inference rather than by a direct statement is now also *measured off the board
at runtime*, so the bot does not depend on my reading of it.

**The field was rebuilt.** Seven new designs (`aifield.py`) that exploit two rule
facts the original zoo ignored, plus `probot.py` — a rate-ranking bot on a
genuinely different architecture with its own tuner. Tuned, it beats this bot
0.81 of 3. It is now in the training field, which drops the bot's baseline from
2.534 to 2.415 pairwise wins.

**Measurement was put on a sound footing.** Paired comparison over identical
games (`measure.py`), which cuts the standard error three- to five-fold, plus a
test that the harness is actually reproducible (`test_determinism.py`). This
mattered: the bot had *two* wall-clock dependencies, and with only one pinned,
two identical parameter sets measured 0.06 pairwise wins apart — larger than any
real improvement in this project.

**The tuner was selecting luck.** Thirteen generations of tuning produced a bot
measurably *worse* than its seed. Both tuners now have a confirmation stage. See
[The tuner was selecting luck](#the-tuner-was-selecting-luck); this is the single
most consequential finding here.

**Eight bugs fixed**, including two that could have cost the whole competition: a
file name that shadowed a standard-library module, and a failure path that turned
the bot into the skeleton for all 80 turns while every stress test reported
success. See [Mistakes found and fixed](#mistakes-found-and-fixed).

**What the bot's strength actually rests on** is now measured rather than
assumed, and one of those measurements corrected an earlier claim in this file.
See [that section](#what-the-bots-strength-actually-rests-on).

This round shipped **v7** (since superseded by v8, above) — tuned against the
rebuilt field with the confirmation stage, shipped with `tie_home: 1`, and passing every submission
check at 13.8 ms worst case. It is weakly better or level on all four measurement
fields and never significantly worse, but the gain against *unfamiliar*
opponents is +0.024 and not statistically significant; the large +0.251 was
measured on a field containing six of my own snapshots. See §8.3b.

## Quickstart



```bash
python ship.py
```

Builds `bot.py` from `fusion.py`, `econ.py` and `mybot.py`, then runs
`crossfield/acceptance.py`. It refuses to pass unless:

- the file is pure ASCII, parses as Python 3.7, imports only the stdlib and
  never prints;
- it plays identically to `fusion.py` and, on the documented interface, to the
  research branch's bot;
- four seats can share one module, and a reused module plays game 2 like a
  fresh one;
- the failsafe chain works when each planner is forced to raise;
- all eleven interface variants and a memory-less module hold their score;
- a server that offers SHIELD on cooldown gets no wasted shield, and a server
  with a flipped movement convention is recovered from;
- the all-home and step-out-and-back openings keep an exact clock;
- 24 live-clock games stay far under 200 ms.

```bash
python ship.py route v7_params.json
```

Builds the walk planner alone, as v7 shipped, to `bot_route.py`.
`route v9_params.json` and `route v8_params.json` build v9 and v8 the same way.



```bash

python test_engine.py

```



```bash

python strategies.py 150

```



> The check that matters most is **"decide() internal exceptions"**. `__call__`

> catches exceptions and returns `STAY`, so a completely broken bot looks healthy

> and scores zero. This caught exactly that: one parameter missing from a JSON

> file made the bot play `STAY` for all 80 turns while the stress test reported

> "0 failures".

## Pitting every branch against each other

`harness/simulate.py` plays Zone Rush games between the bots on every branch for as
long as you let it, then writes a detailed report.

```bash
python harness/simulate.py
```

Press **Enter** to stop. Games in progress finish and count, then the report is written
to `harness/simulations/<session>/report.md`; press Enter again to abandon those games
instead. Ctrl+C works the same way (once to stop, twice to abandon). SIGTERM, or
creating the `STOP` file named at start-up, stops it too, which suits a run left in the
background.

- **Every bot on every branch.** It fetches, then reads each local and remote branch
  straight from git objects, without touching the checkout. By default it enters every
  distinct file that would pass as a submission: a top-level `act(state)`, standard
  library only, no imports of its own sibling files. That means each branch's `bot.py`
  plus alternatives such as `mybot.py` or the research branch's `outputs/bot_*.py`.
  Identical files on several branches play once. Each bot is loaded and asked for turn 1
  before any game; one that cannot answer is left out, and the report says why
  (`agent_new.py` crashes with `NameError: PARAMS`). `--bots submissions` keeps only
  each branch's `bot.py`, `--builtins` adds the skeleton and random bots as baselines,
  and `--add FILE`, `--refs`, `--include` and `--exclude` adjust the field. `--list`
  shows the field without playing.
- **Real harness games, under the server's rules.** `harness/referee.py` resolves every
  turn, and each seat runs in its own process for the whole game, so memory persists
  between turns and stays private to that seat. The limits are 200 ms per turn and 2 s on
  turn 1, and a crash, late answer or illegal action plays `STAY` (rulebook 2.8).
- **A fair schedule.** Games come in blocks of four on one map with one starting token,
  and the line-up rotates through all four seats. Line-ups even out how often each bot
  plays and how often each pair meets. The rulebook's example map is used one block in
  four, and random mirrored maps the rest (`--maps`).
- **Scored as the rulebook scores.** Each game counts as three one-on-one results per
  bot, with equal scores a draw (3.2). The leaderboard is the settled Elo-scale rating,
  with bootstrap intervals and ordinary Elo as played alongside, and the rulebook's
  tie-breaks (head-to-head, then 1st places). A Round 2 view applies the cell-count
  tie-break and 3/2/1/0 pool points (5.3-5.4).
- **Nothing is lost.** Every finished game is appended to `games.jsonl` straight away,
  and `python harness/simulate.py --report harness/simulations/<session>` rebuilds the
  report from it. Games with a crash, late or illegal turn are saved as replays, which
  `python harness/server.py` lists under **Replays** (`--replays all` saves every game).

The report covers the verdict, the Round 1 leaderboard, the head-to-head matrix, places
and score trajectories, the Round 2 view, seat, token and map breakdowns, what each bot
actually does (action mix, claims, upgrades, raids, shields, freezes), rule compliance
and timing per bot, notable games with a command to replay each one, and the method.

To test one bot against a folder of opponents:

```bash
python harness/simulate.py --add-dir opponents --focus main:bot.py --minutes 30
```

- `--add-dir DIR` enters every `.py` file in `DIR`, each checked exactly as `--add`
  checks a file (self-contained, then the turn-1 check); files with no `act(state)` at
  all, such as helpers, are listed as not entered.
- `--focus NAME_OR_CODE` (a code from `--list`, a name, `branch:path`, or a file name)
  seats that bot in every game. The other three seats come from the remaining bots so
  each opponent meets it equally often (within one block of four games), and the block
  rotation takes it through every seat and token position. The report opens with its
  record against each opponent, worst first. If `opponents/MANIFEST.md` (or a
  `MANIFEST.md` in the `--add-dir` folder) gives the opponents styles, that record is
  also grouped by style, worst style first. The manifest can be a table with a file
  column and a style column, `## Style` headings with the files listed under them, or
  lines such as `- raider.py (style: aggressive)`. Entries match bots by file name.
- `--minutes N` stops by itself after N minutes (games in progress finish), writes the
  report and prints the session folder.



---



## Results



Measured over **1,100 games with 20 entrants**, random seats, maps and starting

token, scored the way Round 1 scores it — each four-bot game becomes three

one-on-one results, so `PW/3` is how many of the three rivals were outscored.



| bot | Elo | PW/3 | score | 1st | what it is |

|---|---|---|---|---|---|

| **v3** | **1907** | **2.41** | **2536** | **56%** | this project |

| v1 | 1701 | 2.14 | 2345 | 44% | first tuned version |

| `spine` | 1607 | 1.77 | 2033 | 29% | best farmer written by hand |

| `camper` | 1577 | 1.59 | 2010 | 15% | takes the 3-cells and squats them |

| `cdraider` | 1457 | 1.34 | 1801 | 12% | raids only inside shield cooldowns |

| `greedy` | 1391 | 1.08 | 1566 | 10% | model of the typical AI-written bot |

| `stay` | 674 | 0.08 | 160 | 0% | an unmodified or crashing skeleton |



**300 Elo over the best bot written by hand, 516 over the modal AI-written

entry.** The `stay` row matters too: a bot that crashes, times out or returns an

illegal action plays `STAY` and finishes there.



`bot.py` ships **v6**, a later version that beats v3 on six of seven matchups:



| matchup | v3 | v6 |

|---|---|---|

| mixed zoo lineups | **2.90** | 2.81 |

| held-out lineups | 2.74 | **2.84** |

| vs 3× `spine` | 1.47 | **1.81** |

| vs 3× `camper` | 2.71 | **2.89** |

| vs 3× `cdraider` | 2.52 | **2.66** |

| vs 3× `hunter` | 2.77 | **2.91** |

| mean | 2.586 | **2.704** |



### Robustness



| | |

|---|---|

| counter-bot bred specifically to beat it | 2.17 / 3 — where 1.50 is no edge |

| held-out opponents, never tuned against | 2.84 / 3 |

| transfer ratio (held-out gain ÷ training gain) | 1.8 – 1.9 |

| all five ambiguous rules flipped at once | 2.81 / 3 |

| turn time | 2.6 ms mean, 6.1 ms max (limit 200) |

| crashes / illegal actions / timeouts | 0 |

| four identical copies against each other | 5% score spread, 1st to 4th |



v6 is the strongest version *and* the most exploitable one (v3 gives up only

1.72). It ships anyway, because no competing team has this source to breed a

counter from, and v6 generalises better to opponents it was never tuned against.

`python ship.py v3_params.json` swaps the other way in one command.



---



## How the bot works



### 1. It rebuilds the state the server hides



The starter kit's `state` exposes the board, `bot_id`, `is_priority_token` and

`legal_actions`. It does **not** expose the turn number, any bot's score, take or

upgrade progress, shield cooldowns, freeze counters, or which seat holds the

token. `Tracker` reconstructs all of it from board diffs.



Every shield is observable, because it either catches somebody (that bot freezes)

or it backfires (the shielder freezes). Attribution is genuinely ambiguous when a

bot freezes while standing on rival land — it was either caught by the landlord or

backfired on its own shield. Rather than guess, the tracker searches for the set

of shielders that *exactly explains* the freezes observed, using the hard

constraint that a shielder cannot lose a cell that turn, and stays pessimistic

where two explanations tie. Guessing gave 1,406 errors; solving gave 25.



Knowing every shield gives every four-turn cooldown — and **a rival on cooldown

cannot defend anything.**



Verified against the engine's hidden state over 3,200 turns: scores, progress,

positions, freezes and the token are **exact**; cooldowns are 99.2% exact with

residual errors in the safe direction. Worth **+0.65 pairwise wins and +376

points** per game (`test_amnesia.py`).



### 2. It plans routes, not targets



A beam search over *walks* — sequences of work-cells with the real travel cost

between them — rather than ranking single targets by rate. Scoring whole walks

prices travel correctly and prefers clusters.



An earlier version ranked single targets and **paced between two neighbouring

cells for an entire game**, scoring 1,050 instead of 2,400. The cause was cell

modifiers keyed to walk distance, so whichever cell the bot stood on was

penalised relative to its neighbour.



### 3. It treats defence as the game-theory problem it is



The shield/raid stand-off is a 2×2 game with no pure equilibrium, so a

predictable defender can be baited: step onto their cell, let them shield, step

off, and they are frozen for two turns and on cooldown for four. The bot prices

the backfire branch properly and weights it by a per-opponent estimate of whether

that rival commits or bails. Against an opponent that never commits, its shield

rate falls from 12% to 4% within a single game.



### 4. It self-throttles



The grading machine may be slower or busier than the one these weights were tuned

on, and a late turn is scored as `STAY`. The search has a hard internal deadline

checked mid-iteration, and the beam shrinks when a turn runs long and grows back

when there is room. Under 24× CPU oversubscription the worst turn was 80 ms

against the 200 ms limit.



---



## The game, in numbers



Manhattan distance splits the 8×8 board cleanly into four 4×4 quadrants, one per

corner. Each is worth **28 points per turn** and holds exactly three 3-point

cells. Nothing inside your own quadrant is reachable by a rival in under five

moves, so your inner cells are safe and the centre is the only ground genuinely

worth contesting.



A cell is worth its value multiplied by the turns remaining — a 3-point cell taken

on turn 10 pays 210 points, the same cell on turn 70 pays 30. Raid bonuses

(`8 × value × level`) are one-off and therefore do **not** decay, which is why

half of all bonus income arrives in the last 20 turns.



A perfect solo farmer restricted to its own quadrant scores 2,744. Unopposed and

free to expand, the bot scores 3,404.



---



## Layout



| file | what it is |

|---|---|

| **`bot.py`** | **the submission** — generated by `ship.py` from the three files below, do not hand-edit |

| `fusion.py` | the fused bot's controller: input normalisation, failsafes, cold-start rescue, calibration |

| `econ.py` | the research branch's evolved economic planner, as a class (the primary) |

| `mybot.py` | `Tracker` and the walk planner (v7; the fused bot's warm standby) |

| `CROSS_BRANCH_REVIEW.md` | the critique of all four branches and every measurement behind the fused bot |

| `crossfield/` | the cross-author field (`xfield.py`), interface matrix (`robustness.py`), acceptance suite, identity tests, and every other branch's bots and opponents |

| `engine.py` | rules engine; the five ambiguous rules are flags in `RULES` |

| `zoo.py` | opponent archetypes used for tuning |

| `holdout.py` | opponents never used in tuning, for the overfitting check |

| `arena.py` | Elo tournament harness |

| `tune.py` | (1+λ) evolutionary weight search, multiprocess |

| `strategies.py` | macro-strategy sweep across three opponent fields |

| `rivals.py` | frozen snapshots, so the bot can face earlier versions of itself |

| `exploit.py` | exploitability matrix: every counter against every version |

| `ship.py` | build and verify the submission |

| `gpuenv.py` | Zone Rush as batched tensors, for GPU self-play |

| `rl.py` | PPO self-play training on the GPU engine |

| `nnbot.py` | pure-Python inference twin of the learned policy |

| `v*_params.json` | tuned weight snapshots; **`v9_params.json` is the shipped set** (v8 + `forecast: 1`); `v8_params.json` is v7's weights + the audit switches |

| `nemesis*.json` | counter-bots bred to beat a given version |

| `strategy_audit/` | the strategy audit behind v8: write-up, paired harness, eight outside opponent designs, alternative-referee and Round 2 penalty probes, the v7-compatibility check, and every result table ([`strategy_audit/README.md`](strategy_audit/README.md)) |



Scratch diagnostics, kept for reference and not needed to build or submit:

`diag*.py`, `dbg*.py`, `probe.py`, `calib.py`, `bench.py`, `patch_combo.py`,

`agent_new.py`, `final_eval.py`, `evaluate.py`.



### Tests



Everything, grouped by how badly a failure would hurt:



```bash

python runtests.py         # all suites; "fast" skips the two tournament ones

```



Individually:



```bash

# correctness -- every other number is measured through these

python test_engine.py      # rulebook examples + 400 fuzzed games with invariants

python test_gpuenv.py cpu  # tensor engine vs reference engine, state by state

python test_tracker.py     # the tracker's reconstruction vs the engine's hidden state

python test_determinism.py # the harness itself: paired games must be reproducible



# survival -- cannot crash, stall, time out, or leak state between games

python test_guards.py      # progress-rule detection, the fallback policy, state

                           #   reuse, flat vs 8x8 boards, a server that offers

                           #   SHIELD on cooldown, stdlib shadowing

python test_timing.py      # graceful degradation on hardware up to 100x slower

python test_robust.py      # ambiguous-rule flips, malformed input, seat symmetry

python test_amnesia.py     # what happens if the server keeps no module state



# strength

python audit.py 20         # behavioural pathologies: pacing, shield-happiness

python diag_seat.py 160    # seat bias, where symmetry fixes the answer at 1.50

python diag_loss.py        # where my points actually go

python test_transfer.py    # held-out opponents never used in tuning

python test_fields.py      # how much strength depends on the assumed field

python test_oppmodel.py    # does the opponent model actually adapt

```



### Re-tuning



```bash

python tune.py <generations> <games/gen> <population> <field> <out.json> <seed.json>

python tune_rival.py <generations> <games/gen> <population> <out.json>

```



`field` is `default`, `mixed`, `realistic`, `peer`, or `counter:<snapshot>`.

`counter:` tunes a bot to *beat* a snapshot — that is how this bot's own

exploitability is measured, and how the training field was hardened.

`tune_rival.py` tunes the independent rival in `probot.py`, so that the field

contains a strong opponent built on a different architecture.



---



## Strategy sweep



`v1`…`v6` were the *same* strategy with different weights. `strategies.py` sweeps

the distinct macro plans the game admits, against three different opponent fields

with common random numbers. PW is out of 3; 1.50 is average.



| macro plan | mean PW | vs incumbent |

|---|---|---|

| **deep search + ignore rivals** | **2.824** | **+0.112** |

| deep search alone (visits 8, beam 300) | 2.802 | +0.090 |

| ignore rivals alone | 2.753 | +0.041 |

| incumbent | 2.712 | — |

| turtle (own quadrant only, upgrade everything) | 2.598 | −0.102 |

| centre-steal opening | 2.598 | −0.102 |

| pure farmer (never raid) | 2.589 | −0.111 |

| never shield | 2.287 | −0.413 |

| berserker (raid-first) | 2.253 | −0.447 |

| expansionist (claim the whole board) | 1.804 | −0.896 |



Two results worth absorbing.



**Ignoring rivals beats targeting them.** Maximising your own score and never

weighting a rival's loss scores better than the placement-margin objective the

earlier versions used. In a four-player game, hurting one rival mostly helps the

other two, and the tempo costs you more than it costs them. Maximising absolute

score turns out to be a very good proxy for placement.



**Deeper search is the biggest single lever, but not monotonically.** `visits 8,

beam 300` is the best setting found; `beam 700` is measurably *worse*, because a

wider candidate set dilutes the beam.



---



## The GPU / reinforcement-learning track



Set up, trained, and **rejected**. Recorded so it is not repeated blindly.



`gpuenv.py` reimplements the game as batched tensor operations. `test_gpuenv.py`

replays identical action sequences through it and `engine.py` and compares the

full state after **every turn** under all five ambiguous-rule settings: 9,600

comparisons, exact. That test earned its keep immediately — it caught a bug where

progress was zeroed on every turn of a freeze rather than only when a new freeze

landed, which is invisible under the default rules.



Throughput at batch 32,768: **134,000 complete 80-turn games per second**

(10.7M game-steps/s), against roughly 500K steps/s for the Python engine on one

core. The environment is effectively free.



`rl.py` trains a 75-feature MLP by PPO self-play; `nnbot.py` is its pure-Python

inference twin, verified to match the torch feature extraction to 2.8e-08. After

**164M steps** the policy plateaus and then declines:



| matchup | learned policy | the heuristic bot |

|---|---|---|

| mixed zoo lineups | 0.52 | **2.83** |

| held-out lineups | 1.10 | **2.91** |

| vs 3× `spine` | 0.08 | **1.70** |

| vs 3× `greedy` | 2.60 | **2.99** |

| vs 3× the heuristic bot | **0.00** | — |



Inference was never the obstacle (1.3 ms/turn, well inside budget). The policy is

simply weak, for two structural reasons:



- **Pure self-play converges to a weak mutual equilibrium.** All four seats share

  one policy, so it only ever has to beat itself.

- **No search.** The shipped bot beam-searches seven work-items deep over whole

  routes. Zone Rush rewards multi-turn commitment — one stay to claim, three more

  to upgrade, plus travel — and a reactive policy cannot plan a route.



If picked up again, in order: train against a **vectorised heuristic opponent on

the GPU** rather than against itself, or **warm-start by cloning the existing

bot** before any RL. Using the network as a value function inside the beam is a

dead end for the submission — thousands of forward passes per turn will not fit

200 ms of pure Python.



The GPU work needs a separate venv (`torch 2.11+cu128`, for sm_120 Blackwell

kernels). It is gitignored, and the shipped bot has no dependency on any of it.



---



## What the bot's strength actually rests on

Measured, paired, rather than assumed — and one of these corrected an earlier
claim in this file that the search barely mattered.

| mechanism | how it was measured | worth |
|---|---|---|
| hidden-state reconstruction | wipe module state every turn (`test_amnesia.py`) | **0.77 PW** |
| multi-visit route planning | `visits: 1` against `visits: 7` | **0.20 PW** |
| beam width | `visits: 10` against `visits: 7` | −0.02 PW (nothing) |
| everything hand-designed later | eight paired A/Bs | 0.00 or negative |

```
full (visits 7)   2.597   (reference)
visits 1          2.393   dPW -0.2037   z -6.85 **
visits 3          2.527   dPW -0.0700   z -2.53 *
visits 10         2.578   dPW -0.0187   z -1.18
```

The distinction between the middle two rows is the part worth keeping. Planning a
route across several work-cells is load-bearing; the *width* of the beam that
searches those routes is not. That is also why the bot survives a machine 100x
slower while losing only 2.6% of its score: the deadline narrows the beam but
still runs every visit, so it keeps the mechanism that matters and discards the
one that does not.

It also explains why the independently-built rival reaches parity with no
lookahead at all. It has *hard* commitment -- it holds a goal until the goal is
finished -- and that substitutes for planning. The `visits: 1` variant above has
only soft stickiness, so it is a weaker thing than ProBot, not an equivalent one.

## The game is non-transitive, so single-opponent tests mislead

The independent rival (`probot.py`), once tuned, beats this bot decisively — and
then loses to a bot this bot beats comfortably:

| focus bot | vs 3x pro_tuned | vs 3x spine | vs 3x ai_hawk | vs 3x camper |
|---|---|---|---|---|
| **v6** | **0.81** | 1.85 | 2.31 | 2.81 |
| **pro_tuned** | 1.25 | **0.89** | 2.22 | 2.03 |

Rock-paper-scissors: pro_tuned beats v6, v6 beats spine, spine beats pro_tuned.
Two things follow.

First, **"three identical copies" is not a model of the Round 1 field**, which
mixes opponents and seats. A bot can be murdered by three copies of a design it
would rarely meet twice in one game. All version decisions here are therefore
made on mixed-field paired measurements (`choose.py`), never on head-to-head
trios.

Second, the 0.81 is still worth taking seriously, because it is what
exploitability looks like from the inside. `tune_rival.py` weights v6 at 3.0 in
the rival's own training field, so pro_tuned is partly a counter-bot — and that
is exactly the thing worth defending against, since the repository is public and
anyone can breed one. It has now been frozen as `pro_params_v1.json` and added to
the training field at the highest weight, because until this point the bot had
never been tuned against an opponent capable of beating it.

## The tuner was selecting luck

The single most consequential finding of the late work, and it invalidates
effort rather than code.

The search takes the best of `lam` candidates on one draw of games. That is a
maximum over noisy estimates, so the winner's measured score is biased upward
even when it is no better than the incumbent. With a few hundred games the
paired standard error is around 0.03 pairwise wins, and the best of thirteen
draws sits roughly 1.5 of those above the truth — more than the improvements
being searched for. Accepted candidates then compound the bias generation over
generation.

The tell was in the logs all along. The task set is refreshed every six
generations with the incumbent re-scored on it, and the incumbent dropped by
about that much every single time:

| | on its own task set | re-scored on fresh games |
|---|---|---|
| gens 5-6 | 2.6364 | 2.5568 |
| gens 11-12 | 2.5758 | 2.4583 |

Then the direct test. Thirteen generations of tuning against the rebuilt field,
measured paired against v6 on games neither had seen:

```
v6   2.597   (reference)
v7   2.575   dPW -0.0219 +/- 0.0242   z -0.90
```

**Nothing.** Thirteen generations, several hours, no improvement — the search had
spent them accepting luck. Both tuners now have a confirmation stage: a candidate
has to win its own draw and then beat the incumbent again on a fresh draw that it
was not selected on. Accepting costs a second evaluation; accepting noise costs
the whole run.

I drew the wrong conclusion from this at first, and the retraction is instructive
enough to keep. Seeing no transferable gain, I wrote that v6 must sit close to a
local optimum and that the remaining headroom was small. **That was the measuring
instrument, not the bot.**

### The field you measure on can be saturated

The `realistic` tier is a fair model of the Round 1 field, weak entries included
-- and that is exactly what makes it useless for separating two strong bots. v6
already scores 2.556 of a maximum 3.0 there, winning roughly 85% of its pairings,
so a genuine improvement has almost nowhere left to register. The `peer` tier,
where v6 sits at 1.71, has real headroom.

The same candidate, ten generations into the confirmed tune, measured on both:

| tier | v6 | v7 | dPW | z |
|---|---|---|---|---|
| realistic (saturated) | 2.556 | 2.549 | −0.007 +/- 0.025 | −0.27 |
| **peer** | **1.713** | **1.966** | **+0.2535 +/- 0.0377** | **+6.73** |

Against three copies of a single opponent it is better across the board, not
specialised toward the rival it was tuned against:

| vs 3 copies of | v6 | v7 |
|---|---|---|
| pro_tuned | 0.80 | **1.20** |
| ai_hawk | 2.48 | **2.64** |
| spine | 1.89 | **1.95** |
| camper | 2.93 | **2.98** |

So the honest reading is the opposite of what I first wrote: there *was* real
headroom, the confirmed search found it, and a saturated measurement hid it
completely. Version decisions should lean on `peer` and the held-out tier;
`realistic` answers "is this strong against the expected field", not "is this
better than that".

There is a second, subtler trap underneath this one. The `peer` tier
discriminates, but **six of its eleven entrants are my own snapshots**, so "good
on peer" partly means "good against my own lineage". A fourth tier (`strangers`,
14 opponents, none of them a version of this bot) shows the newly tuned candidate
gaining **+0.251 on peer but only +0.024 on strangers and −0.024 on held-out** --
the large number existed only where the field was my own family. A
discriminating measurement is not automatically an unbiased one.

It also puts an asterisk on the negative results below. Several were measured on
the saturated tier, so some may be false negatives rather than dead ends -- the
ones with a sound mechanism are worth re-running on `peer`, and the tuner is in
any case exploring those parameters directly on a field whose baseline is 2.41.

## Mistakes found and fixed



There is no competition simulator and no trial run — whatever is in this

repository at the deadline is played once, by a server that cannot be inspected

beforehand. So the search for errors is worth as much as the search for strength.

These are the ones that were real. The strategy audit found ten more in v7 and v8
fixes them; they are listed in [v8: fixes from the strategy audit](#v8-fixes-from-the-strategy-audit)
and explained in full in [`strategy_audit/README.md`](strategy_audit/README.md).



- **A file named `select.py` shadowed the standard library.** `multiprocessing`

  imports `select`, so it loaded *this* directory's file instead, whose

  module-level code then parsed the tuner's command line and exited. A three-hour

  tuning run never started, and the symptom was an unrelated argument error about

  a filename. `test_guards.py` section F now checks that no file here shadows a

  stdlib module.

- **The bot could have shipped playing `STAY` for 80 turns.** `decide()` runs

  inside a `try/except` that returned `STAY` on any exception — so one bad

  assumption about the state object degrades the bot to the skeleton while every

  stress test still reports "no crashes". It had already happened once, from a

  single missing parameter key. There is now a `_fallback` policy that depends on

  almost nothing: stay on any cell that is not finished, otherwise walk toward the

  best unowned cell. With `decide()` forced to raise on every turn, the bot still

  scores **1365 against the skeleton's 158** — 8.6×. `ship.py` verifies the

  fallback survives into `bot.py`.

- **A seat-bias alarm that was the test's fault.** `test_robust.py` reported

  2.1 / 2.4 / 1.3 / 1.2 pairwise wins across the four seats, which looks like a

  bot hardcoded to a corner. It is not: the map is four-fold mirrored, so four

  copies of one bot must average exactly 1.50 per seat, and in self-play this bot

  scores **1.43 / 1.49 / 1.54 / 1.55** — noise. The asymmetry belonged to

  `SpineFarmerBot` (1.13 / 0.87 / 1.98 / 2.01); replacing a strong seat is a

  different experiment from replacing a weak one. The seat check is now self-play

  only (`diag_seat.py`).

- **The tuner's fitness function was non-deterministic.** Candidates were

  evaluated with the adaptive beam on, so identical parameters scored differently

  depending on machine load, and the search could chase timing artefacts.

  Evaluation now pins `throttle: 0`.

- **The progress-rule detector carried the wrong amount.** Under the carry-over

  reading, capturing an *upgraded* rival cell leaves progress at 3, not 1 — enough

  to re-upgrade it on the very next stay. Fixing it cut the reconstruction error

  from 36 wrong turns to 1 in 800.

- **`SHIELD` is now cross-checked against the bot's own cooldown**, not only

  against `legal_actions`. If the server offers `SHIELD` during cooldown and

  treats the attempt as `STAY`, the old code would waste the turn *and* record a

  shield that never went up. Verified: zero wasted shields under a server that

  offers it wrongly.

- **The Agent kept state across games even though the Tracker did not.** The
  tracker rebuilds itself when it sees a starting board, but the agent around it
  held its current objective (which feeds the stickiness rule), the random stream
  that mixes the shield decision, the adaptive beam scale and the turn counter.
  If the server plays several games in one process — which the organisers'
  "memory is allowed, but it is your burden" answer makes a real possibility —
  game 2 would be played by a bot still carrying game 1. Found only because the
  seat-symmetry fix changed play enough to expose it; the tracker now announces a
  new game and the agent clears its own state on that signal.
- **`README.md` stopped being valid UTF-8.** Python's `open()` writes in the
  platform's default encoding on Windows, so a maintenance script that rewrote
  the file without `encoding="utf-8"` dropped a cp1252 byte into it. In a public
  repository that renders as mojibake; in `bot.py` it would be a syntax error on
  the grading server. `test_guards.py` section G now checks every `.py`, `.md`
  and `.json` file decodes as UTF-8.
- **A test that failed for a reason unrelated to what it tested.** The
  state-reuse check pinned `throttle` but not `budget_ms`, so under load the
  beam's deadline truncated the search differently between its two runs and the
  check reported a state leak that was really a timing difference. Both guards
  are now pinned wherever two runs are compared for equality.
- **An opponent that paced instead of playing.** `ai_route` walked

  NORTH/SOUTH 66 times in 80 turns and banked 10 stays, because it re-planned from

  scratch every turn and the rate denominator shifted under its feet — the same

  class of bug that once halved this bot's own score. `audit.py` now flags it:

  any bot that stays on under 25% of turns, or reverses direction on over 22%, is

  doing something other than playing.



## Tested and found NOT to work



All of these were plausible, and several were confidently predicted before any

code ran. Recorded so they are not re-tried.



- **Priority-token contest avoidance** — tuned to exactly zero on a weak field, and

  back up to 0.92 on a strong one. Field-dependent, not free.

- **All-out endgame raiding** — the bot already shifts to raiding late on its own;

  forcing it harder is clearly worse (2.86 → 2.61).

- **Occupancy as deliberate defence** ("a cell I stand on cannot be entered") — no

  measurable benefit, because the planner is already parked on cells while

  upgrading them.

- **The centre-steal opening** — six turns of zero income is not recoverable.

- **Perishability bonus** and **retake credit** — both tuned to zero.

- **Equilibrium shield mixing** — the formula is correct and present, but it does

  not bind: stopping an imminent take is worth an order of magnitude more than a

  shield costs. The per-opponent commit estimate is what actually prevents

  baiting.

- **Consolidating late** and **varying risk with standing** — within noise.

- **PPO self-play**, as above.



Six more, all added after the ruleset was confirmed and all measured as paired

differences against v6 on the rebuilt field. `dPW` is the change in pairwise wins

out of 3; `z` is the paired z score, so anything inside ±2 is noise.



| idea | dPW | z | why it failed |

|---|---|---|---|

| Projected final scores in the objective | 0.0000 | — | **structurally inert**: v6's tuned `care_mode` is 4 (uniform), so the objective never reads rival scores at all |

| Home-upgrade bonus (the one unraidable doubling) | −0.013 | −1.5 | a home is only worth 1–2 base, so three early turns there costs more than immunity is worth |

| Penalise upgrading exposed cells (an upgrade doubles the bounty on it) | +0.002 | +0.6 | real, but far too small to see |

| 2 s of extra search on turn 1 | −0.005 | −0.6 | the opening is easy; depth buys nothing on an empty board |

| Pricing the progress a `SHIELD` throws away | −0.034 | **−3.4** | the cost is real, but v6's tuned `shield_bias` was already compensating for it, so adding it double-counts |

| Rival intent (discount cells a rival is visibly walking toward) | −0.027 | −1.1 | consistent with `perish` having already tuned to zero: rival-aware cell modifiers are worth nothing |



Both of the last two are left in the code at zero and handed to the tuner, which

can weigh them jointly against the parameters that were compensating for them.



One caveat on those numbers, stated rather than hidden: the load-dependence

described below was found *after* they were measured. The first two batches ran

with no competing job and carried an exact-zero control (two copies of the same

parameters, reported as 0.0000 +/- 0.0000), so they stand. The shield-progress

and intent batch had no such control; both of its conclusions were negative and

both parameters are now in the tuner's search, so nothing rests on them.



Two further ideas were **killed by measurement before being built**:



- **Timing arrivals to the priority token.** The bot knows exactly which turns it

  holds the token and could schedule contested entries for them. Measured first:

  blocked moves and lost contests cost **0–0.9% of moves**, about 0.2 turns per

  game. The existing contest penalty already avoids them, so there is nothing to

  win.

- **Counting flipped pairings instead of points.** Round 1 scores each game as

  three one-on-one results, so a gain "should" be worth the number of rivals it

  lifts you past. This is **inert by construction**: a walk is scored by one

  scalar total, and any monotone transform of a scalar leaves the best walk

  unchanged. What the idea really reduces to is "prefer a certain gain when it

  already suffices, gamble when behind" — which is the existing `lead_caution`

  parameter.



### The bot played differently in each corner — and it cost nothing



Worth recording because the instinct is to assume a 0.45 asymmetry must be

expensive. It was real, and it was free.



Candidate cells are ranked by `v x (R - d - need) / (d + need)` over small

integers, so exact ties are common, and they were broken by **raw cell index**.

That is not the same rule in all four corners: high indices are the bottom-right,

so seats 3 and 4 broke ties toward their own homes while seats 1 and 2 broke them

away. In self-play, where the four-fold mirrored map pins every seat at exactly

1.50 pairwise wins, v6 measured:



| tie-break | PW by seat 1-4 | spread |

|---|---|---|

| raw cell index (what v6 shipped) | 1.72 / 1.72 / **1.29 / 1.27** | **0.45** |

| nearest my own corner | 1.47 / 1.54 / 1.53 / 1.46 | 0.08 |

| farthest from my own corner | 1.49 / 1.35 / 1.52 / 1.64 | 0.29 |



`CANON[seat]` now re-expresses every cell index in the seat's own frame, and the

same ordering is applied to equally good steps in `_step` (whose `NEIGH` order

was the second, smaller asymmetry — it only shows up under the `farthest` rule,

which drives bots into each other and so into more contests).



Then the strength measurement, on the mixed field: **+0.0021 +/- 0.0175**.

Nothing. Which is exactly right on reflection — 1.72 and 1.27 average to 1.495,

so once seats are mixed the two biased behaviours come to the same thing as the

symmetric one. The payoff was understanding, plus a symmetry test that can now

detect a real corner-dependent bug instead of reporting one that costs nothing.



### Defence has a ceiling, and it is about one cell per game



The bot shields on 1% of turns, which looked like a blind spot. `diag_loss.py`

settles it by counting what actually gets taken:



| opponent | my score | cells lost | income forgone | bonuses handed over | losses I *could* have shielded |

|---|---|---|---|---|---|

| `raider` | 2181 | 3.5 | 370 | 99 | 1.2 |

| `cdraider` | 2403 | 4.6 | 275 | 104 | 1.4 |

| `ai_hawk` | 2436 | 1.0 | 24 | 20 | 0.8 |

| `spine` | 2633 | 0.6 | 6 | 6 | 0.6 |



Most losses happen while the shield is on cooldown or the bot is frozen, so the

total headroom for better defence is **about one cell a game**. Near-zero

shielding is a correct read of the game, not an oversight — upgraded cells take

three stays to steal, so a compact upgraded cluster largely defends itself.



### One cautionary result



**v5 overfitted to beating itself.** Its training field contained four of its own

ancestors plus two counter-bots. It scored best of any version on that field and

worst of the lineage against outside opponents (2.55 against v3's 2.74).

Self-play fields need outsiders to stay honest, and version selection has to run

on an external tournament rather than on each run's own training score.



---



## The ruleset is now settled



`engine.py` originally encoded guesses at five rules the rulebook leaves

ambiguous. All five are now resolved, and **every one matched the default

reading**, so no retuning was needed on their account.



| # | Question | Answer | Source |

|---|---|---|---|

| 1 | Does a frozen bot's forced `STAY` accrue progress? | **No** | organisers, directly |

| 2 | After capturing a cell, does progress reset? | **Yes** (4 stays to own *and* upgrade a neutral cell) | starter README rules 5 + 7; also detected at runtime |

| 3 | Does losing a contested race count as a `STAY`? | **Yes** | starter README rule 4: "Unsuccessful moves count as `STAY`" |

| 4 | Can a bot `SHIELD` on rival land to dodge the catch? | **Yes** — a shield is not a stay | starter README rule 8 |

| 5 | Can a home cell be upgraded? | **Yes**, and it can never be captured | starter README rule 7 |



Two further facts from the starter kit that the bot depends on:



- `state.board` is an **8 × 8 list of lists**, row-major, `(0,0)` top-left, with

  `NORTH` = row − 1. The parser accepts a flat 64-list too, and `test_guards.py`

  checks both give the same move.

- Keeping state between turns is **explicitly allowed**, with the caveat that

  handling blocked or illegal moves is the entrant's problem. Both are handled:

  a blocked move is observed as a non-move and counted as a stay, exactly as the

  rules say.



Question 2 is the only one answered by inference rather than by a direct

statement, and it is the one that changes the arithmetic (4 stays versus 3 to own

and upgrade a neutral cell). So the bot does not rely on the inference: it

**measures the rule off the board at runtime**, by watching any bot capture a

cell and counting the stays until the upgrade appears. It takes about 7 turns to

settle and is correct in 10/10 games under either reading

(`test_guards.py`, section A).

Two more readings the server could still differ on are guarded in `bot.py`
(8 Nov 2026), so that a misreading costs a little rather than a game:

- **Homes that cannot be upgraded.** Question 5 is also an inference: rule 7
  upgrades "your own level-1 cell" and does not exclude the home. If the server
  disagreed, the planner would sit on its home trying to upgrade it for about 52
  of 80 turns, scoring 1.16 pairwise wins out of 3 instead of 2.68. Now a job that
  should have finished and has not marks its cell as not worth pursuing again
  that game (`econ.py`, `Econ.observe`). Under the written rules every finished
  job changes the cell, so this never fires: the bot plays move for move as
  before (240 games, 0 of 19,200 decisions differ). If homes cannot be upgraded
  it scores 2.71 and finishes ahead of the unguarded bot 85% of the time.
- **Which seat starts in which corner.** The starter kit says only that bots
  start in the four corners, one per seat. The starting board was recognised by
  a fixed seat-to-corner order; now any bot on any corner counts
  (`fusion.py`, `_f_normalize`). There was no measurable cost before, but under
  another order turn 1 was treated as a mid-game wake-up.



## The field problem, and what was done about it



The honest weakness of the earlier results was that *every* opponent was written

for this project. Beating them partly meant beating my own assumptions. The brief

was to assume every other team also used an agentic assistant, so the field was

rebuilt in three tiers (`field.py`):



| tier | what it is | why |

|---|---|---|

| peers | tuned snapshots of this bot (`v3`, `v6`) and counter-bots bred against them | the closest available model of another team's tuned bot |

| designs | `aifield.py` — seven serious designs, each getting part of the rulebook right | what real entries look like |

| weak | the original zoo and held-out archetypes | a field of twenty-odd teams always contains several that barely work |



`aifield.py` exists because the original zoo missed two rule facts entirely:



- **a rival's *level-1* cell needs only one stay** and still pays the full

  `8 × base × 1` raid bonus, so cheap raids strictly dominate claiming an equal

  neutral cell;

- **a home can be upgraded and can never be captured**, making an upgraded home

  the only risk-free doubling on the board.



`probot.py` goes further: a rate-ranking bot on a genuinely different

architecture from the beam planner, with its own tunable weights

(`tune_rival.py`). Unopposed it outscores this bot — **3551 against 3276** —

because it pays nothing for defensive habits. It is in the field precisely

because it is not me.



## How changes are measured



Unpaired tournament means cannot see a change worth 0.02 pairwise wins: the

per-game standard deviation is about 1.0, so 400 unpaired games have a standard

error near 0.05 and most real improvements vanish into it.



`measure.py` therefore runs every variant over the **identical** list of

(map, seat, opponents, token) tasks and compares per-task differences. Map and

line-up luck cancels exactly, which shrinks the standard error three- to

five-fold. Two copies of the same parameters report a difference of exactly

0.0000 ± 0.0000, which is the harness validating itself.



```bash

python measure.py 700 realistic base=v6_params.json cand=v6_params.json+shield_bias:1.0

python choose.py 700          # the final three-tier comparison

```



One subtlety that mattered, and cost two restarted tuning runs to get right: the

bot has **two** wall-clock dependencies, and switching off one is not enough.



1. The adaptive beam (`throttle`) scales the search by how long the last turn

   took.

2. The hard deadline *inside* the beam search (`budget_ms`) truncates it when a

   turn runs long — and this one bites even with `throttle: 0`.



With only the first disabled, two identical parameter sets measured 0.0625

pairwise wins apart under load, which is larger than any real improvement found

in this project. Evaluation now neutralises both (`tune.play_task`,

`measure.play`, `rivals.factory`), so the search always runs to completion and

the result cannot depend on how busy the machine is. Both guards are insurance

against a slow grader rather than part of the policy, so they stay in `bot.py`

and stay out of the fitness function — and `test_determinism.py` now asserts the

property directly, three ways, because it is the assumption every other

measurement rests on.

