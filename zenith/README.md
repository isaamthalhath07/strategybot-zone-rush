# Zenith

The generation after Apex, built with a **move grader**: a system that rates every
decision by how it changed the bot's chance of finishing above its rivals, measured to
the end of the game. The grader found where the current generation loses value. Each
change in Zenith targets one of those leaks, and each was kept only after paired games
confirmed it.

`zenith_bot.py` is one file, standard library only (`collections`, `math`, `time`),
exposing `act(state)` exactly as the starter kit defines it. It is built from
[`src/`](src) by [`build.py`](build.py). To submit it under the required name:

```bash
python zenith/build.py bot.py
```

The root `bot.py` is untouched.

## Results

`zenith/lab/benchmark.sh 200 1000`: 200 games per mode, fresh seeds never used in
development, wall clock on as shipped. Every mode is **paired**: Apex plays the
identical games (map, seats, line-up, token, `legal_actions` convention) in the same
seat, so "gain" is Zenith minus Apex with a paired standard error. PW is pairwise wins
out of 3, the Round 1 unit; 1.50 is no edge.

**Against three copies of each previous generation** (the generation itself scores 1.50
there by symmetry, so above 1.50 means Zenith beats it):

| three copies of | Zenith PW | share of pairings won | Apex in the same seat | gain | z |
|---|---|---|---|---|---|
| v7 (main's walk planner) | **1.930** | 64.3% | 1.750 | **+0.180** | +2.36 |
| indep_v7 | **1.955** | 65.2% | 1.960 | −0.005 | −0.09 |
| evolved (research planner) | **2.590** | 86.3% | 2.605 | −0.015 | −0.34 |
| fused (the shipped `bot.py`) | **2.560** | 85.3% | 2.522 | +0.038 | +0.89 |
| **Apex** | **1.710** | **57.0%** | 1.460 | **+0.250** | **+2.56** |

**In mixed line-ups:**

| field | Zenith PW | Apex PW | gain | z (hard / soft) |
|---|---|---|---|---|
| previous generations (3 drawn from v7, indep_v7, evolved, fused, Apex) | **2.115** | 1.990 | **+0.125** | +1.99 / +2.61 |
| human-like players (the styles that beat Apex) | **2.080** | 1.875 | **+0.205** | **+3.08** / +3.31 |
| everything (every author group, the generations, the human-like players) | **2.312** | 2.208 | **+0.105** | +2.30 / +2.54 |

Head-to-head inside the previous-generations line-ups (share of one-on-one pairings won):

| | v7 | indep_v7 | evolved | fused | Apex |
|---|---|---|---|---|---|
| Apex | 68.3% | 71.4% | 65.2% | 72.4% | 56.0% |
| **Zenith** | 68.3% | **73.6%** | **74.4%** | **74.0%** | **65.2%** |

Against the human-like players Zenith **wins the pairings Apex lost**: the cooldown
sniper 55.7% (Apex 39.6%), the steady farmer 55.0% (Apex 47.7%), the endgame sniper
60.9% (Apex 53.6%). On the broad field it is at least level with Apex against every
author group.

Engineering: worst turn 103 ms with every expensive mode active (limit 200), first turn
8.8 ms (limit 2,000), mean 4 to 28 ms per turn depending on the table. Zero crashes and
zero illegal actions in every game above. All eleven server-interface variants, a module
reloaded every turn, module reuse across seats and games, and the safety net with the
agent forced to raise pass (`tests/test_zenith.py`).

**The grader's verdict.** Apex and Zenith were graded on the same 8 tasks against the
human-like players (`grader/runs/campaign2.sh`: same maps, seats, line-ups and tokens,
every other turn graded, 4 samples per candidate):

| | Apex | Zenith |
|---|---|---|
| accuracy | 87.2% | **94.3%** |
| accuracy on critical moves | 84.1% | **93.6%** |
| Blunders / Mistakes | 19 / 7 | **8 / 2** |
| total value lost | 47.2 PW | **19.9 PW** |
| shields played that lost | 8, costing 6.9 PW | **4, costing 0.25 PW** |
| completing raid stays into a shield | 5, costing 1.3 PW | 7, costing 0.0 PW |
| shields missed | 29, costing 6.0 PW | 14, costing 5.4 PW |

Eight games is a small sample, and the games part ways after the first different move,
so these are not the same positions. It is the grader confirming from the other side
what the paired games measured: the shield moments it flagged are where Zenith stopped
losing value. Missed shields are the leak left for the next generation.


---

## 1. Why a new generation: Apex loses to a calm human

Apex could be beaten by hand. To make that measurable,
[`lab/humanlike/`](lab/humanlike) holds six opponents that play the way a person who
has watched these bots would. All six farm with the evolved planner's economy, the
strongest in the repository, because anyone who beats Apex farms at least that well.
Each adds one human habit on top:

| style | what it does |
|---|---|
| `hx_steady` | ignores rivals (no denial), shields only on the turn a raid would complete, snipes level-1 cells in the last twelve turns |
| `hx_cdsnipe` | raids a rival cell only when its owner cannot shield before the take completes (on cooldown or frozen) |
| `hx_sniper` | farms, then raids hard in the last fifteen turns, when bonuses no longer decay against income |
| `hx_bait` | sits two turns on a rival's upgraded cell, steps off on the turn the owner shields, takes the cell in the cooldown |
| `hx_aggro` | lives off one-stay raids on the leader's level-1 cells |
| `hx_mixed` | one of the above per game |

Against three Apex copies, `hx_steady` scores **1.72 to 1.88 of 3** over two 32-game
runs (1.50 is no edge); the evolved bot, in the same seat, 0.95. In mixed human-like line-ups every previous
generation scores 1.80 to 1.88, and **Apex loses its head-to-head pairings with the
cooldown sniper (40.7%) and the steady farmer (44.2%)**. That is a calm, defensive
player who lets the bots fight each other and strikes only when a shield cannot
answer, which is probably close to how a person beats Apex.

## 2. The move grader

[`grader/`](grader) rates every move, chess-review style. Full method in
[`grader/README.md`](grader/README.md). In short:

* **Q(a)** for every distinct legal action is the expected pairwise result (0 to 3) if
  the seat plays *a* now and every bot at the table then plays on to turn 80. The
  grader forks the whole process, engine and live bots with their memory, once per
  candidate and per sample. Samples beyond the first add 4% per-turn noise to every
  seat, so a move is not judged on one butterfly-effect future. Common random numbers
  make the differences far less noisy than the values.
* **Loss** = Q(best) − Q(played), **cross-fitted** (the best move is chosen on half the
  samples and measured on the other half) because a maximum of noisy estimates is
  biased upward. On synthetic equal-valued moves the naive loss reads +0.19 and the
  cross-fitted one +0.005 (`tests/test_grader.py`).
* **Categories**: Brilliant !!, Great !, Best, Excellent, Good, Inaccuracy ?!, Mistake ?,
  Blunder ??, Forced. A Mistake or Blunder must also be significant (loss > 2 SE).
* **Accuracy** on the lichess curve, and accuracy on *critical* moves only, because a
  lost game makes every later move look perfect.

## 3. What the grader found

The evolved planner is Apex's base plan and the fused `bot.py`'s. Its 5,120 moves over
64 games against the human-like players were graded with 6 samples per candidate
(`grader/runs/campaign1.sh`, data in `grader/runs/evolved_humans.jsonl.gz`).
Accuracy was 90.8%, 87.9% on the 3,627 critical moves; 226 Blunders and 112 Mistakes.
Where the lost value goes:

| | share of lost value | per move |
|---|---|---|
| **stayed when it should have moved** | **52.9%** | 0.188 PW |
| moved the wrong way | 21.8% | 0.101 |
| should have shielded (stayed / moved instead) | 13.7% | 0.21 |
| shielded when it should not have | 6.0% | 0.26 to 0.38 |

| turns | share | per move |
|---|---|---|
| 1-10 | 19.8% | 0.143 |
| 11-30 | 35.7% | 0.130 |
| 31-60 | 36.6% | 0.092 |
| 61-80 | 8.0% | 0.032 |

Inside "stayed when it should have moved", by what the stay was doing:

| the stay was | moves | per move | what it means |
|---|---|---|---|
| an upgrade step | 846 | 0.12 to 0.14 | tempo: three turns upgrading while neighbours take the contested cells |
| a claim | 322 | 0.13 | the same race, lost by stopping for a cheaper cell |
| **the completing stay of a raid on an upgraded cell** | 28 | **0.457** | walking into the owner's shield: two frozen turns, the raid lost |
| upgrading the home | 36 | **0.347** | the planner values home income over 100 turns |

and on defence, a shield played with a rival standing on one of its upgraded cells lost
0.28 PW a move on average (first 2,217 moves), while a shield it should have played
and did not cost 0.21.

Two lessons came out of this, both important for what follows:

* **Most graded loss is oracle knowledge.** The grader's best move often depends on
  exactly what the opponents will do next. A bot without that knowledge cannot copy
  it. That is why Apex's exact simulation of copies is so strong, and why no global
  setting of the planner recovers this loss (section 5).
* **The systematic, repeatable leaks are the shield moments.** Completing a raid into
  a likely shield, and defending against an intruder whose habits are visible.
  Those are where a fix generalises.

## 4. What Zenith changes

Zenith is Apex's code (tracker, simulator bank, prediction-aware tactics, exact-world
and endgame searches, interface normalisation, safety net) with five additions, all in
[`src/agent.py`](src/agent.py) under `ZENITH`:

| setting | the leak it targets | what it does |
|---|---|---|
| `dance` | completing a raid into a shield (0.457 PW a move) | learns, per opponent, how often it shields **on the turn a take would complete** (not how often it shields at all, which is what Apex reads) and, when that is above one half, steps off instead of staying: the shield backfires and the owner is frozen two turns and on cooldown four |
| `veto` | shields that lose (0.26 to 0.38 a move) | a planner shield is dropped when Zenith's own model of the intruders, what each one has done at completion moments before, values it below its cost |
| `cdone` | missed shields at real completions (0.21) | that model: a per-raider rate of staying for the completing stay on an upgraded cell |
| `snipe` | the cooldown sniper's edge over Apex | raids a cell whose owner cannot shield before the take completes, when its rate beats the planner's best |
| `stealth` | Apex simulating Zenith | Zenith keeps simulators of itself as an observer would; in the opening it takes an equally short route whenever no public genome predicts it, so from turn 2 every Apex at the table has retired its evolved hypotheses about Zenith |

Measured, paired on identical games against Zenith-with-these-off (which plays Apex
exactly; 15 of 16 games bit-identical, the 16th differs only by an Apex opponent's clock):

| field | games | tactics (`dance`+`veto`+`cdone`+`snipe`) | + `stealth` |
|---|---|---|---|
| human-like players | 300 | **+0.085** (z +2.06) | |
| previous generations | 200 | **+0.128** (z +2.70); vs Apex 40.7% → 54.4% | |
| previous generations | 240 | +0.071 (z +1.74) | **+0.110** (z +1.87); vs Apex 41.4% → 48.3% |
| three Apex copies | 200 | +0.090 (z +1.39) | +0.100 (z +1.15) |

Ablation (240 games, previous generations, each removed from the full set):
without `dance` −0.048 (soft z −1.98), without `veto` −0.038 (soft z −1.65), without
`snipe` −0.008, without `cdone` −0.008. The gain is the two shield-moment fixes.

## 5. What did not work

| idea | result | lesson |
|---|---|---|
| **Teaching the planner's genome from graded positions** (`lab/distill.py`: replay the planner under a candidate genome on every stored position and score it by the grader's Q of the move it would choose) | on 3,063 positions: +0.0037 PW a decision tuning, +0.0034 validation; **in games −0.137 PW (z −2.2)**. On all 4,917: +0.0051 tuning, **+0.0006 validation** | a one-step improvement measured offline does not survive the positions it leads to, and the planner's genome is at a local optimum even under the grader's critique. The validation split caught it once the data was large enough; a game confirmation caught the earlier one. Neither shipped |
| No denial (`denial_base`, `denial_close` = 0), the steady farmer's habit | +0.093 (z +1.72) on human-like players, +0.090 (z +1.20) on previous generations, nothing on top of the tactics | plausible, not significant; not shipped |
| Shorter home income horizon (`home_retention` 40) | +0.013 (z +0.33) | the home-upgrade leak is real but rare |
| An Apex simulator for every rival seat (`apexsim`) | −0.004 on top of the tactics, and the worst turn rises to 125 ms | it reproduces Apex move for move (`tests` section I), but the evolved simulators already predict Apex outside its rare tactic overrides |
| Exact cooldowns from the tracker into the planner (`exact_info`) | −0.017 (z −0.28) | |
| Game-length rollouts once two rivals are exactly identified (`partial`) | −0.050 (z −0.30), 24 ms a turn | chaotic rollouts again |

## 6. Playing it yourself

```bash
python zenith/play.py
```

You play seat 1 against three Zenith bots in the terminal (`w a s d` to move, `x` to
stay, `f` to shield). You see the scores, the turn, every cooldown and progress, as a
person at the table would. At the end every one of your moves is graded: accuracy,
critical-move accuracy, the count of each category, and your costliest moves with what
the best move was worth instead. `--opponents apex,fused,zenith` picks the bots;
`--review-bots` grades theirs too. Games and reviews are saved to `zenith/games/`.
A review of a game you beat Zenith in shows exactly which of its moves lost it, and
that is the data the next generation should be graded and built on.

## 7. Honest limits

* **No real human has played Zenith yet.** "Beats humans" here means the human-like
  players, written to beat Apex the way a calm person does. They are a model. `play.py`
  is how to test the real thing.
* **The margins over Apex are real but not large.** +0.10 to +0.25 PW a game where it
  gains, level against indep_v7, evolved and fused copies (which Apex already beat by
  65 to 87%). Zenith is Apex plus fixes at the shield moments and a stealthier
  opening; most of what the grader calls lost value is oracle knowledge no bot has.
  Head-to-head numbers against Apex carry about ±4 points of noise per 200-game run
  (earlier runs read 48 to 57%; the benchmark 57% against copies, 65% in mixed line-ups).
* **Two searches read the wall clock** (exact-world and endgame), inherited from Apex.
  A slower grader shortens rollouts, never answers late. Every number here was
  measured with the clock on, four games in parallel on four cores.
* **The grader's continuation for a human is an engine.** "Your move lost 0.4 PW" means
  "if Zenith finished the game for you from here".

## 8. Reproducing

```bash
python zenith/tests/test_zenith.py          # the bot: rules, simulators, tracker, interfaces, timing
python zenith/tests/test_grader.py          # the grader
bash zenith/lab/benchmark.sh 200 1000       # section 0
bash zenith/grader/runs/campaign1.sh        # section 3 (about 40 minutes on 4 cores)
python zenith/grader/grade.py analyze zenith/grader/runs/evolved_humans.jsonl.gz
python zenith/lab/distill.py tune zenith/grader/runs/evolved_humans.jsonl.gz
python zenith/lab/genarena.py 300 humans --seed=71 base=gen:apex zenith=gen:zenith
```

`genarena.py` plays any bot against any line-up of the previous generations
(`gen:v7`, `gen:indep_v7`, `gen:evolved`, `gen:fused`, `gen:apex`), the human-like
players (`opp:hx_steady`, ...), and every author's field, paired across variants with
hard and soft pairwise wins.

| path | what it is |
|---|---|
| `zenith_bot.py` | the bot, built from `src/` |
| `src/agent.py` | Apex's agent with Zenith's additions (`ZENITH`, the Apex simulator, stealth, dance, veto) |
| `src/evosim.py`, `src/tracker.py`, `src/sim.py` | Apex's simulator of the evolved planner, hidden-state tracker and rollout engine |
| `grader/movegrade.py`, `grader/grade.py` | the move grader and its command line |
| `grader/runs/` | the grading campaign and its data |
| `lab/genarena.py` | the generations arena |
| `lab/humanlike/` | the human-like players |
| `lab/distill.py` | genome tuning on graded positions |
| `lab/benchmark.sh` | the acceptance benchmark |
| `play.py` | play against the bots, then a graded review |
| `tests/` | `test_zenith.py`, `test_grader.py` |
