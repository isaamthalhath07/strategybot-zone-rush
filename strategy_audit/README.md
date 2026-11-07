# Strategy audit — `bot.py` (v7) against the rulebook

An adversarial audit of the submission: every place where the shipped strategy
disagrees with the official rules, every edge case where it is suboptimal, and a
test against opponents — and referees — that were **not** written in this
repository.

> **Status: the fixes have shipped as v8.** Sections 1–11 are the audit of
> **v7** (`bot.py` at commit `961e729`) as it was carried out; code locations
> such as `bot.py:1103` refer to that file, and every number in them reproduces
> against it ([§9](#9-reproducing)). What v8 changed, what it measured, and what
> was deliberately left alone is in [§12](#12-what-v8-changed).
>
> This directory was called `audit/` until it was renamed: that name clashed with
> the project's existing `audit.py` script, which `runtests.py` runs.

During the audit itself nothing in `bot.py` or `mybot.py` was changed: every
candidate fix existed only as a switch in [`edge_audit.py`](edge_audit.py), so it
could be measured without touching the submission. Each claim is backed by at
least one of: a rule citation plus a code citation, a constructed scenario you can
re-run, or a paired measurement you can re-run. Commands are in
[§9 Reproducing](#9-reproducing).

Rulebook sections are cited as **§x.y** (official StrategyBot rulebook, 9 pages).
"Starter kit" is the organisers' repository `github.com/RedPokerJoker123/StrategyBot`
(its `README.md` and skeleton `bot.py`).

---

## Contents

1. [Bottom line](#1-bottom-line)
2. [Method](#2-method)
3. [Submission risks](#3-submission-risks-a)
4. [Strategy findings](#4-strategy-findings-b)
5. [Tracker and robustness findings](#5-tracker-and-robustness-findings-c)
6. [Round 2 findings](#6-round-2-findings-d)
7. [Testing against models that are not in this repository](#7-testing-against-models-that-are-not-in-this-repository)
8. [Checked and found sound](#8-checked-and-found-sound)
9. [Reproducing](#9-reproducing)
10. [Recommended actions](#10-recommended-actions)
11. [Limitations](#11-limitations)
12. [What v8 changed](#12-what-v8-changed)
13. [v9: forecasting rivals](#13-v9-forecasting-rivals)

---

## 1. Bottom line

The bot reads the state exactly as the starter kit defines it and implements
the rules as `engine.py` reads them. No strategy flaw found here loses many
games. The largest exposure is not a bug: the bot's edge is tuned to one
reading of two rule durations that the server could count differently (C3). The
exposures that matter, in order:

| id | finding | severity | strongest evidence |
|---|---|---|---|
| A1 | private repo must be **shared with the organisers**, and the bot uploaded to the **StrategyBot Arena** | can zero Round 1 | §3.1; starter-kit rule 7 |
| A2 | the original repository may still be **public** (copying → code-sharing DQ; counter-bots) | high | `EXPLAINED.md` §10 says "the repository is public"; this repo is a fork |
| B1 | the raid prior is a **bet on the field**: it assumes nearly every landlord shields | medium–high | vs never-shield opponents **+119 ± 18 pts (z +6.8)** from a lower prior; on an untuned mixed field the hedge is **+17 ± 7 pts (z +2.6)** |
| C3 | the bot's edge is tuned to one reading of the **cooldown (4)** and **freeze (2)** durations | medium | a one-turn different reading costs **0.16–0.22 PW (z −4.4 to −5.4)** |
| C1 | Round 2 penalty freezes make the tracker believe a ready rival **cannot** shield | medium (Round 2) | unsafe belief 0.01% → **2.5% / 7.0%** of rival-turns |
| B2 | shielding a **level-1** cell only delays its loss | low–medium | **88.5%** (184/208) lost to the same raider within 6 turns; skipping them **+5.7 ± 1.7 pts (z +3.3)** |
| C2 | stale state + a missed turn-1 call pins `R = 1` for a whole game | low probability, catastrophic | simulated game: **156 pts vs rivals' ~2,700** |
| B3 | a rival standing on **my home** is priced as a capture threat | latent | fires every turn with a 2-pt home; seen once in 80 games vs `x_flaky` |
| B4 | turn-80 shield ignores what the bot's own last stay was worth | tiny | fix **+0.66 ± 0.18 pts (z +3.6)** |
| B5 | turn-80 raids priced as if the landlord might not shield | field-dependent | 22% blocked (26/120), ~1.4 pts/game |
| B6 | income horizon is **one turn short** everywhere | real, absorbed by tuning | turn 80 on a neutral 3-pt cell: plays `NORTH`; fix measures +0.4 ± 2.3 (n.s.) |
| C4, D | minor tracker leaks; Round 2 movement and ranking | low | see sections |

Against **eight opponent designs written outside this repository** the bot
scores **2.625 / 3** pairwise; on a field mixing them with the repository's own
strangers — nothing it was ever tuned against — **2.66 / 3**. The only design
it loses to is still the repository's own counter-bot `pro_tuned` (0.484).
Among the new designs, opportunistic level-1 raiders hurt most, which is finding
B2 seen from the opponent's side. Details in [§7](#7-testing-against-models-that-are-not-in-this-repository).

---

## 2. Method

**What is measured.** `bot.py` itself — the file that will be submitted — not
`mybot.py`. [`edge_audit.Inst`](edge_audit.py) subclasses `bot.Agent`, adds
logging, and puts each candidate fix behind a switch:

| switch | what it changes |
|---|---|
| `nol1` | do not count an imminent raider on a **level-1** cell as a reason to shield (R > 1) |
| `home` | ignore rivals standing on my home cell when deciding to shield |
| `free` | on turn 80, shield only for an imminent non-home threat worth more than my own last stay |
| `offby1` | count income from the turn a take completes (`rem + 1`) |
| `KEY:VALUE` | any `PARAMS` override, e.g. `q_weight:1.5` |

**Paired measurement.** Every variant plays the identical list of
(map, seat, three opponents, starting token) tasks, generated by
`measure.make_tasks` with a fixed seed. Both wall-clock guards are pinned
(`throttle: 0`, `budget_ms: 10000`), exactly as `measure.py` does, so play is
deterministic and two runs of the same variant are identical. Results are
reported as the mean per-game difference from `base` with its paired standard
error and z score. |z| ≥ 2 is treated as significant; anything inside is noise.

- **PW** = pairwise wins out of 3 (the Round 1 Elo unit, §3.2).
- **pts** = final score.

**Fields.**

| tier | contents |
|---|---|
| `strangers` | the repository's 14 opponents that are not versions of this bot |
| `realistic` | the repository's 23-entry mix, weak entries and own snapshots included |
| `nonshield` | three copies of `greedy`, the repository's only never-shield bot |
| `outsiders` | the eight new designs in [`outsiders.py`](outsiders.py) |
| `unknown` | `outsiders` + `strangers`: nothing the bot was tuned against |
| `solo:NAME` | three copies of one opponent |

**Probes** that need no statistics are in [`scenarios.py`](scenarios.py);
targeted measurements in [`penalty.py`](penalty.py), [`lastturn.py`](lastturn.py)
and [`referee.py`](referee.py). Raw outputs are in [`results/`](results/).

---

## 3. Submission risks (A)

These are not strategy, but each can cost more than every strategy finding
combined.

### A1. The repository is private — it must be shared, and the bot uploaded

- §3.1: "put your bot in your team's own GitHub repository as `bot.py`
  (**public, or shared with the organisers**)".
- §3.1: "a bot that doesn't run plays `STAY` every turn".
- Starter-kit rule 7 adds a second, separate step: "**Upload your bot to the
  StrategyBot Arena** as instructed by the organisers." Nothing in this
  repository mentions the Arena.
- Deadline: **Wednesday 11 November 2026, 23:59 UAE time**. "We play the code
  that is in your repository at the deadline."
- Checked: `bot.py` on `main` is byte-identical to the audited version.

### A2. The original repository may still be public

`EXPLAINED.md` §10 states "the repository is public". This repository is a
fork. If its upstream is still public:

- any team can submit the same code, and §3.4 / §6 list **sharing code between
  teams** as grounds for disqualification from StrategyBot — a dispute you would
  have to win;
- any team can breed a counter. This project already did: `pro_tuned` holds v7
  to **1.20 / 3** head-to-head (README §8.3b), and it is the one opponent the bot
  loses to on the untuned field in §7 (0.484).

A second private fork is visible to this account
(`ishaan12121/strategybot-zone-rush-mine`). That is fine if it belongs to the
same team; two teams entering this code is not.

### A3. The bot has never played on the real server

The interface was checked line by line against the starter kit and matches
(§8). But every test here runs on `engine.py`, which the same project wrote. One
game on the Arena — checking the bot moves where it intends — is the cheapest
insurance available. The bot never verifies at runtime that `NORTH` moved it to
row − 1, so a convention mismatch would fail silently.

---

## 4. Strategy findings (B)

### B1. The raid prior is a bet on the field

**Code.** `bot.py:102-104` — `q_prior = 0.626`, `q_weight = 4.91`,
`raid_risk = 1.59`; used in `_shield_risk` (`bot.py:1050-1063`) and
`_work_gain` (`bot.py:839-840`).

**Mechanism.** Against a landlord with no shield history and no cooldown, the
modelled chance it shields a one-stay raid is 0.626. Multiplied by `raid_risk`,
that is ≈ 0.996, so the raid's gain is scaled by ≈ 0.004 and the freeze penalty
is charged almost in full: **every raid on an unobserved, ready landlord is
valued at about −2κ.** The bot only raids landlords that are provably on
cooldown or frozen, or that it has watched decline to shield several times.

**Why this is a bet.** In `field.py`, every opponent the bot was tuned against
shields, except `greedy` — which `zoo.py` calls "my prediction for the modal
unprompted-LLM bot". The prior was tuned on a field of shielders.

**Measured** (paired, `results/v7_edge_nonshield_300_*`, `results/v7_edge_strangers_400_*`,
`results/v7_edge_unknown_400_*`, `results/v7_edge_outsiders_400_*`):

| change | vs 3× never-shield | strangers | outsiders | unknown (untuned mix) |
|---|---|---|---|---|
| `q_prior` 0.35 | **+119 ± 18 pts (z +6.8)**, +0.047 PW (z +2.0) | **−23 ± 10 pts (z −2.4)** | — | — |
| `q_weight` 1.5 (learns faster in-game) | **+52 ± 13 pts (z +4.1)**, +0.040 PW (z +2.1) | −6 ± 3 pts (z −1.9) | +3 ± 9 pts (n.s.) | **+17 ± 7 pts (z +2.6)**, +0.023 PW (z +1.4) |
| `q_weight` 1.5 + `q_prior` 0.5 | +42 ± 16 pts (z +2.7) | −6 ± 5 pts (n.s.) | — | — |

The same caution shows against the new designs: against three copies of
`x_flaky` (30% of which crash and never shield again) the bot makes
**0.03 raids per game before turn 40**; against `x_fort`, whose fresh level-1
claims are undefended until upgraded, **0.04 raids per game** in total.

**Reading.** A fixed prior must lose on one of these fields. Faster learning
(`q_weight` 1.5) is the better hedge: it gives up about 6 points on the
shield-heavy field it was tuned on and gains 17–52 elsewhere. On points, it
breaks even if roughly more than 11% of real opponents never shield (from the
score columns, assuming effects mix linearly per opponent). It has **not** been
retuned jointly with the other parameters.

### B2. Shielding a level-1 cell only delays its loss

**Rules.** A caught raider is frozen for 2 turns (§2.6); a level-1 cell falls to
**one** stay (§2.4); the shielder cannot shield again for **4** turns (§2.6).

**Arithmetic.**

| defended cell | raider needs after the freeze | turns until it completes | your shield back after | outcome |
|---|---|---|---|---|
| level 1 | 1 stay | 2 + 1 = **3** | 4 turns | **lost on turn 3** |
| upgraded | 3 stays | 2 + 3 = **5** | 4 turns | re-shield in time — **held indefinitely** |

So a committed raider always takes a level-1 cell three turns later, and the
shield bought three turns of income plus two turns of the raider's time — at the
cost of the bot's own turn and four turns without cover elsewhere.

**Code.** `bot.py:1103` values the shield as saving the cell for the rest of the
game: `lost = v * lvl * (R - 1) * (1 - retake_credit)`. At R = 40 that is **57
points** for a 3-point level-1 cell; against a committed raider the real saving
is **9** (`results/v7_scenarios.txt`, S1c).

**Measured.**

| field | L1 cells lost to the same raider within 6 turns of the shield | skip L1 shields (`nol1`) |
|---|---|---|
| strangers (600) | **184 / 208 = 88.5%** | **+5.7 ± 1.7 pts (z +3.3)**, PW n.s. |
| realistic (500) | — | +3.6 ± 1.8 pts (z +1.95), PW n.s. |
| outsiders (400) | 79% | +2.0 ± 1.6 pts (n.s.) |
| 3× `x_leech` (240) | 82% | **+9.6 ± 3.8 pts (z +2.5)** |
| 3× `x_jackal` (80) | 85% | — |

Consistent direction everywhere, worth points but not yet measurably worth
placements. Upgraded-cell shields are the opposite case and are correct, and
they are most of what the bot does: of its 2,913 shields on the strangers field,
118 were on turn 80 and 208 involved a level-1 cell, leaving roughly 2,600 that
defended upgraded cells.

**Implication beyond the shield rule.** A level-1 cell cannot be defended against
a committed raider at all; an upgraded one can be held forever by a well-timed
shield. Upgrading therefore buys **defensibility**, not only double income. The
bot's objective prices only the income (and has an `upg_risk` term, tuned to 0,
that would penalise upgrading exposed cells — the opposite direction). Valuing
defensibility is untested here and worth a measurement.

### B3. A rival on my home is priced as a capture threat

**Rules.** "A rival's home: Nothing — homes can never be taken" (§2.4). A rival
staying on your home *is* caught by your shield (§2.6), so a shield there is not
wasted — but it can only freeze them, never save the cell.

**Code.** `_should_shield` collects intruders with `owner[p] == seat`
(`bot.py:1068-1072`), which includes the home, then values preventing its
"loss" (`bot.py:1103-1104`). The turn-80 path does the same (`bot.py:1078-1083`).

**Scenario** (`results/v7_scenarios.txt`, S1):

- 1-point home: the shield fires only on turn 80.
- **2-point home** and a rival with a committed raiding history: the shield
  fires on **every turn from 1 to 80**.

**In play:** never triggered in 600 strangers games. It did **not** trigger
against three copies of `x_homebait`, a design that baits from homes
(`home` fix changed 1 of 240 games, n.s.). It did fire about once in 80 games
against `x_flaky`. Latent, not exploited.

**Fix:** one line — skip cells where `tr.home_of[p]` is set.

### B4. The turn-80 shield ignores the bot's own last stay

**Code.** `bot.py:1078-1083`: with `free_shield_turns = 1`, on turn 80 the bot
shields if **any** non-frozen rival stands on its land. That includes rivals who
cannot complete anything this turn (12 of 118 last-turn shields on the strangers
field) and rivals on its home. It never compares against its own last-turn
action, which can be a raid completion worth `8·v·lvl + v`.

**Measured:** `free` fix **+0.66 ± 0.18 pts (z +3.6)** strangers, **+0.45 ± 0.17
(z +2.6)** outsiders. Tiny, because on turn 80 rivals shield too: in a traced
game all four bots shielded on the last turn, so the bot's own last raid would
have been blocked anyway.

### B5. Turn-80 raids are priced as if the landlord might not shield

On turn 80 a shield has no cooldown cost and no backfire cost, so a rational
landlord with a free shield always uses it. The bot prices a raid completing on
turn 80 with its ordinary mid-game estimate. **Measured** (`results/v7_lastturn_strangers_base.txt`):
120 last-turn raid attempts in 400 games, **26 blocked (22%)**, 579 points lost
(~1.4 per game). This field mostly does not shield on turn 80; a field of
rational bots would block nearly all of them.

### B6. The income horizon is one turn short

**Rules.** Turn order is moves → takes → **scoring** (§2.2): a cell taken this
turn scores this turn.

**Code.** `bot.py:788`: `rem = R - used - need`, where `R` counts turns left
including this one. The true number of paying turns is `rem + 1`.

**Scenario** (`results/v7_scenarios.txt`, S8): on turn 80, standing on a neutral
3-point cell, the bot plays **`NORTH`** — staying would have scored 3. At R = 2
a claim in place is valued at 3.4 against a true 6.

**Measured:** `offby1` fix +0.4 ± 2.3 pts (n.s.). The tuned weights already
absorb the bias. Fix it only together with a retune.

---

## 5. Tracker and robustness findings (C)

### C1. Round 2 penalty freezes create phantom cooldowns

**Rules.** §4.4: a robot that does not reach its cell for a non-hardware reason
is "frozen for the next **3** turns". That freeze is not caused by any shield.

**Code.** The attribution solver (`bot.py:305-355`) looks for the set of shields
that exactly explains every new freeze. A penalty freeze gets "explained" as a
shield — the frozen bot's own backfire, or its landlord catching it — and that
seat's cooldown is set to 4.

**Measured** (`results/v7_penalty_base.txt`, 60 strangers games per row):

| penalty rate per robot-turn | rival cooldown exact | **unsafe**: believes a ready rival cannot shield |
|---|---|---|
| 0 (Round 1) | 99.8% | 0.01% |
| 1% | 96.0% | **2.51%** |
| 3% | 91.0% | **7.04%** |

An unsafe belief is the dangerous direction: the bot raids into a shield it
thinks cannot come.

**Fix.** A freeze still visible on its **third** consecutive turn is a penalty,
not a shield: undo that turn's attribution.

### C2. Stale state plus a missed turn-1 call: R = 1 all game

**Code.** The only turn-counter reset is `self.turn > 400` (`bot.py:226`). If
module state survives into a new game *and* the turn-1 call is missed, the turn
counter continues from 81. `R` is clamped to 1 (`bot.py:626-628`), so the bot
plays the entire game as if it were the last turn.

**Scenario** (`results/v7_scenarios.txt`, S2): **156 points against rivals' 2,656 /
2,736 / 2,736** — the do-nothing skeleton's level.

**Probability.** The starter kit says globals "are cleared when a new game
starts", so this needs two failures at once. It costs one line to close: reset
(or re-estimate the turn from the board) whenever the counter would pass 80.

### C3. The bot's edge depends on one reading of two durations

| constant | location | if the referee differs |
|---|---|---|
| 80 turns | `bot.py:22` | after turn 80, R clamps to 1: free shields on any intruder |
| shield cooldown 4 | `bot.py:353` | **−0.157 PW** at 3 turns, **−0.177 PW** at 5 ([§7.3](#73-alternative-referees)) |
| freeze 2 | `bot.py:279` | **−0.220 PW** if the catch turn counts as one of the two |

"Can't shield again for the next 4 turns" and "frozen for 2 turns" (§2.6) are
clear in prose but easy to count one turn differently in code. In particular,
"frozen for 2 turns" counted *including* the turn of the catch leaves only one
frozen turn. `engine.py` encodes one reading. The repository's robustness tests
flip five other ambiguous rules, but never these two.

The cost is not mainly the tracker. Only the shorter cooldown corrupts it (unsafe
beliefs 0.04% → 5.19%). The other drops come from the tuned parameters —
`freeze_cost`, `shield_cost`, `raid_risk`, `kappa` — which encode how much a
freeze and a cooldown are worth under the standard reading.

What to do:

- **Ask the organisers** how the server counts both durations. It is one email.
- **Calibrate at runtime.** The bot can read the real cooldown from its own
  `legal_actions` (the turn `SHIELD` leaves and returns after its own shield) and
  the real freeze from the `is_frozen` flags of any caught bot, then set the
  tracker's constants from what it saw.
- **Play one Arena game** with a deliberate early shield to observe both.

§1: "If any rule changes, every team is told, and the latest announcement
applies." Any announced change to the turn count or these durations needs a
retune, not just a constant edit.

### C4. Minor leaks (all small; most err on the safe side)

- **Intended vs effective action.** `self.last_action = a` (`bot.py:558`)
  records what the bot returned, not what the server applied. If the server
  plays `STAY` after a timeout, the solver forces "I shielded", finds no
  consistent explanation, and drops **every** shield attribution that turn.
- **Raid risk ignores a frozen landlord with cooldown 0** (`bot.py:1054-1059`
  uses `cd` for exposure, not `max(cd, frozen)`). Overstates risk.
- **Backfire probability** uses `1 − max(commit)` instead of `∏(1 − commit_j)`
  across intruders (`bot.py:1113`). Overstates backfire risk.
- **Non-imminent intruders** add nothing to a shield's value, although catching
  them freezes them and erases their banked stays.
- **Contest tie-break ignores "owner wins"** (§2.3; `bot.py:1171-1177`).
  Penalises stepping onto my own cell beside a higher-priority rival (I would
  win) and under-penalises entering a rival's cell beside its owner (they always
  win). Weight 0.043, tie-break only.
- **`CANON` assumes seat → corner** (`bot.py:53-65`). Round 2 §4.3: "The
  organisers assign each team's corner." Tie-break only (measured +0.002 by the
  project); derive the frame from `tr.homes[seat - 1]` instead.

---

## 6. Round 2 findings (D)

- **Penalty freezes break the tracker** — C1.
- **Movement exposure.** Per game on the strangers field: **24.1 moves, 15.2
  heading changes, 2.6 reversals.** Each move risks a 3-turn calibration penalty
  (§4.4: "the robot overshoots, undershoots or drifts"). `EXPLAINED.md` §10
  already notes a path-length penalty would help; nothing is implemented, and
  code locks before the first game (§4.2). Build and test a move-averse variant
  in advance.
- **Ranking rules differ from Round 1.**
  - §5.3: equal scores are separated by **cells owned**; the bot ignores cell
    count. (Round 1 counts equal scores as a draw, §3.2, but `engine.places()`
    uses the Round 2 tie-break everywhere — a measurement nuance.) Negligible.
  - Semi-finals: only the top 2 of 4 advance. Final: AED 3,000 / 2,000 / 1,500 /
    0. The single update allowed before the semi-finals (§4.2) can carry a
    stage-specific risk setting.

---

## 7. Testing against models that are not in this repository

Every opponent the bot was tuned and measured against was written in this
repository, by the same hand that wrote the bot — the project's own §10 names
this as "the weakest assumption". Two kinds of outside model were built for the
audit.

### 7.1 Eight opponent designs written from the rulebook alone

[`outsiders.py`](outsiders.py) shares no code with `zoo.py`, `aifield.py`,
`holdout.py` or `probot.py`, and each design is built on an idea the existing
field does not contain:

| design | idea |
|---|---|
| `x_fort` | claims **and** upgrades a compact cluster; shields only on a rival's third stay on an upgraded cell — the one shield that always works (B2 arithmetic). Never raids |
| `x_leech` | takes rival level-1 cells and **never bails**, even after being frozen |
| `x_homebait` | steps onto a rival's **home** and straight off to make its shield backfire, then raids during the cooldown; raids directly if baits stop working |
| `x_jackal` | trails the leader and steals its fresh level-1 claims, preferring owners on cooldown or frozen; farms when raiding is not better |
| `x_vulture` | farms for 58 turns, then raids **upgraded** cells (16·v bonus, never decays); shields free on turn 80 |
| `x_flaky` | a decent farmer that fails like real entries: 20% timeouts, illegal strings, 30% crash for good |
| `x_literal` | the single-prompt "first attempt": points per turn of effort, raid bonus included; shields on sight |
| `x_sim` | **different architecture**: no hand-written plan; random rollouts through a rules simulator for each legal action |

Each was smoke-tested with exceptions surfaced (the `STAY`-on-exception wrapper
hides crashes — the trap the project's own README describes). Two designs that
first scored under 1,000 were traced and strengthened before any measurement, so
the field is not a set of strawmen: against `spine`, `pro` and `camper` all eight
score 1,500–2,050.

### 7.2 Results

**Mixed field, all eight** (`results/v7_edge_outsiders_400_*`): **2.625 / 3**.

**Untuned field, outsiders + strangers** (`results/v7_edge_unknown_400_*`): **2.66 / 3**.

**Three copies of each** (`results/v7_edge_solo-*`), sorted hardest first:

| opponent ×3 | PW / 3 | pts | what it reveals |
|---|---|---|---|
| `x_homebait` | **2.46** | 2316 | hardest field; bot shields 8.5×/game, but B3 never fires |
| `x_vulture` | 2.56 | 2640 | late raids on upgraded cells; bot raids it 10.5×/game once it learns it ignores L1 intrusions |
| `x_literal` | 2.56 | 2520 | naive aggressive raider is a credible threat; highest backfire rate (0.40/game) |
| `x_sim` | 2.59 | 2519 | rollout architecture: mid-pack, not a blind spot |
| `x_jackal` | 2.80 | 2677 | **most cells lost of any field (3.4/game)**; 85% of L1 shields lost anyway |
| `x_flaky` | 2.94 | 2884 | 0.03 raids/game before turn 40 against bots that often stop shielding (B1) |
| `x_fort` | 2.99 | 2870 | 0.04 raids/game: correct against upgraded cells, but leaves undefended fresh claims (B1) |
| `x_leech` | 2.99 | 3117 | 82% of L1 shields lost anyway; `nol1` +9.6 pts (z +2.5) |

**Pairwise win rate against each design in the untuned mix** (lowest first):
`pro_tuned` **0.484**, `x_sim` 0.814, `ai_hawk` 0.825, `x_literal` 0.826,
`x_vulture` 0.845, `x_jackal` 0.855, … `centre` 1.000.

**Fixes on outside fields.**

| variant | outsiders | unknown | strangers |
|---|---|---|---|
| `nol1+home+free` | +2.6 ± 1.6 pts (n.s.) | +3.3 ± 2.2 pts, +0.0125 PW (z +1.5) | **+7.6 ± 2.3 pts (z +3.3)** |
| `q_weight:1.5` | +3.2 ± 9.3 pts (n.s.) | **+17.3 ± 6.6 pts (z +2.6)**, +0.0225 PW (z +1.4) | −6.2 ± 3.3 pts (z −1.9) |

**What the outside designs add.** Nothing in the new field breaks the bot, and
its strength holds on opponents it has never seen — the strongest evidence yet
that the project's results are not an artefact of its own field. The bot's
weakest matchups are the opportunistic level-1 raiders (`x_literal`, `x_jackal`,
`x_vulture`), which is B2 from the other side: level-1 territory cannot be
defended against a raider who waits out the freeze, so it is the bot's soft
underbelly.

### 7.3 Alternative referees

The server is the one model nobody can inspect. The repository tests five
ambiguous rules, but not the two durations `bot.py` hard-codes. "Can't shield
again for the next 4 turns" and "frozen for 2 turns" can each be counted one turn
differently by an implementer. [`referee.py`](referee.py) plays identical tasks
under each reading:

| referee reading | PW / 3 | pts | dPW vs standard | tracker unsafe beliefs |
|---|---|---|---|---|
| standard: cooldown 4, freeze 2 | 2.763 | 2565 | — | 0.04% |
| cooldown 3 (one turn shorter) | 2.607 | 2427 | **−0.157 ± 0.031 (z −5.0)** | **5.19%** |
| cooldown 5 (one turn longer) | 2.587 | 2454 | **−0.177 ± 0.041 (z −4.4)** | 0.11% |
| freeze 1 (catch turn counted) | 2.543 | 2416 | **−0.220 ± 0.041 (z −5.4)** | 0.07% |
| freeze 3 | 2.820 | 2594 | +0.057 ± 0.028 (z +2.1) | 0.08% |

300 paired games per reading on the strangers field
(`results/v7_referee_strangers_300_base.txt`). Every opponent plays under the same
referee, so these are changes in the bot's *relative* standing.

**This is the largest effect found in the audit.** A one-turn difference in
either duration costs 0.16–0.22 pairwise wins — more than any tuning gain the
project ever measured. The bot is still the strongest entrant under every
reading (2.54–2.82), but most of the edge the tuner bought rests on the engine's
counting being the server's counting. See C3 for what to do.

---

## 8. Checked and found sound

- **Interface** matches the starter kit exactly:
  - `Cell` attributes `occupant`, `owner`, `is_upgraded`, `is_home`,
    `is_frozen`, `base_points`;
  - `0` for empty and neutral;
  - `bot_id` 1–4;
  - board indexed `[row][col]`, `(0,0)` top-left, `NORTH` = row − 1;
  - action strings `NORTH EAST SOUTH WEST STAY SHIELD`;
  - `STAY` always legal; a frozen bot is offered only `STAY`.
- **Imports** are standard library only (`time`, `collections`).
- **`engine.py` matches the rulebook** on closed cells, contested cells, owner
  priority, shields not counting as stays, raid bonus `8 × v × level`, and
  upgradable homes.
- **Tracker accuracy in Round 1**: rival cooldowns 99.8% exact; unsafe errors
  0.01% of rival-turns.
- **Candidate reach of 5** never leaves the bot idle before the last 3 turns on
  any mixed field (`idle_late` = 0), and at most 0.04 turns per game in the solo
  runs.
- **No pacing**: 2.2–2.6 reversals per game on mixed fields.
- **Own cooldown** is checked against `legal_actions` as well as the tracker.
- **Stale README number.** "Shields on 1% of turns" describes v6. v7 shields
  **4.9 times per game (~6% of turns)** on the strangers field, and 5.9% of those
  backfire.

---

## 9. Reproducing

All commands run from the repository root; each writes its table to
`strategy_audit/results/`. They use up to 4 worker processes.

**`bot.py` is now v8**, and every command audits whichever bot `AUDIT_BOT` names
(default: the shipped `bot.py`). The tables in sections 1–11 are v7's, so to
reproduce them, pull v7 out of git history and point the harness at it for the
whole session:

```bash
git show 961e729:bot.py > /tmp/v7.py
```

```bash
export AUDIT_BOT=/tmp/v7.py
```

Then run the commands below. Each writes to `strategy_audit/results/` under a
name that starts with the label of the bot that produced it, read from the bot
file's own content: `v7` here, wherever the file was saved. A re-run therefore
lands on exactly the committed `v7_…` file, and reproduces it **byte for byte**
(checked for the scenario, turn-80, penalty and solo probes). The same command
run against the shipped bot writes a separate `v8_…` file, so neither version's
evidence can overwrite the other's.

**Result file names.**

- The pattern is `<bot>_<probe>_<details>.txt`. `<probe>` is `edge`, `referee`,
  `penalty`, `lastturn` or `scenarios`, and `<details>` is the tier, the number of
  games and the variants.
- The bot label comes from the file's content hash, line endings normalised:
  `v7` and `v8` for the shipped versions, `mybot` for the development source
  behind v8. Any other file gets `bot-<hash>` or `mybot-<hash>`, so an edited bot
  never writes over the results of the one it replaced.
- Names over 120 characters keep a readable prefix and end in a hash of the full
  name instead of being cut short, so two long runs cannot collide.
- The known hashes are listed in `KNOWN_BOTS` in [`edge_audit.py`](edge_audit.py).

All five scripts honour `AUDIT_BOT`. The v8-against-v7 tables of
[§12](#12-what-v8-changed) compare parameter files on the development source
(`AUDIT_BOT=mybot`) instead; their commands are in §12.7. Run `unset AUDIT_BOT`
afterwards to return to the shipped bot.

```bash
python strategy_audit/scenarios.py
```

```bash
python strategy_audit/edge_audit.py 600 strangers base nol1 home free offby1 q_prior:0.35
```

```bash
python strategy_audit/edge_audit.py 300 nonshield base q_prior:0.35 q_weight:1.5 q_weight:1.5+q_prior:0.5
```

```bash
python strategy_audit/edge_audit.py 500 realistic base nol1
```

```bash
python strategy_audit/edge_audit.py 400 strangers base q_weight:1.5 q_weight:1.5+q_prior:0.5
```

```bash
python strategy_audit/edge_audit.py 400 outsiders base nol1 home free q_weight:1.5 nol1+home+free
```

```bash
python strategy_audit/edge_audit.py 400 unknown base nol1+home+free q_weight:1.5
```

```bash
python strategy_audit/edge_audit.py 240 solo:x_leech base nol1
```

```bash
python strategy_audit/penalty.py
```

```bash
python strategy_audit/lastturn.py strangers
```

```bash
python strategy_audit/referee.py 300 strangers
```

Run time scales with games × variants, at roughly half a second per game per
worker. Every first-pass number in this document was re-run through these
committed scripts and reproduced exactly; see [§11](#11-limitations).

---

## 10. Recommended actions

1. **Before the deadline (Wed 11 Nov, 23:59 UAE).** Share the repository with
   the organisers; upload to the Arena; play one live game and confirm moves land
   where the bot intends. Confirm the original repository is private and that no
   other team has this code.
2. **Confirm the two durations (C3).** Ask the organisers how the server counts
   "frozen for 2 turns" and "the next 4 turns", or observe both in one Arena
   game. A one-turn difference costs up to 0.22 PW; if the server differs,
   retune on an engine that matches it.
3. **Decide B1.** *(v8: decided — kept at v7's value; see §12.)* It is the largest measured effect in either direction, and it
   is a judgement about the real field, not a bug. `q_weight 1.5` is the hedge;
   retune with it before shipping.
4. **Cheap, consistent wins:** B2 (`nol1`), B3 (`home`), B4 (`free`) — together
   **+7.6 pts (z +3.3)** on strangers, positive everywhere tested. *(Shipped in v8.)*
5. **Before the Round 2 code lock:** C1 (undo a freeze that lasts 3 turns), C2
   (reset past turn 80), and a move-averse variant. *(C1 and C2 shipped in v8; the
   move-averse variant is still open.)*
6. **Any change goes into `mybot.py` and is rebuilt with `python ship.py`** —
   `bot.py` is generated, and `ship.py` verifies the result plays move-for-move
   identically to the source, never raises internally, and stays far inside the
   time limit.

---

## 11. Limitations

- **The referee is a reconstruction.** Every game here runs on `engine.py`. The
  outside opponents remove one source of bias (the field); they cannot remove
  this one.
- **Fixes were tested one at a time** and in one combination, never retuned
  jointly. Several (B6 especially) interact with tuned parameters that were
  compensating for them.
- **The outside designs were written by the auditor**, from the rulebook alone,
  not by competing teams. They are independent of this repository's design
  lineage, not of every bias.
- **Small solo samples.** Solo runs use 80 games (240 for the two exploit probes);
  read their PW to about ±0.05.
- **Referee probe scope.** In [§7.3](#73-alternative-referees) every bot plays
  under the altered rule, and most opponents' own trackers also assume 4 and 2.
  The numbers are the bot's standing when the referee differs from what everyone
  assumed, not a full model of a re-tuned field.
- **Reproduction check.** The first pass of this audit ran from a scratch copy of
  the harness. Every one of its measurements was re-run through the committed
  scripts with the same seeds and reproduced **digit for digit**. Examples:
  strangers 600 base 2.7600 / 2579.7; `nol1` +5.69 ± 1.72; non-shield
  `q_prior 0.35` +119.14 ± 17.62; identical penalty, turn-80 and scenario
  outputs. Play is deterministic with the guards pinned, so the same Python
  version (3.13 here) reproduces every table exactly.

---

## 12. What v8 changed

`bot.py` now carries **v8**: v7's tuned weights, every one unchanged, plus the
switches below. It is built with:

```bash
python ship.py v8_params.json
```

It passes every `ship.py` check: standard library only, `act(state)` untouched,
identical play to `mybot.py`, no internal exceptions, the fallback intact, and 40
stress games with no failure (worst turn 23 ms against the 200 ms limit).

### 12.1 Status of every finding

| id | finding | in v8 | switch |
|---|---|---|---|
| A1–A3 | submission risks | **open — team actions**, not code | — |
| B1 | raid prior is a field bet | **kept as v7** — faster learning costs 0.111 PW on the peer field (12.4) | `q_prior`, `q_weight` unchanged |
| B2 | shields spent on level-1 cells | **fixed** | `shield_l1: 0` |
| B3 | rival on my home priced as a threat | **fixed** — the S1 scenario now fires at no turn at all (`results/v8_scenarios.txt`) | `shield_home: 0` |
| B4 | turn-80 shield ignores my own last stay | **fixed** | `last_shield_value: 1` |
| B5 | turn-80 raids priced optimistically | open — field-dependent | — |
| B6 | income horizon one turn short | open — the tuned weights absorb it; needs a retune | — |
| C1 | Round 2 penalty freezes read as shields | **partly fixed** — unsafe beliefs cut by 20–27% (12.6) | `penalty_undo: 1` |
| C2 | stale state pins R = 1 all game | **fixed** — 156 points → **2,584** in the S2 scenario | `turn_guard: 1` |
| C3 | edge tuned to one reading of the durations | **partly fixed** — v8 is never worse than v7 under any reading (12.3); the weights still encode 4 and 2 | `calibrate: 1` |
| C4 | minor leaks | **fixed**: own shield that never happened, backfire product, owner-wins contests, home-derived frame. `risk_frozen` implemented, measured slightly worse, left off | `solver_retry`, `backfire_prod`, `contest_owner`, `canon_home`: 1; `risk_frozen`: 0 |
| D | Round 2 movement and ranking | open | — |

`calibrate` measures three things at runtime: the cooldown from the turn
`SHIELD` returns to the bot's own `legal_actions`; an upper bound on it from the
same rival shielding twice; and the freeze length as the shortest freeze seen to
start mid-game (a penalty can only make a freeze look longer).

### 12.2 Proof that the refactor changed nothing by itself

Every switch's default in `mybot.PARAMS` reproduces v7. Three independent checks:

- [`check_v7_compat.py`](check_v7_compat.py): `mybot.py` with `v7_params.json`
  against the v7 `bot.py` read from git history — **60 games, 4,800 decisions,
  identical.** Run again after every later change to the tracker.
- The v7 row of every v8 table reproduces the original audit exactly, e.g.
  strangers 600 at **2.7600 / 2579.7**, and the whole alternative-referee table.
- `test_tracker.py`, `test_guards.py` and `test_determinism.py` pass.

### 12.3 v8 against v7

Paired on identical games (`AUDIT_BOT=mybot`, `@v7_params.json` against
`@v8_params.json`; `results/mybot_edge_*_v7_params_v8_params.txt`):

| field | PW / 3 (v7) | dPW | dScore |
|---|---|---|---|
| strangers (600) | 2.760 | −0.002 ± 0.005 | **+7.2 ± 1.8 (z +3.9)** |
| peer (400) | 1.951 | +0.000 ± 0.005 | **+3.5 ± 1.3 (z +2.8)** |
| realistic (500) | 2.529 | +0.008 ± 0.008 | **+4.3 ± 1.9 (z +2.3)** |
| unknown (400) | 2.660 | +0.010 ± 0.008 | +3.2 ± 2.2 |
| outsiders (400) | 2.625 | +0.005 ± 0.005 | +2.6 ± 1.7 |
| nonshield (300) | 2.877 | +0.007 ± 0.005 | +4.5 ± 3.6 |

Under each referee reading, paired over the same 300 strangers games
(`results/mybot_referee_strangers_300_*.json`):

| referee | dPW | dScore |
|---|---|---|
| standard: cooldown 4, freeze 2 | **+0.013 ± 0.007 (z +2.0)** | **+6.2 ± 2.9 (z +2.1)** |
| cooldown 3 | +0.023 ± 0.019 | **+26.4 ± 6.7 (z +3.9)** |
| cooldown 5 | +0.023 ± 0.016 | **+14.4 ± 4.8 (z +3.0)** |
| freeze 1 | −0.003 ± 0.023 | **+18.8 ± 8.4 (z +2.3)** |
| freeze 3 | **+0.030 ± 0.014 (z +2.2)** | **+35.6 ± 8.2 (z +4.3)** |

Points improve in all eleven comparisons, eight significantly; pairwise wins are
never significantly worse. v8 is a robustness release, not a strength jump: its
largest gains come under rule readings that differ from the engine's. And the
sensitivity in C3 remains: under any alternative reading, v8 still sits 0.15–0.24
PW below its own standard-rules result.

### 12.4 How the configuration was chosen

The draft v8 switched everything on. Isolating the two uncertain switches and the
B1 hedge on that draft (`results/mybot_edge_*_v8draft_*.txt`):

| change on the draft | strangers (600) | unknown (400) | other fields |
|---|---|---|---|
| `q_weight` 1.5 | **−0.020 PW (z −2.1)** | +0.028 PW (z +1.7), +17.4 pts (z +2.5) | peer **−0.111 PW (z −3.9)**; nonshield +48 pts (z +3.7); realistic and outsiders n.s. |
| `risk_frozen` off | +7.2 pts (draft with it on: +6.7) | +3.2 pts (on: +0.7) | — |
| `backfire_prod` off | +6.7 pts (identical) | +1.1 pts (on: +0.7) | — |

- **`q_weight` stays at v7's value.** The hedge gains points mostly where the bot
  already wins about 96% of pairings and loses placements where they are actually
  contested. Round 1 is Elo, where beating strong bots matters most.
- **`risk_frozen` is off.** It is the more correct model, but it measured slightly
  worse on both fields where it was isolated, presumably because the tuned raid
  weights were fitted without it.
- **`backfire_prod` is on.** It is inert in measurement and the more correct model.

### 12.5 A regression caught before shipping

The draft v8 was measured against alternative referees before it shipped, and one
reading exposed a bug in the new code (`results/mybot_referee_strangers_300_v8draft.*`):

| referee | draft v8 − v7 | shipped v8 − v7 |
|---|---|---|
| freeze 3 | **−0.070 PW (z −3.0), −32.6 pts** | **+0.030 PW (z +2.2), +35.6 pts** |

**Cause.** `penalty_undo` treats a freeze that outlasts a shield freeze as a Round 2
penalty. When the server's shield freeze itself lasts 3 turns, and before the
freeze length had been calibrated, every real shield looked like a penalty, so
real cooldowns were withdrawn. The draft also calibrated only from freezes the
bot's own shield caused, and v8 shields less often.

**Fix.**

- The freeze length is now the minimum over every freeze that starts mid-game.
- Freezes already present on the first board are ignored.
- `penalty_undo` acts only once the freeze length has been seen.
- The cooldown gains an upper bound from rivals shielding twice.

### 12.6 Round 2 penalty freezes

`penalty.py`, 60 strangers games per row (`results/mybot_penalty_v7_params.txt`,
`results/mybot_penalty_v8_params.txt`):

| penalty rate per robot-turn | v7 unsafe beliefs | v8 unsafe beliefs |
|---|---|---|
| 0 (Round 1) | 0.01% | 0.01% |
| 1% | 2.51% | **2.01%** |
| 3% | 7.04% | **5.11%** |

A partial fix by construction: for its first two turns a 3-turn penalty is
indistinguishable from a 2-turn shield freeze, so the withdrawal can only happen
on the third.

### 12.7 Reproducing §12

```bash
python strategy_audit/check_v7_compat.py 60
```

```bash
AUDIT_BOT=mybot python strategy_audit/edge_audit.py 600 strangers @v7_params.json @v8_params.json
```

```bash
AUDIT_BOT=mybot python strategy_audit/referee.py 300 strangers @v7_params.json
```

```bash
AUDIT_BOT=mybot python strategy_audit/referee.py 300 strangers @v8_params.json
```

```bash
AUDIT_BOT=mybot python strategy_audit/penalty.py @v8_params.json
```

The other fields take the same form as the first `edge_audit.py` command with
`peer 400`, `realistic 500`, `unknown 400`, `outsiders 400` or `nonshield 300`.
The referee probe saves per-game results as JSON, so the paired v8 − v7 table in
12.3 is computed from the two `mybot_referee_strangers_300_*.json` files.

---

## 13. v9: forecasting rivals

v9 is v8 plus one switch, `forecast: 1`: a Bayesian goal-inference forecaster
(`Forecaster` in `mybot.py`; method in `EXPLAINED.md` §5.5). It infers each
rival's target from that rival's own moves in the current game, instead of
relying on a model of opponents fitted to the tuning field. Its constants (β 2,
ρ 0.9, κ 3, a two-target chain) were fixed before any measurement and never tuned.

Results were produced by `mybot.py` as shipped in v9, labelled `mybot-0ba97d3b`
by its content hash, and by the shipped bots (`v8`, `v9`) for the forecast probe
and scenarios.

### 13.1 Can it see where rivals are going?

[`forecast_probe.py`](forecast_probe.py) puts an observer in the bot's seat,
forecasts every moving rival each turn, and scores the forecast against what the
rival actually did (`results/v8_forecast_unknown_200.txt`,
`results/v8_forecast_realistic_200.txt`).

| held-out field: outside designs + strangers, 200 games | forecast | rule prior, no inference | stays put | keeps going |
|---|---|---|---|---|
| next destination found (11,268 cases) | **48.0%** | 48.1% | 1.1% | — |
| probability given to the true destination | **0.088** | 0.081 | — | — |
| position error, 1 turn ahead (cells) | **0.78** | 0.80 | 1.00 | 1.00 |
| position error, 3 turns ahead | **1.31** | 1.32 | 1.55 | 1.76 |
| position error, 8 turns ahead | **2.17** | 2.18 | 2.54 | 2.86 |

The training-like field gives the same picture (47.0% against 47.6%; 0.091
against 0.085; 2.09 against 2.43 and 2.77 at 8 turns). By design, the naive
`x_literal` and `pro` are forecast 72–74% of the time and the erratic `x_flaky`,
`x_fort` and `ai_route` about 20%.

Most of the power comes from planning from the rival's point of view (the prior).
Watching its moves adds calibration, not accuracy.

The probe also found three modelling errors before anything shipped, each fixed
and documented in the code:

| version | finds the true destination |
|---|---|
| likelihood of the exact move | 2.5% |
| goals persisting about ten turns | 19% |
| every stay read as continuing work | 16% |
| shipped: distance-event likelihood, current prior × decaying evidence, legs end when work finishes | 48% |

### 13.2 Does using it win games?

Paired against v8 on identical games (`AUDIT_BOT=mybot`, `@v8_params.json`
against `@v8_params.json+forecast:1`; `results/mybot-0ba97d3b_edge_*`).

| field | first draw | confirmation, fresh tasks (seed 101) | pooled |
|---|---|---|---|
| **unknown** (outside designs + strangers) | +0.045 PW (z +1.75), +22.6 pts | **+0.053 PW (z +2.57)**, −1.7 pts | **+0.050 ± 0.016 PW (z +3.1)**, +8.0 pts (n.s.) |
| outside designs | +0.053 PW (z +1.97), +28.6 pts | +0.015 PW (z +0.64), +8.6 pts | +0.030 ± 0.018 PW (z +1.7), **+16.6 ± 7.5 pts (z +2.2)** |
| **strangers** | −0.008 PW, −8.5 pts | **−0.040 PW (z −2.14)**, −18.2 pts | **−0.024 ± 0.014 PW (z −1.8)**, −13.3 ± 6.9 pts (z −1.95) |
| peer (strongest) | +0.014 PW, +2.6 pts | — | — |
| realistic | −0.007 PW, +6.1 pts | — | — |
| never-shield | +0.030 PW (z +1.5), −6.5 pts | — | — |
| 3× `x_jackal` | +0.033 PW, +18.2 pts; cells lost 3.72 → **3.02** | — | — |
| 3× `x_leech` | +0.000 PW, −2.3 pts | — | — |

The confirmation draw was run because the first draw's best numbers are biased
upward (README: "The tuner was selecting luck"). It did its job: the outside-designs
gain shrank from z +1.97 to +0.64, and the strangers loss grew.

### 13.3 Decision

Shipped, because the method's purpose is generalising to opponents the bot has
never seen. The field built for that — mixed lineups with nothing tuned against —
gains **+0.050 PW (z +3.1)** over 1,000 games, and nothing significant is lost
against the strongest bots. The cost is real: **−0.024 PW (z −1.8)** against the
repository's own strangers, and the points gain on the unknown field did not
replicate. The forecaster's constants were not adjusted to remove that loss: doing
so would fit them to the very field used to judge them.

**Conservative alternative:** `forecast: 0` reproduces v8 move for move
(`python ship.py v8_params.json`), and v8 is on branch `claude/strategy-audit-v8`.

**Untested:** the forecast is only used to avoid cells a rival will reach first. Its
other natural use, defence — reaching and holding a level-1 cell before a forecast
raider arrives, since shields cannot save those (B2) — has not been tried.

### 13.4 Reproducing §13

```bash
python strategy_audit/forecast_probe.py 200 unknown
```

```bash
AUDIT_BOT=mybot python strategy_audit/edge_audit.py 400 unknown @v8_params.json @v8_params.json+forecast:1
```

```bash
AUDIT_BOT=mybot AUDIT_SEED=101 python strategy_audit/edge_audit.py 600 unknown @v8_params.json @v8_params.json+forecast:1
```

The other rows take the same form with `outsiders`, `strangers`, `peer 400`,
`realistic 500`, `nonshield 300`, `solo:x_jackal 120` or `solo:x_leech 120`. Runs
land on exactly the committed file names as long as `mybot.py` is unchanged; an
edited `mybot.py` gets a new label and writes new files instead of overwriting
these.
