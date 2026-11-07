# Zone Rush, explained from scratch

This is the long-form companion to `README.md`. The readme says what was built
and what the numbers are; this document explains **the game, the arithmetic that
governs it, every strategy anyone could play, what each one actually does, and
what every file in the repository is for** — starting from no prior knowledge.

Everything factual about the rules comes from the official rulebook (Section 2)
and the starter kit at `github.com/RedPokerJoker123/StrategyBot`, plus three
answers the organisers gave directly. Everything factual about strategy is
measured in this repository, and where a number is quoted it says how it was
measured. Where something is my judgement rather than a measurement, it says so.

A note on scope: there are two branches, `main` and `hardened-field-and-fixes`.
History is linear — the branch is `main` plus one commit — so nothing exists on
`main` that is not also on the branch. This document describes the branch.

**Contents**

1. [The game](#1-the-game)
2. [The arithmetic that decides everything](#2-the-arithmetic-that-decides-everything)
3. [What kind of game this is](#3-what-kind-of-game-this-is)
4. [Every strategy, and what it actually does](#4-every-strategy-and-what-it-actually-does)
5. [How this bot works](#5-how-this-bot-works)
6. [Every parameter, and what it controls](#6-every-parameter-and-what-it-controls)
7. [Every file in the repository](#7-every-file-in-the-repository)
8. [How anything here gets measured](#8-how-anything-here-gets-measured)
9. [Results, and everything that failed](#9-results-and-everything-that-failed)
10. [What is still open](#10-what-is-still-open)

---

## 1. The game

### 1.1 The board

An **8 × 8 grid**, 64 cells. Four bots, one per corner. **80 turns**, then the
highest cumulative score wins.

Coordinates are Python row–column: `(0, 0)` is top-left, `(i, j)` means row `i`,
column `j`. The four homes are:

| seat | corner | flat index |
|---|---|---|
| 1 | (0, 0) top-left | 0 |
| 2 | (0, 7) top-right | 7 |
| 3 | (7, 7) bottom-right | 63 |
| 4 | (7, 0) bottom-left | 56 |

Every cell has a **base value** of 1, 2 or 3 points per turn. Maps vary but are
always **four-fold mirrored** — the top-left 4 × 4 quadrant is reflected into the
other three — and values rise toward the middle. Homes are cheap (1 or 2).

On the canonical map the quadrant is

```
1 1 1 2
1 1 2 2
1 2 2 3
2 2 3 3
```

which over the whole board gives **24 cells worth 1, 28 worth 2, and 12 worth 3**.
Four of the 1s are homes, so 60 cells are up for grabs. If a single bot somehow
owned everything at level 1 it would earn 116 points per turn; doubled by
upgrades, 232. Nobody comes close — the best unopposed score measured here is
3551 over 80 turns, an average of 44 per turn.

The mirroring matters more than it looks. It means **the four seats play
geometrically identical games**, which in turn means any difference in a bot's
results between seats is that bot's own bug. That fact is used as a test — see
[§8.4](#84-symmetry-as-a-correctness-test).

### 1.2 The six actions

Every turn, all four bots choose **simultaneously** from:

`NORTH` `EAST` `SOUTH` `WEST` `STAY` `SHIELD`

`NORTH` is row − 1 (up the screen), `SOUTH` is row + 1. No diagonals, no moving
off the board. The server hands your bot the list of actions that are currently
legal, and `STAY` is always in it.

### 1.3 How a turn resolves

The order is fixed and it matters enormously:

1. **Moves and shields.** Bots move or stay; shields go up.
2. **Takes, upgrades and freezes.** Cells change hands, upgrades complete,
   caught bots freeze.
3. **Scoring.** Every bot scores the land it owns.
4. **The priority token passes** to the next seat (1 → 2 → 3 → 4 → 1).

Because scoring happens *after* takes, a cell you capture on turn *t* pays you on
turn *t* as well. Because shields resolve *before* takes, a shield cancels a
capture that would otherwise have completed that same turn. Both are load-bearing
for strategy.

### 1.4 Movement, blocking, and contested cells

- **Closed cells.** A cell with a bot on it *at the start of the turn* cannot be
  entered — even if that bot is moving away. So **bots can never swap places**.
- **Contested cells.** If two or more bots move into the same empty cell:
  - if one of them **owns** the cell, it gets it;
  - otherwise the bot that comes **first in seat order counting from the
    priority-token holder** gets it;
  - the others stay where they are.
- **A blocked or lost move counts as `STAY`.** This is not a technicality: it
  means a bot that tried to move and failed still accrues capture progress on the
  cell it is standing on.

The **priority token** only ever matters for that tie-break. One seat holds it
each turn and it rotates every turn, so each seat holds it one turn in four, and
every bot can compute exactly which turns those are.

### 1.5 Capturing cells

**`STAY` on a cell that isn't yours and it becomes yours, at level 1.** Arriving
does not count — only the turns you *stay* there.

| cell you stay on | stays needed | you get |
|---|---|---|
| neutral | **1** | the cell at level 1 |
| a rival's **level-1** cell | **1** | the cell at level 1, **plus a raid bonus** |
| a rival's **upgraded** cell | **3** | the cell at level 1, **plus a raid bonus** |
| a rival's **home** | — | nothing, ever. Homes cannot be captured |

**The raid bonus** is a one-off payment of `8 × base × previous level`. A rival's
upgraded 3-point cell pays `8 × 3 × 2 = 48` points the instant you take it.
Capturing *neutral* ground pays no bonus.

**Progress resets to zero** when you move off the cell, when you `SHIELD`, and
when you are frozen.

That a rival's level-1 cell costs **one** stay — exactly as cheap as neutral
ground — while still paying the full bonus, is the single most under-appreciated
line in the rulebook. See [§2.4](#24-why-level-1-cells-are-the-best-raid-targets).

### 1.6 Upgrading

**`STAY` three turns on your own level-1 cell** and it becomes level 2, worth
double. A cell that is captured always drops back to level 1.

Homes can be upgraded like any other cell, and since homes can never be captured,
**an upgraded home is the only permanently safe doubling on the board.** (It is
also nearly worthless, because homes are worth 1 or 2 — see
[§9.2](#92-tested-and-found-not-to-work).)

### 1.7 Shield, freeze, backfire, cooldown

Instead of moving you may `SHIELD`. For that turn:

- **none of your cells can be captured** — all of them, not just the one you are
  standing on; and
- **every rival staying on your territory** (your home included) loses its
  progress and is **frozen for 2 turns**.

With four consequences:

- **Frozen:** the bot can only `STAY`; its chosen action is ignored.
- **Backfire:** a shield that catches nobody freezes *you* for 2 turns. Rivals
  who are already frozen cannot be caught again, so a shield that reaches only
  frozen rivals also backfires.
- **Cooldown:** after shielding you cannot shield again for **4 turns**.
- **No progress:** a shield turn is not a stay, so it gives no capture or upgrade
  progress — and it *resets* whatever progress you had.

### 1.8 Scoring and how Round 1 is ranked

At the end of every turn each bot scores the value of every cell it owns, doubled
for upgraded cells. Raid bonuses are added when they happen. After 80 turns the
highest total wins; ties share a place. Nobody is eliminated.

Round 1 ranks by **Elo**, and the adaptation is the important part: **each
four-bot game counts as three one-on-one results.** Finishing above a bot is a
win against it, below is a loss, equal is a draw. So 1st place is 3 wins, 2nd is
2 wins and 1 loss, 3rd is 1 and 2, 4th is 0 and 3.

Two consequences that shape everything downstream:

- **Margin is worthless.** Beating a rival by 1 point and by 1000 points are the
  same result. What matters is *how many rivals you finish above*.
- **The natural objective is expected pairwise wins out of 3.** Every measurement
  in this repository is in that unit, written `PW`. 1.50 is the break-even value
  of a symmetric four-way game.

### 1.9 What your bot can see — and what it cannot

Your bot is one Python file exposing `act(state)`, standard library only, called
once per turn. 200 ms per turn, 2 s on the first turn. A bot that crashes, runs
late, or returns an illegal action plays `STAY` for that turn.

`state` gives you exactly four things:

| field | meaning |
|---|---|
| `state.board` | 8 × 8 list of lists of `Cell` |
| `state.bot_id` | your seat, 1–4 |
| `state.is_priority_token` | whether **you** hold the token this turn |
| `state.legal_actions` | the actions available to you now |

And each `Cell` gives exactly six:

| field | meaning |
|---|---|
| `occupant` | seat standing here, 0 if empty |
| `owner` | seat owning it, 0 if neutral |
| `is_upgraded` | level 2? |
| `is_home` | is this one of the four homes? |
| `is_frozen` | frozen status of the bot standing here |
| `base_points` | 1, 2 or 3 |

Now the interesting part — **everything the state object does *not* tell you**:

- the **turn number**
- **anyone's score**, including your own
- **anyone's capture or upgrade progress**, including your own
- **anyone's shield cooldown**, including your own
- **how many turns** a frozen bot still has to serve
- **which seat holds the token**, unless it is you
- any history at all

Every one of those is strategically decisive, and every one of them can be
reconstructed from the sequence of boards you *do* see. That reconstruction is the
largest single source of strength in this bot — worth **0.77 PW** when measured
by taking it away ([§5.1](#51-the-tracker-rebuilding-what-the-server-hides)).

The organisers confirmed that keeping state between turns is **allowed**, with the
caveat that handling blocked or illegal moves is the entrant's problem.

### 1.10 The five ambiguities, and how each was settled

The starter kit ships no engine, so `engine.py` had to encode a reading of five
rules the rulebook leaves genuinely open. All five are flags in `engine.RULES` so
both readings can be tested. **All five turned out to match the default reading**,
so no strategy work had to be redone.

| # | question | answer | how it was settled |
|---|---|---|---|
| 1 | Does a frozen bot's forced `STAY` accrue progress? | **No** | organisers, asked directly |
| 2 | After capturing, does progress reset? | **Yes** → 4 stays to own *and* upgrade a neutral cell | starter README rules 5 + 7; also detected at runtime |
| 3 | Does losing a contested race count as a `STAY`? | **Yes** | starter README rule 4: "Unsuccessful moves count as `STAY`" |
| 4 | Can a bot `SHIELD` on rival land to dodge the catch? | **Yes** — a shield is not a stay | starter README rule 8 |
| 5 | Can a home be upgraded? | **Yes**, and it still cannot be captured | starter README rule 7 |

Question 2 is the only one answered by inference rather than by a direct
statement, and it is the one that changes the arithmetic (4 stays versus 3 to own
and upgrade a neutral cell). So the bot does not rely on my reading: it
**measures the rule off the board at runtime**, by watching any bot capture a
cell and counting the stays until the upgrade appears. It settles in about seven
turns and is correct in 10/10 games under *either* reading
(`test_guards.py`, section A).

---

## 2. The arithmetic that decides everything

Almost every strategic question in this game is settled by one calculation, so it
is worth doing slowly.

### 2.1 Action-turns are the scarce resource

You have exactly **80 actions**. Moving produces nothing directly. Shielding
produces nothing directly. **Only `STAY` converts an action into permanent
income**, by completing a capture or an upgrade.

So the whole game is: *maximise the income you own, integrated over the turns
remaining, subject to a budget of 80 actions and the travel costs between cells.*

### 2.2 What each piece of work is worth

Let `v` be a cell's base value and `R` the turns remaining (including this one).

| work | stays | pays |
|---|---|---|
| claim a neutral cell | 1 | `v × (R − 1)` income |
| upgrade your own level-1 cell | 3 | another `v × (R − 3)` income |
| raid a rival's **level-1** cell | 1 | `8v` **one-off** + `v × (R − 1)` income + their loss |
| raid a rival's **upgraded** cell | 3 | `16v` **one-off** + `v × (R − 3)` income + their loss |

Two features of that table drive everything:

- **Income decays with the clock.** A claim on turn 10 is worth seven times a
  claim on turn 70. Claiming is an early-game activity.
- **The raid bonus does not decay at all.** `8v` is `8v` whether it lands on turn
  5 or turn 80. Raiding is therefore worth *far* more late than early — which is
  why a single "raid weight" cannot express the truth, and why this bot carries
  two (`w_raid` and `w_raid_late`, interpolated by the clock).

### 2.3 Claim or upgrade?

Work it through on a 3-point cell at turn 10 (`R = 71`):

- claim it: 1 stay → `3 × 70 = 210` points
- then upgrade it: 3 stays → `3 × 67 = 201` points, i.e. **67 per stay**
- instead, walk one step and claim another 3-pointer: 2 actions → `3 × 68 = 204`,
  i.e. **102 per action**

So **while unclaimed high-value cells are within a step or two, claiming wins by
roughly 50%.** Once the neighbourhood is claimed, travel costs rise and upgrading
becomes the better rate. The crossover is not a fixed turn; it depends on how much
unclaimed ground is near you.

This is exactly what a pure rate-ranking bot discovers on its own, and it is why
`probot.py` scores **3551 unopposed** against this bot's 3276: unopposed, there is
always more neutral ground, so claim-first is simply correct, and the defensive
habits that make this bot strong in a real game are dead weight.

### 2.4 Why level-1 cells are the best raid targets

Per stay spent:

| target | stays | bonus | bonus per stay |
|---|---|---|---|
| rival level-1, `v = 3` | 1 | 24 | **24** |
| rival upgraded, `v = 3` | 3 | 48 | **16** |

A level-1 cell is **1.5× more efficient to raid** than an upgraded one, and it
costs exactly as many stays as claiming neutral ground while paying a bonus on
top. Against an opponent sitting on a sprawl of un-upgraded cells, raiding
strictly dominates claiming.

### 2.5 Why upgrading is also a defence

Turn that around. Upgrading your own cell:

- doubles its income, **and**
- raises the price of taking it from **1 stay to 3**, **and**
- means an attacker who does take it has spent 3 of their 80 actions.

So upgrading buys income *and* durability. The cost is that it doubles the bounty
on the cell — `16v` instead of `8v` — which is a real consideration this bot
expresses as `upg_risk`, measured at a small but genuine **+0.008 PW (z = +2.47)**
on the discriminating field.

This is the resolution of an apparent contradiction. Unopposed, claim-first wins;
in a contested game this bot's tuned weights prefer upgrading (`w_upgrade 1.34`
against `w_claim 0.85`). Both are correct for their setting. The 275-point gap in
unopposed score is the premium paid for durability.

### 2.6 An upgraded cell can be defended forever

This one is a genuine discovery from the rules, not a measurement.

A raider needs **3 consecutive stays** to take an upgraded cell. You need **one
shield** anywhere in that window to reset it. Your cooldown is 4 turns. Can one
defender hold one cell against one raider indefinitely?

Walk it through. The raider arrives at `t0` and must stay at `t1, t2, t3`.

- You shield at `t1`. The raider's progress resets and it freezes for 2 turns.
- Your cooldown blocks `t2, t3, t4, t5`; you can shield again at `t6`.
- The raider is frozen through `t2`, thaws at `t3`, and must stay `t4, t5, t6` to
  complete a fresh attempt.
- It completes at the end of `t6` — and you can shield at `t6`.

**Yes.** One shield per five turns holds the territory. The cost is about one
action-turn in five, against an attacker spending *all* of theirs. Compact
upgraded clusters are, in principle, nearly impregnable.

The honest caveat, from measurement: it matters less than the arithmetic suggests,
because most losses happen while your shield is *already* on cooldown or while you
are frozen. `diag_loss.py` counts the ceiling on better defence at **about one
cell per game** ([§9.3](#93-defence-has-a-ceiling)).

**The converse, which v7 missed: a level-1 cell cannot be defended at all.** Run
the same walk with a raider that needs **one** stay. You shield at `t1`; it is
frozen through `t2`; it stays at `t3` and takes the cell — while your cooldown
still blocks `t2` to `t5`. Freeze (2) plus one stay is 3, which is not more than
the cooldown (4), so the shield buys three turns, not the cell. For an upgraded
cell it is 2 + 3 = 5 > 4, which is why that one holds.

v7 still valued a level-1 shield as if it saved the cell for the rest of the game
(57 points at 40 turns left, against a real 9). Measured, **79–89%** of the
level-1 cells it shielded were taken by the same raider within six turns anyway.
v8 stops spending shields there (`shield_l1: 0`); see
[`strategy_audit/README.md`](strategy_audit/README.md), finding B2.

### 2.7 The cooldown window is the real exploit

When any bot shields, **its entire territory is undefendable for the next four
turns.** A bot that tracks rival cooldowns can time its raids into those windows
and take cells with *no* risk of interception.

There is a sharper version. Deliberately walk onto a rival's level-1 cell and let
them shield you. You freeze for 2 turns, thawing at `t+2`. You are already
standing on the cell. You stay at `t+3` — one stay is all a level-1 cell needs —
and their cooldown (blocking `t+1` through `t+4`) means they cannot stop you.
**You have bought a guaranteed capture for two frozen turns.**

This is the mechanism that makes late raiding profitable *for a bot that can model
it*, and the clearest evidence for that is a disagreement between two independently
tuned bots:

| | this bot (v6) | the independent rival, tuned |
|---|---|---|
| `w_raid` | 1.52 | 0.69 |
| raid weight late in the game | **1.92** (raids more) | **0.20, at its floor** (raids less) |
| trust in the raid bonus | — | 0.49 (halves it) |

Opposite conclusions, and the explanation is *capability*, not strategy. This bot
reconstructs every rival's cooldown and prices each raid's interception risk, so it
can pick the safe raids. The rival's cooldown multipliers tuned to ineffective, so
for it raiding is simply unprofitable and its tuner correctly drove the weight to
zero.

### 2.8 Timing at the end of the game

- A claim completing on the final turn earns `v × 0` — **nothing**. The bot's
  value function returns `None` for work that cannot pay, so it correctly ignores
  it.
- A **raid** completing on the final turn still pays its full `8v × level` bonus.
  So the last few turns should be spent raiding, not claiming.
- In the last turn or two a **backfiring shield costs nothing** — there is no
  cooldown left to burn and no future turns to lose — so shielding becomes free
  and should be used to deny anything deniable. That is the `free_shield_turns`
  parameter.

---

## 3. What kind of game this is

### 3.1 It is not a minimax game

Minimax, alpha–beta, and ordinary game-tree search assume **alternating** moves
with **perfect information**. Zone Rush is neither:

- all four bots move **simultaneously**, so there is no "opponent's turn" to
  minimise over; and
- the state is **partially observed** (§1.9).

Applying minimax here means inventing a move order that does not exist. The
formally correct objects are:

- **locally**, a *matrix game*: all four bots pick actions at once and the payoff
  depends on the joint choice. For the shield/raid stand-off this is small enough
  to solve exactly, and this bot does ([§5.3](#53-the-shieldraid-stand-off-as-a-matrix-game)).
- **globally**, a *receding-horizon planning problem*: choose a sequence of work
  that maximises income integrated to turn 80, re-planning every turn as the board
  changes. That is what the walk planner does
  ([§5.2](#52-the-walk-planner-routes-not-targets)).

### 3.2 Four players, general sum — so attacking is usually a mistake

With four bots, hurting one rival helps the other two as much as it helps you.
Spending an action to knock 50 points off the leader improves your *margin*
against them, but it equally improves the margin of the two bots you ignored.

This is why the tuner, repeatedly and across every version, drove rival-targeting
to zero: `care_mode` settled on **4 (uniform — ignore who the rival is)** and
`w_denial` on **0.22, then 0.00**. Maximising your own absolute score is a better
proxy for placement than any margin objective, because the denial term's benefit
is shared with your other opponents.

### 3.3 Elo is pairwise, and the game is non-transitive

Because each game yields three one-on-one results, strength is not a single
number. Measured here:

| focus bot | vs 3× pro_tuned | vs 3× spine | vs 3× ai_hawk | vs 3× camper |
|---|---|---|---|---|
| **v6** | **0.81** | 1.85 | 2.31 | 2.81 |
| **pro_tuned** | 1.25 | **0.89** | 2.22 | 2.03 |

Rock-paper-scissors: pro_tuned beats v6, v6 beats spine, spine beats pro_tuned.

Two things follow, and both changed how this project measures:

1. **"Three identical copies" is not a model of the Round 1 field**, which mixes
   opponents and seats. A bot can be destroyed by three copies of a design it
   would rarely meet twice in one game.
2. **There is no "strongest bot" in the abstract** — only strongest against a
   given distribution of opponents. Which makes the *field you assume* the single
   most important modelling choice in the whole project, more important than the
   algorithm.

---

## 4. Every strategy, and what it actually does

### 4.1 The strategy space

Strip away implementation and the game admits a handful of genuinely distinct
plans. Everything anyone can play is a blend of these:

| plan | what it means | does it work? |
|---|---|---|
| **Farm your quadrant** | claim the nearest good cells, upgrade them, stay home | **Yes — this is the core.** Low variance, high score |
| **Rush the centre** | sprint for the four 3-point middle cells and hold them | No. Six turns of zero income is not recoverable |
| **Raid continuously** | live off `8v` bonuses | No. Dominated once opponents can shield |
| **Raid opportunistically** | farm, but take cells whose owner cannot defend | **Yes** — this is where the hidden-state model pays |
| **Fortress** | small compact cluster, everything upgraded, shield-cycle to hold | Partly. Sound in theory; defence ceiling is ~1 cell/game |
| **Turtle** | claim only near home, never contest | Playable, slightly weak — forfeits the valuable middle |
| **Bait** | draw shields deliberately, harvest the cooldown | Real but thin. Costs 2 frozen turns for one guaranteed cell |
| **Hunt the leader** | spend actions attacking whoever is ahead | **No.** Four-player general-sum punishes it (§3.2) |
| **Deny** | take cells to reduce a rival rather than to gain | No. Benefit shared with your other two rivals |
| **Endgame pairwise** | late on, target the one rival you can still overtake | Inert as implemented — see §9.2 |
| **Steal the centre early** | take a *rival's* best cells before they arrive | Measured, lost. Tuned to zero |
| **Upgrade home** | the only unraidable doubling | Measured, **harmful** (−0.053 PW). Homes are worth 1–2 |

The tuned answer is a specific blend: **farm your own quadrant preferring
upgrades, ignore who your rivals are, and raid opportunistically when you can see
that the owner cannot answer.**

### 4.2 The macro-strategy sweep

`strategies.py` exists because v1–v5 were all the same strategy with different
weights. It writes out the genuinely distinct *plans* as overlays on tuned weights
and scores each against three different fields with common random numbers, so the
comparison is between plans rather than between lucky draws. 18 named plans were
run. The findings that survived:

- **"Ignore rivals"** (`care_mode: 4`, `w_denial: 0`) was the biggest single
  macro win, and it is now the shipped default.
- **"Deep search"** (more visits, longer horizon, wider beam) helped, and the
  `visits` component of it turned out to be the real driver — see §5.2.
- **"Claim+upgrade combo"** was ambiguous then. It has since been shown to be a
  **false negative** caused by a saturated measurement field, and measures
  **+0.063 PW** on the discriminating field (§8.3).
- **"Centre rush"**, **"hunt the leader"** and **"steal"** all lost.

### 4.3 The opponents, and what each one represents

The field is not decoration — it *is* the objective function, since strength only
exists relative to a distribution of opponents. It is built in three tiers
(`field.py`).

#### Tier 1: the original archetypes (`zoo.py`)

These were invented to have something to measure against, and each encodes one
plausible design.

| bot | strategy | what it is for |
|---|---|---|
| `stay` | the unmodified skeleton | the floor. A bot that crashes plays exactly this |
| `random` | random legal actions, 5% shields | noise floor |
| `greedy` | nearest-highest-value claiming, `base / cost` ranking, never shields | **my prediction of the modal unprompted-LLM bot** |
| `greedyshield` | same economics, shields the instant a rival sets foot on its land | the same bot with the obvious defensive reflex |
| `pacifist` | claims only neutral ground, never raids, shields on sight | tests whether raiding is needed at all |
| `spine` | walks the high-value corridor out of home claiming as it goes, upgrades 2+ cells on arrival, backfills cheap cells last, stays in its quadrant, disciplined shields | **the optimal-route farmer from §2.** The strongest hand-written bot: 2610 solo, and the hardest opponent in the original zoo |
| `raider` | farms 24 turns then hunts rival level-1 cells by bonus-per-turn | tests the raid-heavy plan |
| `camper` | grabs its best 8 cells, upgrades them, then squats the best one and shields hard | the fortress plan, and the natural counter to raiders — occupancy *is* immunity, since an occupied cell cannot be entered |
| `baiter` | steps onto rival land, then steps off ~80% of the time before the capture completes | **an attack on my own bot.** Exists to verify this bot cannot be farmed by a predictable shield reflex |

#### Tier 2: the held-out archetypes (`holdout.py`)

These are **never** in any tuning field. They are the overfitting test: if tuned
weights only beat the bots they were tuned against, these will show it.

| bot | strategy |
|---|---|
| `turtle` | claims only within 4 steps of home, upgrades everything, strict shield rule. The "play it safe" design, extremely low variance |
| `hunter` | farms, but always raids whoever is currently winning — tracks scores itself |
| `centre` | sprints for the middle four cells, holds and upgrades them, fights there |
| `cdraider` | **tracks rival shield cooldowns and raids only inside the windows.** Deliberately the design I argue is the strongest available exploit, written as an opponent so my bot has to face it |

#### Tier 3: the AI-field designs (`aifield.py`)

Written after the realisation that the original zoo ignored two rule facts
entirely — that a rival's level-1 cell costs one stay, and that homes can be
upgraded but never captured. Each of these is a serious attempt at what a
well-prompted assistant would actually land on.

| bot | strategy |
|---|---|
| `ai_marginal` | textbook marginal value: rank all work by points per action-turn. A genuinely strong baseline — **3548 solo** |
| `ai_cheapraid` | lives off the one-stay level-1 raid, strongly prefers victims whose shield is on cooldown |
| `ai_homefort` | upgrades its home first, then grows an upgraded cluster outward. Very low variance |
| `ai_centre` | takes and upgrades the four centre 3-pointers |
| `ai_route` | chains the next three work-cells, paying real travel between them |
| `ai_hawk` | farms until a rival burns its shield, then swarms that rival for four turns |
| `ai_elo` | farms, then in the last 18 turns spends actions only on pairings it can still flip |

All of them share a correctly-reasoned defensive rule — shield only when a rival
is *imminently* completing a capture (it has already banked `need − 1` stays) and
the threat clears a value floor. Shielding on sight, which the original zoo did,
burns the cooldown and backfires constantly.

#### Tier 4: the independent rival (`probot.py`)

The most important opponent in the repository, and the answer to the honest
objection that every other strong bot here is either mine or invented by me.

It is a **rate ranker, not a route planner** — a different architecture — with its
own 15 tunable weights and its own tuner (`tune_rival.py`), trained against a
field that deliberately excludes itself. Unopposed it **outscores this bot, 3551
to 3276**, because it pays nothing for defensive habits. Tuned, it beats this bot
**0.81 of 3**.

Its value is twofold. It is a genuine threat in the training field, and because it
was tuned independently, where it *agrees* with this bot is real corroboration
rather than an echo:

| its tuned weight | direction | agrees with |
|---|---|---|
| `w_upgrade` +47% | prefer upgrading | this bot's `w_upgrade` ≫ effective raid weight |
| `w_raid` −46% | raiding is overrated | same conclusion |
| `shield_floor` +72% | shield rarely | `shield_bias` pinned high |
| `home_pref` −34% | home upgrades are poor | the measured −0.053 PW |
| `compact` pinned at 0 | no compactness preference | `zone_bonus` ≈ 1.07, neutral |
| `centre` 0.04 | no centre pull | the centre-rush plan losing |

Every strategic conclusion in this project was previously measured with my planner
against my field. A structurally different bot, tuned separately, reaching the
same conclusions is the strongest available evidence they are about the *game* and
not about my assumptions.

#### The counter-bots (`snapshots.json`)

`nemesis1`–`nemesis3` are this bot's own architecture, tuned specifically to
**beat a named version of itself** (`tune.py counter:v6`). They measure
exploitability: how much edge a dedicated attacker can get against a version.
1.50 of 3 means no edge at all. v3 measures 1.72; v6 measures 2.17 — v6 is the
stronger bot *and* the more exploitable one.

That trade-off was a real decision, and the reason for taking it was that no
competing team had the source to breed a counter-bot from. **That reason no longer
holds** — the repository is public — which is why a differently-architected
attacker like `pro_tuned` now carries the highest weight in the training field.

---

## 5. How this bot works

Four mechanisms, in order of measured importance.

### 5.1 The Tracker: rebuilding what the server hides

Worth **0.77 PW** when removed (`test_amnesia.py` wipes module state every turn:
2.67 → 1.90). This is the largest single component of the bot's strength.

From the sequence of boards alone it reconstructs the turn number, all four
scores, every bot's capture and upgrade progress, all four shield cooldowns,
freeze counters, and the token holder. Verified against the engine's private state
over 3,200 turns (`test_tracker.py`): **scores, progress, positions, freezes and
the token are exact.** Cooldowns are 99.9% accurate, and *its own* cooldown is
exact (0 errors in 1,120 turns) — which is what makes the `SHIELD` cross-check in
§5.4 safe.

The hard part is **shield attribution**. A bot that freezes while standing on
rival land was either caught by that landlord shielding, or backfired on its own
shield — and the board does not say which. Rather than guess, the tracker runs a
small **constraint search**: enumerate every subset of seats that *could* have
shielded (cooldown clear, not already frozen, and — a hard constraint — did not
lose a cell this turn, since a shield protects all your cells), predict the freeze
pattern each subset implies, keep only subsets that exactly reproduce what was
observed, rank survivors by plausibility (a landlord defending its own land is
likely; shielding while squatting on enemy land is not), and on ties take the
**intersection**, i.e. believe only what every explanation agrees on.

It also feeds itself its own last action, since it knows with certainty whether
*it* shielded.

### 5.2 The walk planner: routes, not targets

Worth **0.20 PW** — measured by reducing it to a single-target chooser
(`visits: 1` → −0.2037, z = −6.85, score 2567 → 2314). The second-largest effect
in the project.

Instead of ranking individual cells by rate, it runs a **beam search over
*walks*** — sequences of work-cells — paying the real travel cost between them.
This prices travel correctly, naturally prefers clusters, and avoids the pathology
that rate-ranking falls into.

A crucial distinction the measurements separate:

| | worth |
|---|---|
| planning a route over several work-cells (`visits`) | **0.20 PW** |
| the *width* of the beam searching those routes | **−0.02 PW — nothing** |

Which is why the bot survives a machine 100× slower while losing only 2.6% of its
score: the deadline narrows the beam but still runs every visit, discarding the
part that does not matter and keeping the part that does.

**The pathology this fixes, and once suffered from.** An early version scored 1050
instead of 2400 because it stood on its best target and walked away, pacing
between two neighbouring cells forever. The cause: the `perish` and `safe` risk
modifiers were keyed to the *walk's* travel distance, so whichever cell the bot
occupied got penalised relative to its neighbour. The fix was to make every
modifier **cell-intrinsic** — computed once per turn, never dependent on where the
walk currently stands — plus `stickiness` hysteresis. The same bug later appeared
in an opponent I wrote (`ai_route` paced NORTH/SOUTH 66 times in 80 turns and
banked 10 stays), which is why `audit.py` now flags any bot staying on under 25%
of turns or reversing on over 22%.

### 5.3 The shield/raid stand-off as a matrix game

The defensive decision is a genuine 2 × 2 simultaneous game:

| | they commit (stay) | they bail (leave) |
|---|---|---|
| **I shield** | I keep the cell, they freeze 2 turns | **backfire**: I freeze 2 turns and burn 4 turns of cover |
| **I don't** | they take the cell + bonus | nothing happens |

So the decision turns on `P(commit)`, and the **backfire branch must be priced**.
Leaving it out makes shielding look free, the bot shields on sight, and that is
precisely what a baiting opponent farms. The bot computes

```
gain     = Σ over imminent intruders (what I lose + what they gain) × P(commit)
backfire = P(they bail) × freeze_cost × κ
cost     = κ × shield_cost          # the turn itself, plus 4 turns of no cover
net      = gain − backfire − cost
```

shields outright when `net` is decisive, and otherwise **mixes at the equilibrium
frequency** `q = net / (net + backfire + cost)` so a predictable defender cannot be
baited. `P(commit)` is estimated per opponent from observed behaviour — how often
that seat has committed versus bailed when standing on someone's land.

Two honest findings about this machinery:

- **The equilibrium mixing does not bind in practice.** Stopping an imminent
  capture is worth an order of magnitude more than a shield costs, so the
  mixing branch almost never triggers. What actually prevents baiting is the
  per-opponent commit estimate.
- **Shielding resets your own progress**, and pricing that cost explicitly
  measured *worse* (−0.034 PW, z = −3.35) — because the tuned `shield_bias` was
  already absorbing it, so adding the term double-counted. A real cost, correctly
  identified, that still hurt when added naively. It is in the code at zero and
  handed to the tuner to weigh jointly.

### 5.4 The safety net

There is no competition simulator and no trial run: whatever is in the repository
at the deadline is played once, by a server that cannot be inspected beforehand.
So the guards matter as much as the strategy.

| guard | what it protects against |
|---|---|
| **Fallback policy** | `decide()` raising. Returning `STAY` there is the worst available failure — one bad assumption plays the skeleton for 80 turns while every stress test reports "no crashes". It happened once, from a single missing parameter key. The fallback scores **6.8–8.6× the skeleton** |
| **Adaptive throttle + internal deadline** | a slow or loaded grader. 60 ms internal budget against a 200 ms limit; the beam shrinks when a turn runs long. Worst case measured **37 ms with 32 processes fighting over 24 cores** |
| **New-game reset** | the server playing several games in one process. The tracker detects a starting board; the agent now clears its own objective, RNG stream and beam scale on that signal |
| **`SHIELD` cross-check** | a server that offers `SHIELD` during cooldown and scores the attempt as `STAY`. Checks both `legal_actions` *and* its own tracked cooldown |
| **Runtime rule detection** | my reading of ambiguity #2 being wrong |
| **Seat-canonical tie-breaking** | the bot playing a different game in each corner (§8.4) |
| **Full parameter baking** | `ship.py` bakes the complete parameter set, so a key added after the last tuning run cannot go missing |

### 5.5 Forecasting rivals: Bayesian goal inference (v9)

Everything up to v8 sees the whole board but never asks where a rival is
*going*. Its only model of opponents was the tuning field — weights fitted against
bots written in this repository — which is overfitting by construction: it knows
how the bots it trained against behave, not how a stranger will.

`Forecaster` replaces that with **inverse planning**. Each rival is treated as a
goal-directed agent playing by the same rules, and its goal is inferred from its
own moves in the current game. Nothing is fitted to any pool of opponents.

- **Prior — plan from the rival's chair.** For every cell, how good a target it is
  *for that rival, from where it stands*: the points the work earns (value ×
  turns it will pay, plus any raid bonus) per action-turn it costs (travel +
  stays). The same arithmetic as §2.2, applied to someone else.
- **Evidence — a noisy-rational move model.** Each step either brings the rival
  closer to a candidate goal, holds, or takes it further away, with likelihoods
  in the ratio e^β : 1 : e^−β (β = 2).
- **Structure taken from the rules.**
  - Rivals re-plan every turn, so the belief is the *current* prior times recent
    evidence, with evidence fading by ρ = 0.9 per step.
  - A stay is how work is done: a stay that *finishes* work (the tracker's progress
    is back to 0) starts a fresh goal, and a stay mid-work marks the current cell
    as the goal.
- **Forecast.** The posterior gives each rival's likely destination and its
  arrival turn. Chaining "its best next target after that one" twice carries the
  forecast further out.
- **Use.** Any piece of work in the walk planner is multiplied by the probability
  that its cell is still free when the bot arrives: every rival forecast to stand
  on it first takes it with that rival's probability, and arriving on the same
  turn is a contest, counted as even.

The constants — β 2, ρ 0.9, κ 3 (prior temperature), a two-target chain — were set
on principle before any measurement and never tuned. Tuning them on the fields
used to judge the method would reintroduce exactly the overfitting it replaces.

**Three modelling errors**, found with `strategy_audit/forecast_probe.py` on the
training-like field and each documented where it was fixed:

| version | finds the true destination |
|---|---|
| likelihood of the exact move — splits credit among equally good moves, but real bots walk in straight lines | 2.5% |
| goals persisting ten turns — rivals finish a target every few turns | 19% |
| every stay read as "goal = here", even one that just finished the work | 16% |
| **as shipped** | **48%** |

**What it achieves.**

- **Accuracy:** on the held-out field it finds a moving rival's next destination
  48% of the time, against 1% for "it stays put". Its position error 8 turns
  ahead is 2.17 cells, against 2.54 for "stays put" and 2.86 for "keeps going".
  The rule prior alone is nearly as accurate (48.1%), so most of the power is in
  planning from the rival's chair; watching its moves adds calibration (it gives
  the truth 0.088 probability against 0.081).
- **Strength:** paired against v8, **+0.050 PW (z +3.1)** over 1,000 games on the
  field closest to Round 1 — mixed lineups of opponents the bot was never tuned
  against — level against the strongest bots, and **−0.024 PW (z −1.8)** against
  the repository's own strangers. Full tables are in the README's v9 section and
  in `strategy_audit/README.md` §13.

---

## 6. Every parameter, and what it controls

The bot has 51 tunable numbers, plus 11 on/off switches added in v8 and the v9
forecaster's switch with its four fixed constants (both listed last).
Grouped by what they *mean*:

**Planning**

| parameter | meaning |
|---|---|
| `horizon` | turns of walk the planner looks ahead |
| `visits` | work-cells per planned walk — **the mechanism worth 0.20 PW** |
| `beam` | beam width (measured worthless, kept for safety headroom) |
| `ncand` | work-cells considered per turn |
| `reach` | ignore work further away than this |
| `stickiness` | bonus for continuing last turn's objective — stops pacing |
| `tie_home` | how equal-priority cells are ordered: toward my corner, away, or raw index |
| `budget_ms`, `throttle`, `first_turn_ms`, `first_turn_mult` | time safety, not policy |

**Economy**

| parameter | meaning |
|---|---|
| `w_claim`, `w_upgrade`, `w_raid` | relative weight of the three kinds of work |
| `w_raid_late` | raid weight at the final turn, interpolated by the clock — because the bonus does not decay (§2.2) |
| `combo`, `combo_pri` | claim-and-upgrade in one visit, paying travel once |
| `hold` | value of squatting a threatened cell (occupancy is immunity) |
| `consolidate` | tilt from claiming toward upgrading as the clock runs down |
| `upg_risk` | an upgrade doubles the bounty on its own cell |
| `home_bonus` | work on my own, unraidable home |
| `w_denial` | how much a rival's loss counts toward my placement |
| `zone_bonus` | prefer my own quadrant |
| `perish`, `safe_discount` | cells a rival could reach sooner / can never contest |
| `squat_penalty` | a rival is sitting on it and may not leave |
| `contest_penalty` | avoid steps that lose the priority-token race |
| `steal`, `steal_until`, `steal_min` | the centre-steal opening (measured, lost, tuned to 0) |
| `intent`, `intent_turns` | discount cells a rival is visibly walking toward |

**Risk and defence**

| parameter | meaning |
|---|---|
| `kappa`, `def_kappa` | value of one action-turn, offensive and defensive. **Kept separate deliberately**: sharing one let the raid side tune it down until the shield cost collapsed |
| `freeze_cost` | a freeze costs this many action-turns |
| `q_prior`, `q_weight` | prior and strength of the belief that a rival shields a raider off its land |
| `raid_risk` | global scaling of raid interception risk |
| `shield_cost`, `shield_bias`, `shield_certain` | the price of a shield, the margin it must clear, and when to stop mixing |
| `own_prog` | progress a shield throws away |
| `retake_credit` | I own the cell, so I win the contest to retake it |
| `commit_prior` | prior on a raider committing rather than bailing |
| `free_shield_turns` | last turns where a backfire costs nothing |

**Objective shaping**

| parameter | meaning |
|---|---|
| `care_mode` | who to aim at: margin / leader / weakest / nearest / **uniform** |
| `tau` | score-margin scale for the placement sigmoid |
| `proj_care` | compare rivals on current score or on projected final score |
| `endgame_care`, `endgame_denial` | switch to winning still-live pairings near the end |
| `lead_caution` | when ahead treat raids as riskier; when behind, safer |

**v8 switches — fixes from the strategy audit**

Not tuned weights but on/off corrections, each closing one finding in
[`strategy_audit/README.md`](strategy_audit/README.md). Every default in `mybot.PARAMS` reproduces
v7 exactly (checked move for move by `strategy_audit/check_v7_compat.py`);
`v8_params.json` switches them all on.

| parameter | finding | v8 | meaning |
|---|---|---|---|
| `shield_l1` | B2 | 0 | spend a shield to stop a take on a level-1 cell — it only delays the loss (§2.6) |
| `shield_home` | B3 | 0 | count a rival on my home as a capture threat — homes can never be taken |
| `last_shield_value` | B4 | 1 | on the last turn, shield only for a real take worth more than my own last stay |
| `turn_guard` | C2 | 1 | a board after turn 80 is a game whose start was missed: re-estimate the turn |
| `calibrate` | C3 | 1 | measure the shield cooldown and the freeze length instead of assuming 4 and 2 |
| `penalty_undo` | C1 | 1 | a freeze outlasting a shield freeze was a Round 2 time penalty: withdraw the cooldown inferred from it |
| `solver_retry` | C4 | 1 | if my own shield never happened, re-solve instead of dropping every shield seen |
| `risk_frozen` | C4 | 1 | a frozen landlord cannot shield either: raid risk uses max(cooldown, freeze) |
| `backfire_prod` | C4 | 1 | a shield backfires only if every rival on my land leaves |
| `contest_owner` | C4 | 1 | the step tie-break knows a cell's owner always wins a contest for it |
| `canon_home` | C4 | 1 | tie-break frame from my actual home cell, not my seat number |

**v9 switch — forecasting rivals (§5.5)**

| parameter | v9 | meaning |
|---|---|---|
| `forecast` | 1 | infer each rival's goal from its own moves and discount work on cells a rival will reach first; 0 reproduces v8 move for move |
| `fc_beta` | 2.0 | rationality of the move model: closer : held : further = e^β : 1 : e^−β |
| `fc_rho` | 0.9 | how much of the previous step's evidence survives each turn |
| `fc_kappa` | 3.0 | prior temperature: the best target is e^κ ≈ 20× as likely a priori as a worthless one |
| `fc_chain` | 2 | further targets forecast after the current one |

Fixed on principle, not tuned (see §5.5).

---

## 7. Every file in the repository

49 Python files, about 9,600 lines, plus parameter snapshots and documentation.

### 7.1 The submission

| file | what it is |
|---|---|
| **`bot.py`** | **the submission.** One self-contained file, standard library only, `act(state)`. Built by `ship.py`, never edited by hand |
| `mybot.py` | the development source — the real bot. `Tracker`, `Agent`, the walk planner, the shield game, `_fallback`, `act` |
| `ship.py` | builds and verifies the submission: bakes the full parameter set, strips the dev docstring, then checks stdlib-only imports, an untouched `act(state)` signature, identical play to the dev bot, four seats sharing one module, that `decide()` raises no internal exceptions, that the fallback survives, a degenerate-policy flag (>85% `STAY`), and 40 stress games with a timing ceiling |

### 7.2 The rules engine

| file | what it is |
|---|---|
| `engine.py` | the exact rules engine, reimplemented from the rulebook. The foundation — nothing else here is trustworthy without it. Holds `RULES`, the five ambiguity flags; `make_map`; `Cell`/`View` mirroring the starter kit exactly; and `step()`, the four-phase turn resolution |
| `botlib.py` | shared helpers for the opponents (board parsing, BFS, Manhattan distance, zones). The submission does not use it — `bot.py` is self-contained |

### 7.3 The opponents

| file | what it is |
|---|---|
| `zoo.py` | the 9 original archetypes (§4.3 tier 1) |
| `holdout.py` | the 4 held-out archetypes, never used in tuning (tier 2) |
| `aifield.py` | the 7 AI-field designs (tier 3) |
| `probot.py` | the independent rival — a different architecture with its own weights (tier 4) |
| `rivals.py` | frozen parameter snapshots, so the bot can play earlier versions of itself and the counter-bots bred against it |
| `field.py` | **one registry for everything.** Resolves any opponent name, and defines the tiers (`realistic`, `peer`, `designs`, `legacy`). Replaced five drifted near-copies of the same lookup |

### 7.4 Measurement

| file | what it is |
|---|---|
| `measure.py` | **paired A/B measurement.** Every variant plays the identical list of (map, seat, opponents, token) tasks and is compared by per-task difference, which shrinks the standard error 3–5× because map and line-up luck cancels exactly |
| `choose.py` | the shipping decision. Re-measures candidates on three tiers — `realistic`, `peer`, held-out — and encodes which is which: **peer decides, realistic must not regress, held-out catches fitting to the training field** |
| `arena.py` | the Elo tournament harness. `pairwise_wins`, a registry, Elo/PW/score/place/head-to-head statistics, random-matchup tournaments |
| `audit.py` | behavioural audit — catches pathologies a score table hides: pacing, shield-happiness, idle turns, illegal actions, worst-case timing |
| `diag_seat.py` | seat-bias diagnostic. Four copies of one bot on a mirrored map must average exactly 1.50 per seat; anything else is that bot's bug |
| `diag_loss.py` | where the points actually go — cells lost, income forgone, bonuses handed over, and how many losses a legal shield could have stopped |
| `exploit.py` | exploitability matrix: every counter-bot against three copies of every version |

### 7.5 Tuning

| file | what it is |
|---|---|
| `tune.py` | the (1+λ) evolutionary search over the bot's 51 parameters, with common random numbers, periodic task refresh, **a confirmation stage** (§8.2) and held-out validation |
| `tune_rival.py` | the same method applied to `probot.py`, against a field that excludes ProBot — because a bot tuned only against copies of itself learns a weak mutual equilibrium |
| `strategies.py` | the macro-strategy sweep: 18 named *plans* as overlays, across three fields (§4.2) |

### 7.6 The GPU / reinforcement-learning track

Rejected after measurement, kept because the negative result is informative.

| file | what it is |
|---|---|
| `gpuenv.py` | Zone Rush as batched tensor operations — thousands of games stepping at once. **134,000 games/second** |
| `test_gpuenv.py` | proves the tensor engine matches `engine.py` exactly, comparing the full state after every turn under all five rulesets. 9,600 comparisons, exact |
| `rl.py` | self-play PPO with GAE, action masking, a 75-feature egocentric encoding and a small MLP chosen so the same forward pass can run in pure stdlib Python inside the time budget |
| `nnbot.py` | the pure-Python inference twin, matching the torch features to 2.78e-08 |
| `nn_policy.json` | the trained weights |

**The result: 163.8M steps, plateaued around 1670, and scored 0.00 of 3 against
three copies of the heuristic bot.** Inference was never the constraint (1.3 ms).
Two structural reasons: pure self-play converges to a weak mutual equilibrium, and
a reactive policy cannot plan the multi-turn routes this game rewards — which
§5.2 later quantified at 0.20 PW.

### 7.7 Tests

Grouped by how badly a failure would hurt. `runtests.py` runs them all.

**Correctness** — every other number is measured through these:

| file | what it checks |
|---|---|
| `test_engine.py` | the engine against every worked example and invariant in the rulebook: the 48-point raid, shield cancel, backfire, no-swaps, owner-wins-contest, token order, home immunity, plus 400 fuzzed games asserting no two bots share a cell, monotone scores, income/ownership consistency |
| `test_tracker.py` | hidden-state reconstruction against the engine's private state over 3,200 turns |
| `test_gpuenv.py` | the tensor engine against the reference engine, state by state |
| `test_determinism.py` | **the measurement harness itself** — paired games must be reproducible, three ways |

**Survival** — the bot must not crash, stall, time out, or leak state:

| file | what it checks |
|---|---|
| `test_guards.py` | eight sections: runtime rule detection, the fallback policy, state reuse across games, mid-game drop-in, flat vs 8 × 8 boards, a server offering `SHIELD` on cooldown, own-cooldown exactness, stdlib shadowing, and UTF-8 validity |
| `test_timing.py` | graceful degradation on hardware emulated up to 100× slower, and that the throttle actually engages |
| `test_robust.py` | the five ambiguous-rule flips, malformed input, every seat, mirror matches |
| `test_amnesia.py` | what losing module state between turns would cost (**0.77 PW**) |

**Strength:**

| file | what it checks |
|---|---|
| `test_transfer.py` | the tuned bot against opponents it has never been tuned against |
| `test_fields.py` | how much measured strength depends on the assumed field |
| `test_oppmodel.py` | whether the opponent model actually adapts, using a pure baiter |

### 7.8 Parameter snapshots

| file | what it is |
|---|---|
| `v1_params.json` … `v7_params.json` (plus `v2b`, a variant branch of v2) | the tuned versions in order. `v7` was tuned against the rebuilt field with the confirmation stage, and shipped with `tie_home: 1` for seat symmetry |
| `v8_params.json` | v7's weights, unchanged, plus the eleven audit switches of §6 (ten on, `risk_frozen` measured and left off). Not a retune — every v7 weight is identical |
| **`v9_params.json`** | **the shipped set**: v8 plus `forecast: 1` and the forecaster's fixed constants (§5.5) |
| `v4_seed.json`, `v5_seed.json`, `v6_seed.json` | the seeds those runs started from |
| `nemesis1.json`, `nemesis2.json`, `nemesis3.json` | counter-bots bred to beat a named version of this bot |
| `pro_params_v1.json` | the frozen independent rival. **Committed**, because `field.py` depends on it; without it the field silently falls back to the untuned version |
| `snapshots.json` | the registry `rivals.py` reads |
| `turn_fit.json` | the fitted mid-game turn estimator |

A run in progress writes to `best_params.json`, which is **gitignored** along
with `pro_params.json`, so a half-tuned file cannot be mistaken for a decision.
Harvested results are copied to an explicit `vN_params.json` and committed.

### 7.8b The strategy audit (`strategy_audit/`)

An adversarial review of the shipped bot against the rulebook, and a test against
opponents and referees written outside this repository. Its findings are what v8
fixes. Full write-up: [`strategy_audit/README.md`](strategy_audit/README.md).

| file | what it is |
|---|---|
| `strategy_audit/README.md` | every finding with its rule, code location, mechanism and paired evidence, and what v8 did about it |
| `strategy_audit/edge_audit.py` | paired, instrumented harness. `AUDIT_BOT` picks the bot (`bot`, `mybot`, or a file such as an old version pulled from git); variants are fix switches, `KEY:VALUE` overrides or `@file.json` |
| `strategy_audit/outsiders.py` | eight opponent designs written from the rulebook alone, sharing no code with the field here |
| `strategy_audit/referee.py` | plays identical games under alternative readings of the cooldown and freeze durations |
| `strategy_audit/penalty.py` | injects Round 2 time-penalty freezes and measures tracker error |
| `strategy_audit/lastturn.py`, `strategy_audit/scenarios.py` | turn-80 raids; constructed edge cases run against the bot's internals |
| `strategy_audit/check_v7_compat.py` | proves every v8 switch at its default plays move-for-move like the v7 `bot.py` in git history |
| `strategy_audit/forecast_probe.py` | scores the v9 forecaster against what rivals actually did — next destination, position 1–8 turns ahead, arrival time — against no-inference, stay-put and momentum baselines |
| `strategy_audit/results/` | every table the write-up quotes |

### 7.9 Scratch files — not load-bearing

These are one-off debugging and diagnostic scripts from earlier in the project.
Nothing depends on them; they are kept because each one answered a question at the
time and re-deriving them would be wasted work. Listed for completeness.

| file | what it did |
|---|---|
| `agent_new.py` | a working copy of the agent during a large refactor. Superseded by `mybot.py` |
| `bench.py` | a quick focused tournament against the zoo |
| `calib.py` | fitted the mid-game turn estimator now stored in `turn_fit.json` |
| `dbg.py`, `dbg2.py`, `dbg3.py` | tracker and planner traces — printed the bot's internal state turn by turn while hunting the pacing bug and the tracker mismatches |
| `diag.py`, `diag2.py`, `diag3.py` | score decomposition: where points came from (income vs bonus), action mix by game phase |
| `probe.py` | a hand-driven parameter probe, predating `tune.py` |
| `patch_combo.py` | the one-off patch that added the claim-and-upgrade-in-one-visit path |
| `evaluate.py`, `final_eval.py` | earlier full-tournament and version-selection scripts, superseded by `choose.py` |

---

## 8. How anything here gets measured

Four methodological lessons, each of which cost something to learn. They matter
more than any individual parameter, because they determine whether a reported
improvement is real.

### 8.1 Paired comparison, and two kinds of clock dependence

Unpaired tournament means cannot see a change worth 0.02 PW: per-game standard
deviation is about 1.0, so 400 unpaired games give a standard error near 0.05 and
most real improvements vanish into it. `measure.py` therefore runs every variant
over the **identical** task list and compares per-task differences. Two copies of
the same parameters report a difference of exactly **0.0000 ± 0.0000** — the
harness validating itself.

That only works if replaying a game is reproducible, and the bot had **two**
wall-clock dependencies:

1. the adaptive beam (`throttle`), which scales the search by how long the last
   turn took; and
2. the hard deadline *inside* the beam search (`budget_ms`), which truncates it
   when a turn runs long — **and this one bites even with `throttle` off**.

With only the first pinned, two identical parameter sets measured **0.0625 PW
apart** under load — larger than any real improvement in this project. Evaluation
now neutralises both, and `test_determinism.py` asserts the property directly.
Both guards stay in `bot.py`: they are insurance against a slow grader, not part
of the policy, so they belong in the submission and out of the fitness function.

### 8.2 The tuner was selecting luck

The search takes the best of λ candidates on one draw of games. That is a
**maximum over noisy estimates**, so the winner's measured score is biased upward
even when it is no better than the incumbent. At a few hundred games the paired
standard error is around 0.03 PW, and the best of thirteen draws sits roughly 1.5
of those above the truth. Accepted candidates compound the bias.

The tell was in the logs all along — the task set refreshes every six generations
with the incumbent re-scored, and it dropped by about that much every time:

| | own task set | fresh games |
|---|---|---|
| gens 5–6 | 2.6364 | 2.5568 |
| gens 11–12 | 2.5758 | 2.4583 |

Then the direct test: thirteen generations of tuning, measured paired against the
seed on games neither had seen — **−0.0219 ± 0.0242. Nothing.** Several hours
spent accepting luck.

Both tuners now have a **confirmation stage**: a candidate must win its own draw
*and then* beat the incumbent again on a fresh draw it was not selected on. After
the fix, the refresh drop fell from ~0.09 to **0.009**, and the search started
producing real gains.

### 8.3 The field you measure on can be saturated

This one produced a wrong conclusion that survived for a while, so it is worth
stating plainly.

Seeing no transferable gain, I concluded the bot must sit at a local optimum with
little headroom left. **That was the measuring instrument, not the bot.**

The `realistic` tier is a fair model of the Round 1 field, weak entries included —
and that is exactly what makes it useless for separating two strong bots. The
reference already scores **2.556 of a maximum 3.000** there, winning about 85% of
its pairings, so a genuine improvement has almost nowhere to register.

The same candidate, measured on both tiers:

| tier | reference | candidate | dPW | z |
|---|---|---|---|---|
| realistic (saturated) | 2.556 | 2.549 | −0.007 ± 0.025 | −0.27 |
| **peer** | **1.713** | **1.966** | **+0.2535 ± 0.0377** | **+6.73** |

A ceiling can only bias a result **toward zero**, which means the negative results
in §9.2 are biased toward "no effect" too. Re-running four of them on the
discriminating tier, two flipped:

| idea | on realistic | on peer | verdict |
|---|---|---|---|
| `combo: 0.9` | −0.021 | **+0.0633 ± 0.0341** | **false negative** |
| `upg_risk: 0.6` | +0.002 (z 0.58) | **+0.0083 ± 0.0034** (z **+2.47**) | **false negative** |
| `stickiness: 1.2` | +0.010 | +0.0167 ± 0.0088 | borderline positive |
| `home_bonus: 1.4` | −0.013 | **−0.0533 ± 0.0190** (z **−2.80**) | genuinely harmful |

`choose.py` now encodes the lesson, and prints a warning when the reference sits
above 2.4 on realistic.

### 8.3b ...and it can be biased toward your own architecture

The fix for saturation introduced a subtler problem, and finding it required
being suspicious of a result that flattered the work.

The `peer` tier discriminates because every game in it is close. But **six of its
eleven entrants are my own parameter snapshots** (v3, v4, v6, nemesis1–3). So
"good on peer" partly means "good against my own lineage", which is nothing like
the Round 1 field. The tell was an older version, v3, scoring *best of all* on
peer while regressing significantly on held-out opponents.

So a fourth tier was added — **`strangers`**: 14 opponents, strong and varied,
and **not one of them a version of this bot**. The newly tuned candidate measured
across all four:

| tier | gain over v6 | contains my own versions? |
|---|---|---|
| peer | **+0.251** (z +6.05) | **yes — 6 of 11** |
| realistic | +0.012 | 4 of 23 |
| **strangers** | **+0.024** (z +1.23) | **no** |
| heldout | −0.024 | no |

**The large gain exists only on the tier dominated by my own lineage.** On every
field of non-self opponents it is +0.02 and not statistically significant. The
candidate had been tuned against a field where my own snapshots carry 8.2 of
about 35 total weight, so peer was measuring exactly what the tuner had optimised.

The gain is real — just far narrower than the headline number suggested. The
candidate still ships, because it is weakly better or level on every field and
never significantly worse, with consistently higher raw scores. But it ships as a
**marginal** improvement, and the general lesson is sharper than the specific
one: *a discriminating measurement is not automatically an unbiased one, and a
field containing your own past work measures family resemblance as much as
strength.*

### 8.4 Symmetry as a correctness test

Because the map is four-fold mirrored, **four copies of one bot must average
exactly 1.50 PW in every seat.** Any deviation is that bot's own bug, and unlike
most properties this one has a known right answer in advance.

It found a real one. Candidate cells are ranked by
`v × (R − d − need) / (d + need)` over small integers, so exact ties are common —
and they were broken by **raw cell index**. That is not the same rule in all four
corners: high indices are the bottom-right, so seats 3 and 4 broke ties *toward*
their own home and seats 1 and 2 broke them *away*.

| tie-break | PW by seat 1–4 | spread |
|---|---|---|
| raw cell index (as shipped) | 1.72 / 1.72 / **1.29 / 1.27** | **0.45** |
| **toward my own corner** | **1.50 / 1.50 / 1.50 / 1.50** | **0.00** |
| away from my own corner | 1.49 / 1.35 / 1.52 / 1.64 | 0.29 |

`CANON[seat]` now re-expresses every cell index in the seat's own frame, and the
same ordering is applied to equally good steps in `_step` — whose fixed
north/south/west/east iteration order was a second, smaller asymmetry.

**In Elo terms it is worth nothing** (+0.002 ± 0.018 on realistic, +0.011 ± 0.027
on peer), which is right on reflection: 1.72 and 1.27 average to 1.495, so once
seats are mixed the two biased behaviours come to the same thing as the symmetric
one. It ships anyway, because the bot then plays one well-understood policy in
every corner instead of two different ones — and because the test can now detect a
genuine corner-dependent bug instead of flagging one that costs nothing.

One warning this episode also taught: a mixed-field seat test is **not** a
substitute. It reported this bot at 2.1 / 2.4 / 1.3 / 1.2 across seats, which was
`SpineFarmerBot`'s own seat bias leaking in — replacing a strong seat is a
different experiment from replacing a weak one.

---

## 9. Results, and everything that failed

### 9.1 Where the strength comes from

Measured, not assumed:

| mechanism | how it was measured | worth |
|---|---|---|
| hidden-state reconstruction | wipe module state every turn | **0.77 PW** |
| multi-visit route planning | `visits: 1` vs `visits: 7` | **0.20 PW** |
| beam width | `visits: 10` vs `visits: 7` | −0.02 PW (nothing) |
| everything hand-designed afterwards | ten paired A/Bs | 0.00 or negative |

### 9.2 Tested and found not to work

All of these were plausible, several were confidently predicted before any code
ran, and the ones marked † were measured on the saturated tier and so may be
false negatives (§8.3).

| idea | result |
|---|---|
| **PPO self-play** | 163.8M steps → 0.00 of 3 against the heuristic bot |
| **Hunting the leader / denial** | four-player general-sum punishes it; tuned to zero |
| **The centre-steal opening** | six turns of zero income is not recoverable |
| **All-out endgame raiding** | the bot already shifts late on its own; forcing it is worse (2.86 → 2.61) |
| **Occupancy as deliberate defence** † | no measurable benefit — the planner is already parked on cells while upgrading them |
| **Perishability bonus, retake credit** | both tuned to zero |
| **Equilibrium shield mixing** | correct and present, but does not bind; the commit estimate is what prevents baiting |
| **Projected final scores in the objective** | **structurally inert** — `care_mode: 4` means the objective never reads rival scores |
| **Home-upgrade bonus** | −0.053 PW on peer. Confirmed harmful |
| **Pricing the progress a shield discards** | −0.034 PW. Real cost, but `shield_bias` was already absorbing it |
| **Rival intent modelling** | −0.027 PW, consistent with `perish` having tuned to zero |
| **2 s of extra search on turn 1** | −0.005 PW. The opening is easy; depth buys nothing on an empty board |
| **Harder commitment** (`stickiness` 1.5–2.2) | −0.004 to −0.010. The region is **flat** — "at the bound" did not mean "wants more" |
| **Timing arrivals to the priority token** | killed before building: blocked moves and lost contests cost **0–0.9% of moves**, about 0.2 turns per game |
| **Counting flipped pairings instead of points** | **inert by construction** — a walk is scored by one scalar, and any monotone transform of a scalar leaves the best walk unchanged. What the idea reduces to is "prefer a certain gain when it already suffices", which is the existing `lead_caution` |

### 9.3 Defence has a ceiling

The bot shields on about 1% of turns, which looks like a blind spot. `diag_loss.py`
settles it by counting what actually gets taken:

| opponent | my score | cells lost | income forgone | bonuses handed over | losses a shield could have stopped |
|---|---|---|---|---|---|
| `raider` | 2181 | 3.5 | 370 | 99 | 1.2 |
| `cdraider` | 2403 | 4.6 | 275 | 104 | 1.4 |
| `ai_hawk` | 2436 | 1.0 | 24 | 20 | 0.8 |
| `spine` | 2633 | 0.6 | 6 | 6 | 0.6 |

Most losses happen while the shield is already on cooldown or while the bot is
frozen, so the total headroom for better defence is **about one cell a game**.
Near-zero shielding is a correct read, not an oversight — upgraded cells take
three stays to steal, so a compact upgraded cluster largely defends itself.

### 9.4 The cautionary result

**v5 overfitted to beating itself.** Its training field contained four of its own
ancestors plus two counter-bots. It scored best of any version on that field and
worst of the lineage against outside opponents (2.55 against v3's 2.74). Self-play
fields need outsiders to stay honest, and version selection has to run on an
external tournament rather than on each run's own training score. That is why
`choose.py` exists, and why `holdout.py` is never in any tuning field.

### 9.5 Mistakes found and fixed

Eight, worst first. Two could have cost the competition outright.

| bug | consequence |
|---|---|
| **A file named `select.py` shadowed the stdlib module** that `multiprocessing` imports, so its module-level code parsed the tuner's command line and exited. A three-hour run never started, and the symptom was an unrelated argument error |
| **The exception path returned `STAY`** — one bad assumption would have played the skeleton for 80 turns while every stress test reported success |
| **The Agent kept state across games** although the Tracker reset, so a server playing several games in one process would have had game 2 played by a bot still carrying game 1 |
| **Equal-priority ties broken by raw cell index** — a different policy in each corner (§8.4) |
| **The tuner's fitness function was non-deterministic**, so identical parameters scored differently by machine load |
| **The progress detector carried the wrong amount** after taking an upgraded cell (3, not 1 — enough to re-upgrade on the next stay) |
| **`README.md` stopped being valid UTF-8** — Python's `open()` writes in the platform encoding on Windows. Mojibake in a public repo; a syntax error if it happened to `bot.py` |
| **A state-leak test failed on timing rather than on state** — it pinned `throttle` but not `budget_ms` |

Plus one in an opponent: `ai_route` paced NORTH/SOUTH 66 times in 80 turns and
banked 10 stays, the same class of bug that once halved this bot's score.
`audit.py` now flags it.

**Found later by the strategy audit, and fixed in v8** (full write-up in
[`strategy_audit/README.md`](strategy_audit/README.md)):

| bug | consequence | v8 |
|---|---|---|
| **A missed turn-1 call left the turn counter running past 80** | if module state survived into a new game, the whole game was played as its last turn: 156 points against rivals' ~2,700 | `turn_guard` re-estimates the turn; 2,584 in the same scenario |
| **Level-1 cells were defended with shields** | 2 frozen turns + 1 stay ≤ a 4-turn cooldown, so 79–89% fell to the same raider anyway (§2.6) | `shield_l1: 0` |
| **A rival on the bot's home was priced as a capture threat** | homes can never be taken; with a 2-point home the shield fired on every turn | `shield_home: 0` |
| **Round 2 time penalties read as shields** | the tracker believed a ready rival could not shield: unsafe on 2.5–7.0% of rival-turns | `penalty_undo` cuts it by 20–27% |
| **Cooldown and freeze lengths assumed, never measured** | the bot's edge depends on them: a server counting either one turn differently costs v7 0.16–0.22 PW | `calibrate` measures both; v8 beats v7 under every reading |
| **The turn-80 shield ignored the bot's own last stay** | gave up a completed raid to stop one that could not happen | `last_shield_value` |

And one in the first v8 draft, caught before shipping by testing against an
alternative referee: the penalty fix could not tell a 3-turn *shield* freeze from
a 3-turn *penalty* before it had seen one, so it withdrew real cooldowns
(**−0.070 PW**). It now waits until the freeze length has been observed, and the
shipped v8 is **+0.030 PW** against v7 under that referee.

---

## 10. What is still open

Stated honestly, because a document like this is most useful where it admits its
limits.

- **The field is still the weakest assumption.** It is much better than it was —
  it now contains a differently-architected bot that beats this one — but *every*
  opponent here was still written in this repository. No actual competitor's code
  has ever been played against. Non-transitivity (§3.3) means this matters more
  than it would in a two-player game.
- **Exploitability is a live risk, and the repository is public.** v6 measures 2.17
  of 3 against a counter-bot bred specifically to beat it (1.50 = no edge). The
  original justification — that nobody else had the source — no longer holds.
  `tune.py counter:<version>` is how anyone would do it, including against this
  bot.
- **Some negative results in §9.2 are still unretested** on the discriminating
  tier. Four were re-run and two flipped; the rest are marked †.
- **Round 2 is a different game.** It is played on physical robots, where
  mis-calibration costs a 3-turn freeze and a stationary robot cannot miss its
  cell. That argues for a path-length penalty and a bias toward staying put —
  neither of which is in the bot, because neither helps in Round 1. v8 makes the
  tracker tolerate those freezes better (`penalty_undo`), but the first two turns
  of a penalty still look exactly like a shield freeze.
- **The tuned gain is marginal on unfamiliar opponents.** v7 was weakly better or
  level on every field and never significantly worse — but the headline +0.251
  was measured on a field containing six of my own snapshots, and against
  strangers it is +0.024 and not significant (§8.3b). The search converged:
  twenty further generations added +0.007. v8 keeps those weights and only adds
  corrections; it is a robustness release, not a strength jump.
- **The weights encode one reading of two rule durations.** Under a referee that
  counts the shield cooldown or the freeze one turn differently from `engine.py`,
  the bot drops 0.15–0.24 PW from its own standard-rules result. v8 measures both
  durations at runtime and beats v7 under every reading, but calibration fixes the
  tracker, not the weights. The real fix is to confirm the counting with the
  organisers and, if it differs, retune on an engine that matches.
- **The raid-shield prior is a bet on the field** (`q_prior`, `q_weight`).
  Learning faster gains 48 points against never-shield opponents and loses 0.111
  PW against strong ones; v8 keeps v7's setting. If the real field turns out
  mostly naive, this is the first thing to revisit.
- **Forecasting helps where the opponents are unfamiliar and costs a little where
  they are not.** v9's goal inference is +0.050 PW (z +3.1) on mixed lineups of
  opponents never tuned against, but −0.024 PW (z −1.8) against the repository's
  strangers, and its points gain did not replicate on fresh games. The forecast is
  only used to avoid cells a rival will reach first; using it for defence — reaching
  a level-1 cell before a forecast raider does — is untested. If Round 1 turns out to
  look like the strangers rather than the outside designs, v8 is the safer build.
- **The income horizon is one turn short** (`rem = R - used - need`; a cell
  taken this turn also scores this turn). The tuned weights absorb it, so fixing
  it alone measures nothing; it belongs in the next retune.
