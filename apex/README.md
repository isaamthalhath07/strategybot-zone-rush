# Apex

A Zone Rush bot built for one job: **beat the evolved bot**
(`research/evolution-2026-11-07:bot.py`, the economic planner that the fused `bot.py` on
`claude/eager-cannon-vq1vca` also plays move for move) without giving anything back against
the rest of the field.

[`apex_bot.py`](apex_bot.py) is one file, standard library only (`collections`, `math`,
`time`), exposing `act(state)` exactly as the starter kit defines it. It is built from
[`src/`](src) by [`build.py`](build.py). To submit it under the required name:

```bash
python apex/build.py bot.py
```

The root `bot.py` on this branch is untouched.

## Results

Paired against the evolved bot on identical games (same map, seats, line-up, token and
`legal_actions` convention), on fresh seeds never used during development, with the shipped
settings (wall clock on). PW is pairwise wins out of 3, the Round 1 unit.

| line-up | games | evolved bot PW | Apex PW | gain | z | Apex vs the evolved bot, head to head |
|---|---|---|---|---|---|---|
| one evolved bot + two from the field | 1,000 | 2.199 | **2.312** | **+0.114** | **+7.6** | **56.2%** of pairings won |
| broad field (three from seven author groups) | 1,000 | 2.490 | **2.535** | **+0.045** | **+3.7** | 57.4% |
| two evolved copies + one from the field | 160 | -- | -- | +0.16 over Apex without exact-world search | +3.6 | 60% |
| three evolved copies | 40 | 1.66 (by symmetry 1.50) | **2.85** | -- | -- | **95%** |

The first two rows are the confirmation runs. The last two are development measurements on
smaller samples (the exact-world search makes those games slow); they are being re-run on fresh
seeds and the rows will be updated.

Credit by opponent author group in the broad-field run (share of one-on-one pairings won):

| | independent v7 author | main's designs | 20 LLM-written | 25 original | research population | shipped bots | weak |
|---|---|---|---|---|---|---|---|
| evolved bot | 89.7% | **90.3%** | 97.0% | 92.0% | 66.8% | 53.6% | 97.4% |
| Apex | **90.0%** | 89.5% | **97.4%** | **93.4%** | **70.2%** | **58.6%** | **98.3%** |

Weakest pairing: main's v7 walk planner, 51.9% for Apex against 57.5% for the evolved bot
(n = 80, about one standard error).

Engineering: worst turn 108.8 ms in the confirmation runs and 102.5 ms with five processes
fighting over four cores (limit 200); mean 3.5 to 4.6 ms in mixed games; first turn under
7 ms (limit 2,000). Zero crashes, zero illegal actions. All eleven server-interface variants
play cleanly.

---

## The evolved bot, scrutinised

Every weakness below was measured, not guessed, and each one maps to a part of Apex.

### 1. It is a pure function of public information

Everything the evolved bot reads -- the board, its seat, whether it holds the token, its legal
actions -- is visible to, or reconstructible by, every rival. Its memory is a deterministic
function of the board history. It uses no randomness and no clock.

So its next move is computable *before it moves*. Apex carries an exact simulator of it
(`EvoSim`) and runs one per rival seat, fed the same observations that rival gets: the shared
board, the rival's seat, the token holder (Apex knows the rotation after at most three turns),
and the rival's legal list rebuilt from Apex's own exact cooldown tracker.

Verified move for move against the evolved bot and the three other public genomes of the same
code (its second-run finalist and two research relatives): 21,200 decisions in the lab, 0
mismatches; section B of the tests repeats it on this branch against a committed copy of the
bot. The fused `bot.py` plays like the evolved bot on the documented interface, so it is
identified too.

A simulator is retired on its first wrong prediction, and trusted only after enough
*evidence*: a matched move or shield counts far more than a matched STAY, because a bot that
mostly stays can match a simulator for a long time by accident. One non-copy reached 42
evidence points before diverging; true copies reach 72 to 82 over a game. Predictions drive
tactics from 14 points, and the exact-world search (below) needs 30 on every rival.

### 2. Its defence is a threshold rule a predictor can read

It shields when an estimated threat clears `(1 + backfire x miss) x max(1, 0.49 x best_rate)`.
Early in the game a raid on one of its level-1 cells usually does not clear that bar; on an
upgraded cell it fires on the raider's third stay. It feints (steps off a rival's cell to bait
a shield) whenever its learned "this rival shields" rate is above 0.344 -- which is true of
every rival at the start of a game.

Against a predicted rival none of this is a gamble any more. Apex never stays on the evolved
bot's land on a turn it is about to shield -- it steps off, so the shield backfires (two frozen
turns and a four-turn cooldown for the evolved bot) -- and never shields into its feints (a
predicted step-off is p(stay) = 0.03, not the prior 0.76). That layer alone, on top of the
evolved bot's own planner, lifts pairwise credit against three evolved copies from 46% to 61%
(+0.455 PW, z = +7.4).

### 3. It raids inside cooldown windows

61 of the 65 successful evolved raids on Apex in the diagnostic games landed while Apex's
shield was cooling down: the evolved bot tracks cooldowns and walks in right after a shield.
Apex's planner does the same to it and to everyone else, on cooldowns its tracker gets right
99.5% of the time against engine ground truth.

Closing that window by replacing the inherited shield rule was tried and lost (see "What did
not work"): the shields that open it are the ones that stop weaker raiders four times a game,
and they are worth more than the half cell a game the evolved bot takes back.

### 4. When every rival is a copy, the whole game is predictable

With three copies at the table the game is deterministic from Apex's point of view, so Apex
switches to *exact-world search*: every candidate action is played out to the end of the game
with exact simulators in all four seats (its own continuation included), and the one with the
best expected pairwise result is played. One-step policy improvement over a perfect model is a
guaranteed improvement, and it shows. Rollouts only change about 6% of decisions -- a third of
them in the first ten turns, mostly "keep walking to the contested 3-point cells instead of
stopping for a cheap one" -- and that is enough to win almost every game.

### 5. It is myopic about the end of the game

A rate planner with one job of lookahead cannot see that the last twenty turns are a race of
raids whose bonuses do not decay and claims that are worth almost nothing. Apex searches the
endgame: from 20 turns out it rolls every candidate action forward to turn 80, with exact
simulators for identified rivals and, for everyone else, whichever of five behaviour models has
predicted that rival best so far (online model selection between the evolved planner itself, a
claim-first farmer, an upgrade-heavy farmer, a raider and a shield-on-sight guard). Worth
+0.077 PW on mixed lineups (z = +5.0).

### 6. It opens by upgrading a cheap home

Its value function caps every cell's income horizon at about 41 to 58 turns, except homes,
which get 100. On maps with a 2-point home it spends turns 1 to 3 upgrading it. The exact-world
search overrides exactly that whenever it can see the consequences.

### 7. Engineering

From the cross-branch review: no exception handling anywhere in `act()`; the skeleton's score
on five of eleven plausible interface variants; 23% lost if module memory is lost. Apex handles
all eleven variants with zero bad turns, keeps an independent copy of the evolved planner warm
every turn as a backup, and has a stateless fallback below that which still farms.

---

## How Apex works

One decision, in order. Each layer can only refine the one before it, and each runs inside its
own guard.

| layer | what it does | file |
|---|---|---|
| **normalise** | accepts the documented state and ten variants of it (flat or nested board; objects, dicts or tuples; 0/1 or string flags; string `bot_id`; lower-case or enum actions; no token flag) and always answers with the server's own legal-action object | `agent.py` |
| **tracker** | rebuilds turn, all four scores, every bot's capture progress, freeze counters, shield cooldowns and the token holder from board diffs. Shields are attributed by a constraint solver -- every subset of seats that could have shielded, kept only if it reproduces the observed freezes exactly, and a shielder cannot lose a cell that turn -- with the simulators' predictions as tie-break | `tracker.py` |
| **simulator bank** | one exact simulator per rival seat for each of four public genomes; retired on the first wrong prediction, trusted on evidence | `evosim.py`, `agent.py` |
| **behaviour models** | for rivals no simulator explains: five candidate policies scored online by how well they predict that rival, plus Beta estimates of how often it commits to a raid, shields, and raids at all | `agent.py` |
| **base plan** | the evolved planner itself, on Apex's own seat -- the strongest planner measured in this repository | `evosim.py` |
| **tactics** | prediction-aware: never stay where the owner is about to shield (step off and let it backfire); add a shield when a predicted or likely completing raid is worth more than the turn, the progress it discards and the cooldown it opens | `agent.py` |
| **exact-world search** | every rival a trusted simulator: roll every candidate to the end of the game, all four seats simulated | `agent.py`, `sim.py` |
| **endgame search** | last 20 turns: the same rollouts, rivals modelled | `agent.py`, `sim.py` |
| **safety net** | a second, independent copy of the evolved planner runs every turn; a stateless farmer below it; `STAY` last | `agent.py` |

The rollouts run on `sim.py`, a compact copy of the rules checked state by state against
`engine.py` (section A of the tests: 300 random games with shields, identical every turn).
Time is guarded twice: the search stops launching rollouts as the turn's 100 ms internal
deadline approaches, and checks the clock inside a rollout every four simulated turns. The game
allows 200 ms.

### Why the search is confined to those two situations

Deterministic rollouts are chaotic. A one-turn difference in a prediction cascades, and
candidate values swing from 0.01 to 2.3 on tiny changes. With an exact model that chaos is real
and Apex exploits it; with an approximate model it is noise and the bot paces. Full-game
rollouts with approximate rival models lose 1.15 pairwise wins a game. The endgame window
peaks at 20 turns: 30 already loses ground and 55 collapses. Near the end the rollouts reach a
true terminal score within a horizon short enough that model errors cannot compound.

---

## What did not work

All paired on the lab field, PW out of 3.

| idea | result | what it taught |
|---|---|---|
| **Full-game rollouts with approximate models** for rivals that are not copies (the evolved planner as a proxy) | **-1.15 PW** (z = -15.4); 35% credit, 12% against the evolved bot | the decisive negative: rollouts are only as good as the model, and long deterministic rollouts amplify every model error |
| A short exact horizon then a cheap greedy policy to the end | about 1,600 points instead of 2,700; the bot paced | the tail's misjudgement is systematic and shifts every turn |
| Short exact horizons cut off with "score + income x turns left", against exact copies | h8 43%, h15 67%, h25 85%, full game 100% | the cutoff ignores future work, so routes are misvalued; only a true terminal is reliable |
| Endgame windows wider than 20 turns | 24: -0.022, 30: -0.032, 40: -0.120, 55: -0.320 | the same compounding, measured |
| Replacing the inherited shield rule with one that prices the cooldown window | 85% vs 91% credit against main's designs | the inherited rule's shields stop raiders four times a game |
| Simulator trust after 6 matching moves | a non-copy matched 50 | evidence weighting |
| Home retention 50 / 30 instead of 100; preferring 3-point cells (value^1.3) | -0.003 / +0.013 / +0.028 | noise |
| Value-function temperature 60 / 250 instead of 120 | +0.007 / 0.000 | noise |
| Nine generations of genome tuning with a confirmation stage | one accept (late-raid weight 1.64 -> 2.48, +0.029 on fresh games), which no longer helped once the endgame search existed | the planner sits near a local optimum on this field; the gains are in what the planner cannot see |

---

## Honest limits

- **The field is still this repository's.** It is broad -- seven author groups, 92
  opponents including 20 pasted from ChatGPT and Gemini, six map families, both `legal_actions`
  conventions -- but no real competitor's code has been played against.
- **The largest margins need copies of public bots at the table.** Against three evolved
  copies Apex wins almost every game; against a field with one evolved bot in it, the margin is
  the head-to-head row above. Against bots it cannot simulate, the gain comes from the endgame
  search and the tactics, not from prediction.
- **Two modes read the wall clock** (exact-world and endgame search), so those decisions can
  differ on a slower machine: a slower grader gets shorter rollouts, never a late answer. Every
  measurement here was made with the clock on, as shipped.
- **Prediction is not identification.** A bot that copies the evolved planner's moves for 30
  evidence points and then deviates will mislead the exact-world search until it deviates. The
  measured cost of that, in lineups built to provoke it, is positive overall (the search's gains
  outweigh it), but it is not zero.

---

## Reproducing

On this branch alone:

```bash
python apex/tests/test_apex.py
```

The suite needs nothing but this branch: the in-bot rules engine against `engine.py`, the
simulator bank against a committed copy of the evolved bot (`tests/fixtures/evolved_bot.py`,
byte-identical to `research/evolution-2026-11-07:bot.py`), the tracker against the engine's
hidden state, eleven interface variants and a module reloaded every turn, module reuse across
seats and games, the safety net with the agent forced to raise, wall-clock timing with every
expensive mode active, and the static checks. Edit `src/*.py`, never `apex_bot.py`; `build.py`
regenerates it.

The strength numbers need the cross-branch field, which lives on two other branches.
`lab/setup_lab.sh` assembles it in a separate worktree, pinned to the exact commits measured:

```bash
bash apex/lab/setup_lab.sh ../apex-lab
```

```bash
cd ../apex-lab && python zarena.py 1000 h2h --seed=102 --per evolved=opp:evolved apex=file:apex/apex_bot.py
```

`zarena.py` modes: `field` (three opponents sampled group-first from seven author groups),
`h2h` (the evolved bot plus two field opponents), `duo` (two evolved copies plus one), `trio`
(three evolved copies), `mix` (half `h2h`, half `field`). Every variant on one command line
plays the identical task list -- map, seats, line-up, token, `legal_actions` convention -- and
differences come with a paired standard error. `vsEvo` is pairwise credit against every seat
the evolved bot played. `zdiag.py` counts claims, upgrades, raids, shields, freezes and raid
flows between bots; `tune_apex.py` is the confirmation-stage tuner; `lab/apex/` holds the
lab-side checks (simulator bank against every public genome, tracker accuracy, false-trust
rates).
