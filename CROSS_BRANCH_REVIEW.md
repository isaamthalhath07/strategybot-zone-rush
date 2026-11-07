# Cross-branch review: four strategies, one field, one fused bot

This repository had four branches, each with its own answer to "what should
`bot.py` be", and each measured on a field written by the same author that wrote
the bot:

| branch | what it is |
|---|---|
| `hardened-field-and-fixes` (= `main`) | **v7**: hidden-state tracker + beam search over walks, 50 tuned weights |
| `v7-independent-field` | a different **v7**: v3's economic weights on v6's deeper search, chosen on a new 8-bot field |
| `research/evolution-2026-11-07` | an **evolved economic planner**: rate ranking with 2-job lookahead, 23 evolved genes |
| `visual-harness` | no strategy: a referee, a per-seat subprocess runner and a browser viewer |

This review puts all of them on one field nobody tuned against, critiques each,
fixes what is broken, and ships a fused bot. Every number below was produced in
this round and can be reproduced with the commands at the end.

**Bottom line.** The research branch's economic planner is the strongest decision
policy in the repository. On 1,200 fresh paired games it beats main's v7 by
**+0.215 pairwise wins (z = +8.0)** and is not worse against any author's
opponents. Nothing tried on top of its decisions survived confirmation. What it
lacked was everything *around* the decisions: no exception handling at all, and on
five of eleven plausible server-interface variants it scored what the do-nothing
skeleton scores. The shipped `bot.py` is therefore that planner, move-for-move
identical on the documented interface, wrapped in main's tracker and walk planner
as a warm standby and eight further failsafe layers. Measured against every other
branch's bot it is the only one that survives every interface variant tested.

---

## 1. Putting four branches on one field

`crossfield/xfield.py` is the measuring instrument. Each design choice removes a
bias that one of the branches' own measurements had:

| choice | the bias it removes |
|---|---|
| opponents grouped **by author** (main's 15 designs, the independent field's 8, the research population's 11, the 5 public shipped bots, 7 weak bots at half weight), sampled group-first | each branch's field was dominated by its own author, and an author who writes more bots dominates a pooled field |
| pairwise credit **attributed per opponent** inside mixed lineups | "beats three copies of X" is not the Round 1 field (main's README says so; the independent branch selected on it anyway) |
| **six map families** from both generators | main tuned only on its own centre-slope generator (319 distinct maps in 500 seeds) |
| **both `legal_actions` conventions** (with and without moves into occupied cells) | the research referee drops those moves; main's engine and the harness keep them |
| **Round 1 scoring**: equal scores are half credit | `engine.Game.places()` broke score ties on cells owned, which is the Round 2 rule (now fixed in `engine.py`) |
| **paired tasks**, paired standard errors | identical (map, seat, lineup, token, interface) for every variant |
| **fresh module namespace per game**, own board copy per seat | module memory leaking between games; a bot mutating a shared board |
| wall-clock guards pinned for every opponent that has them | `research/user_family.py` ports main's 60 ms budget; it made results load-dependent until pinned |

The rules themselves were checked first. `engine.py`, the visual harness's
`referee.py` and the research branch's `arena.py` are three independent readings
of the rulebook. Under random play with shields, illegal actions and random maps
they agree **exactly, state by state, over 400 games and 32,000 turns**. The engine
is trustworthy as far as three readings can make it; none of them is the
organisers' server.

Controls that validate the harness itself: the fused bot against the research bot
it wraps measures **0.0000 ± 0.0000 over 1,200 games**. Repeated games are
identical once the one opponent with a wall clock is pinned, and main's
`test_determinism.py` still passes.

### The result

1,200 fresh paired games (`--seed=9`), PW out of 3:

| bot | PW/3 | credit | vs fused | z | vs main | vs indep | vs research | vs shipped | vs weak |
|---|---|---|---|---|---|---|---|---|---|
| **fused `bot.py`** | **2.406** | **80.2%** | — | — | 90.8% | 88.1% | 70.8% | **60.8%** | 98.3% |
| research evolved | 2.406 | 80.2% | 0.0000 | (identical) | 90.8% | 88.1% | 70.8% | 60.8% | 98.3% |
| research finalist | 2.392 | 79.7% | −0.015 | −0.6 | 90.1% | 87.5% | 71.9% | 58.9% | 97.8% |
| main v7 | 2.191 | 73.0% | −0.215 | −8.0 | 89.0% | 82.6% | 60.5% | 45.7% | 98.0% |
| independent v7 | 2.173 | 72.4% | −0.233 | −8.5 | 87.9% | 81.6% | 62.3% | 43.5% | 97.5% |
| v6 | 2.147 | 71.6% | −0.260 | −9.3 | 86.7% | 82.3% | 60.6% | 41.1% | 98.5% |

The baseline run (`--seed=1`, 800 games) had already given the same ordering:
evolved +0.169 over main v7 (z = +5.0), independent v7 −0.083 (z = −2.7).

---

## 2. Each strategy, critically

### 2.1 `hardened-field-and-fixes` — main's v7 beam planner

**Strengths, all confirmed here.** The tracker is the best piece of engineering in
the repository: scores, progress, positions, freezes and the token are exact, and
cooldowns are 99.2% exact (re-run: 25 ambiguous of 3,200). It survives losing
module memory every turn almost intact (2,462 vs 2,520), because it reconstructs
from the board. It has a real fallback policy, a hard deadline, and the most
honest measurement culture of the four (paired A/Bs, a confirmation stage, a
retraction kept in the README).

**Where it overfits.**
- Its own README concedes the headline: +0.251 on `peer`, where six of eleven
  entrants are its own snapshots, but +0.024 on strangers. On this field v7 does
  beat v6 (+0.044 to +0.09), so the gain is real but small.
- Its objective is a field artefact. Main's tuner drove `care_mode` to 4 ("ignore
  rivals", `w_denial` 0.21); the independent branch's selection drove the same
  code to `care_mode` 0 (`w_denial` 1.21). Two fields, opposite conclusions about
  the single most important strategic choice, from the same architecture.
- Fifty tuned weights, several pinned at their bounds (`squat_penalty` 0.05,
  `def_kappa` 0.3, `zone_bonus` 1.0).
- Every tuning game used one map generator.

**Where it breaks.**
- **Off-by-one income** (`_work_gain`). Takes resolve before scoring, so work
  that completes with R turns left pays R − used − need + 1 turns. v7 counted one
  fewer, so a capture on the final turn was valued at `None` and the bot walked
  away from free points. Fixed as `pay_fix`; worth +0.018 to the walk planner.
- **The clock resets in an all-home opening.** Five turns of everyone staying
  home read as turn 1 with every score 0 (true: turn 6, scores 8). Fixed. The fix
  took three attempts, each caught by a test written for the previous one (§5).
- **A flat board of namedtuple cells plays STAY all game.** The 2-D test was "is
  `bd[0]` a list or tuple", and a namedtuple is a tuple. The fallback used the
  same parser, so both failed silently. Fixed (`_flatten`).
- **A rival standing on my home counted as an imminent take.** Homes cannot be
  captured. Mid-game this burned shields; on the last turn it shielded instead of
  completing its own raid. Fixed: homes are excluded, and the final-turn shield
  is weighed against what its own stay would complete.
- **A SHIELD the server turned into STAY wiped a rival's real shield.** The
  attribution solver insisted the requested shield happened, found no consistent
  explanation, and recorded no shield at all. Fixed by solving under both
  hypotheses.
- **`bot_id` as a string** computed `"1" * 7919 * 2654435761`: a crash at best, a
  multi-gigabyte allocation at worst. Fixed (`int()`).
- **Homes reported as unowned** were all assigned to seat 1. Fixed (corner
  fallback).
- **`python ship.py` crashed.** Its default `best_params.json` had been renamed.
  Fixed: it now builds the fused bot, and `python ship.py route <params>` builds
  the walk planner alone.
- **`runtests.py`'s audit gate fired on every run**, because two opponents are
  pathological by design. It now fires only when the bot itself is flagged.

**Interface robustness:** five of eleven variants fall to the skeleton's score
(§4), and a NORTH/SOUTH-swapped server leaves it 17% of its score.

### 2.2 `v7-independent-field` — v3 economics on v6 search

**Strengths.** It asked the right question first: are all the opponents mine? Its
eight new opponents (`route`, `grab`, `seq`, `rollout`, ...) are a genuine second
author and are part of the field here. Its finding that re-tuning on a broader
field overfits within 18 generations is correct and was kept.

**Where it overfits.**
- **Selection on the evaluation field.** v7 was *chosen* for doing best on
  `bench2.py`, then reported on `bench2.py`. Opponents "never used to tune either
  version" were still used to select.
- **Selection on three-copy trios**, which main's own README calls a
  non-model of Round 1. Eight of its fourteen scenarios are trios.
- **The result does not hold on a neutral field.** It is −0.233 behind the fused
  bot and −0.018 to −0.083 behind main's v7. Against *its own author's* opponents,
  in mixed lineups, it is also behind main's v7 (81.6% vs 82.6%; 81.0% vs 83.4% in
  the baseline). A margin objective (`w_denial` 1.21) wins three-copy trios against
  farmers and loses the four-player general-sum game, where hurting one rival
  hands points to the other two.

**Where it breaks.** It is main's code from *before* the hardening pass:
- no fallback policy: any internal exception means STAY;
- no new-game reset of the agent: state leaks across games in one process;
- no shield-cooldown cross-check, no progress-carry detection, no seat-symmetric
  tie-breaks;
- every main-v7 bug listed above.

It is the worst on the interface matrix: six of eleven variants fall to the
skeleton's score, and losing module memory costs it 31%.

### 2.3 `research/evolution` — the evolved economic planner

**Strengths, and they are the decisive finding of this review.** Its headline
claim replicates on a field it never saw. It claimed +8.2 points of pairwise
credit over v6 on its own field; on this one it is +8.6 (80.2% vs 71.6%). It is
never worse than main's v7 against any author group, and against every group it
is the best of the five bots or within 1.1 points of it. Its genome sits at a
local optimum *on this field too*: seven single-gene probes found nothing (§3),
including two that move bound-pinned genes past their bounds. It is also fast
(0.3 ms mean per turn), with a predeclared promotion rule and bootstrap
intervals.

**Where it overfits.**
- Its audit field is dominated by its own lineage: `economic_*` descendants,
  its own incumbent, and its own responses. Main's shipped v7, its `probot`
  rival, its `aifield` designs and the independent branch's agents were never in
  it.
- That matters in one place. Against main's own designs, the field where main
  was tuned, it is level with v7 (90.8% vs 89.0%), not ahead.
- Per opponent, in mixed lineups, main's planner does better against pure
  farmers (camper, guard, spine, ai_cheapraid, pro: about 98% vs 91% of 191
  pairings). The
  cause is not farming skill: unopposed and against three farmers the two score
  the same (3,566 vs 3,512). It is the four-player trap. The evolved denial terms
  draw it into fights with the aggressive bots at the table, and the passive
  farmer collects the difference.
- Sixteen boards per audit, four per generator, as its own report concedes.

**Where it breaks.**
- **No exception handling anywhere in `act()`.** Five of eleven interface
  variants score 158, the skeleton's score: dict cells, a string `bot_id`,
  lower-case actions, Enum-like actions, a missing token flag.
- **Losing module memory costs 23%** (1,803 vs 2,349). Its cold-start turn
  estimate (`2 + owned + upgrades`, capped at 67) has a median error of 9 turns,
  against 5 for main's fitted estimate.
- **A NORTH/SOUTH-swapped server leaves it 33% of its score.**
- **The manifest's SHA-256 does not match the committed file**: 20,669 bytes
  hashed, 20,230 committed. The 439-byte gap equals the file's 439 lines, which is
  consistent with hashing a CRLF copy. Either way, anyone verifying the manifest
  against the repository gets a mismatch.
- Its memory is keyed by seat in a module dict, so two simultaneous games in one
  process would collide.

### 2.4 `visual-harness`

Not a strategy, so the critique is of its strategy *for testing*.

**Strengths.** It is the most faithful server model of the four: one process per
seat with `python -I`, the board rebuilt from JSON into `Cell` objects,
stdout captured so a stray `print` cannot corrupt the protocol, and the 200 ms /
2 s limits enforced. Its referee agrees with the other two exactly (§1). The
shipped bot was run through it in every seat: clean, at most 0.7 ms per turn.

**Weaknesses.**
- It cannot measure strength: one game at a time, and its built-in bots are
  only the skeleton and a random bot.
- Its random-map generator is byte-for-byte main's, so it adds no map diversity.
- It gives no robustness coverage of off-spec inputs, which is where three of
  the four bots actually break.

---

## 3. What combining them measured

Every candidate was tested paired against the research bot on one task set. Only
a candidate that then held up on fresh task sets would have been adopted. Main's
README documents exactly how a tuner selects luck, and this round reproduced that
trap once (the sym_far row).

| candidate | discovery | confirmation | verdict |
|---|---|---|---|
| main's walk planner as the primary (with all five fixes) | −0.158 (z −4.7) | — | rejected; kept as the warm standby |
| `pay_fix` inside the walk planner | +0.018 over no fix | — | kept: it is a correctness fix |
| econ reads the exact tracker's rival cooldowns | +0.0075 (z +1.1) | −0.006 (z −0.9) | neutral, off |
| seat-symmetric ties, nearest own corner | −0.024 (z −1.0) | — | rejected |
| seat-symmetric ties, farthest own corner | +0.021 (z +0.9) | +0.044 (z +1.8; seats 2–4 z +2.1), then **−0.009 (z −0.4)** | rejected: selection luck |
| research finalist genome | +0.004 | −0.009 (z −0.3); −0.015 (z −0.6) | rejected |
| `denial_base` 0.33 | +0.029 (z +1.6) | −0.004 (z −0.2) | rejected |
| `denial_base` 0 / `risk_late` 12, 5 / `upgrade_late` 4.5 / `route_delay` 0 / `cash_weight` 0.8 | +0.005 / −0.019, −0.025 / +0.003 / +0.016 / −0.014 | — | all noise; the best of seven z-scores (1.6) is what chance produces |
| **predict exact copies of public bots** (`mirror`) | see below | — | built, rejected as unsafe, off |
| **cold start: walk planner for one turn + tracker turn estimate** | single restart: 2.385 vs 2.338 for walk-planner-for-the-rest-of-game; memory lost every turn: 96% vs 88% | — | **adopted** |

Two notes on that table:
- The seat-symmetry probes had a built-in control. For seat 1 the canonical frame
  *is* the raw frame, so seat 1 changed in zero games in every run, as it must.
- The seed-4 single-gene probes ran before a reset bug in the controller was found
  (§5). That bug was rare, but it hit every fusion variant equally. The best probe
  was then re-run on fixed code (seed 5) together with the control, which came out
  exactly 0.0000.

**Why "predict the copies" is off.** This is the out-of-the-box idea, and it
deserved a real attempt. The repository is public and its strongest bot is
deterministic, so a copy's move this turn is computable. It sees the same board,
and its seat, token, legal list and cooldown can all be reconstructed. With that
prediction, the shield/raid stand-off against a copy is a solved game: shield
exactly on its completing stay, and step off just before its shield.
`fusion._FMirror` implements this, replaying from turn 1 once the token is known
and retiring a hypothesis on a single mismatch. `crossfield/exp_mirror.py` then
asks the question that matters: is identification safe?
- Requiring 10 matching turns, it recognised 50 of 50 true copies **and 25 of 70
  non-copies**.
- With no threshold at all, near-relatives matched for **63–79 turns** before
  diverging. These were `economic_f04298…` (the same code with a slightly
  different genome) and `incumbent`.
- They diverge precisely at close shield and raid decisions, which is exactly
  where the exploit would act.

No match count separates them, so the option ships switched off.

---

## 4. The fused bot

`bot.py` is built by `ship.py` from three development modules and verified by
`crossfield/acceptance.py` before it is written as ready:

| file | role |
|---|---|
| `econ.py` | the research planner as a class; `crossfield/test_econ.py` proves it is move-for-move identical to the research file (3,840 turns, both genomes) |
| `mybot.py` | main's tracker and walk planner, with every fix in §2.1; split into `ingest()` / `plan()` so it can be kept current every turn without searching |
| `fusion.py` | normalisation, failsafes and the controller |

The decision chain is econ → walk planner → `_fallback` → STAY. Each link runs
under its own `try/except`, a link that raises is replaced *on the same turn*, and
one that raises twice is retired for the rest of the game.

**What the acceptance suite checks, with this build's results:**

| check | result |
|---|---|
| pure ASCII, Python 3.7 grammar, stdlib-only imports, one `act(state)`, no `print/open/exec` | pass |
| identical to `fusion.py`; identical to the research bot on the documented interface | pass, pass |
| four seats sharing one module; game 2 in a reused module equals game 2 in a fresh one | pass |
| failsafe chain vs 3 spine: healthy / econ raises / both planners raise / everything raises | 2,581 / 2,575 / 1,109 / 158 |
| eleven interface variants | 0 degrade |
| module memory lost every turn | 2,462 (normal: 2,349) |
| server that offers SHIELD during cooldown and scores it as STAY | 0 shields sent on cooldown |
| server with NORTH and SOUTH swapped | 2,558 vs 2,558 |
| all-home opening; a rival stepping out of its home and back | both clocks and all scores exact |
| live clock, real guards, 24 games | mean 0.33 ms, p99 0.63 ms, max 2.3 ms (limit 200) |
| visual harness, separate process per seat, every seat | clean, max 0.7 ms |

**The interface matrix** (`crossfield/robustness.py`). One game against three
spines; 158 is what the do-nothing skeleton scores.

| server variant | main v7 | indep v7 | evolved | evolved finalist | **fused** |
|---|---|---|---|---|---|
| documented 8×8 `Cell` objects | 2520 | 2640 | 2349 | 2274 | 2349 |
| flat 64-list / namedtuple rows / tuple board / 0-1 ints | ok | ok | ok | ok | ok |
| flat 64-list of namedtuples | **158** | **158** | ok | ok | ok |
| cells are dicts | **158** | **158** | **158** | **158** | ok |
| `bot_id` as a string | **158** | **158** | **158** | **158** | ok |
| lower-case action strings | **158** | **158** | **158** | **158** | ok |
| Enum-like action objects | **158** | **158** | **158** | **158** | ok |
| `is_priority_token` missing | 1596 | **158** | **158** | **158** | ok |
| fresh module every turn | 2462 | 1810 | 1803 | 1782 | **2462** |
| NORTH/SOUTH swapped (4 games) | 17% | 18% | 33% | — | **100%** |

---

## 5. Things that could go wrong that nobody had tested

Each item below names a failure mode, how `bot.py` handles it, and the evidence.

1. **The server's objects are not the documented ones.** All eleven matrix
   variants are handled by normalisation. The returned action is always the
   server's own legal-list element, in its own type.
2. **The server reloads the module (amnesia), once or every turn.** A single
   restart hands the planner the tracker's fitted turn estimate after one
   walk-planner turn. Memory lost on every turn is handled by the walk planner,
   which reconstructs from the board alone. Measured: 96% of normal score.
3. **Several games in one process.** New games are detected from the board, and
   planners are rebuilt. A reused module plays game 2 exactly like a fresh one.
4. **Openings where positions revert.** This caught three successive bugs, each
   exposed by the test written for the one before:
   - v7 reset on any starting board;
   - my first fix still reset when a rival stepped out and back;
   - my second fix reset when the homes *upgraded* during the all-home stays,
     because the tracker's "fresh" test ignored upgrades.

   The rule that holds is that positions revert but ownership and upgrades do not.
5. **SHIELD offered during cooldown, or SHIELD silently turned into STAY.** The
   exact tracker gates own shields, and attribution is solved under both
   hypotheses.
6. **A different movement convention.** The bot learns it online from its own
   displacements *and* from legal lists. Legal lists turned out to be essential:
   in a flipped frame at the corner the planner never proposes the one move that
   would reveal the flip, so displacement evidence alone never starts.
7. **A planner bug that only some boards trigger.** Planners are isolated and
   retired, with an independent standby kept warm.
8. **A slow or loaded grader.** The primary takes 0.3 ms. The standby has a 60 ms
   deadline and an adaptive beam (main's `test_timing.py`: tolerates a machine
   100× slower).
9. **Encoding and Python-version surprises.** The file is pure ASCII and parses
   as Python 3.7.
10. **stdout used as the protocol channel**, as in the visual harness. Nothing
    prints, and the acceptance suite checks it.
11. **Rivals reading this public source.** The walk planner's shield mixing is
    seeded from the clock on the server. The primary is deterministic, and a
    perfect copy of it could in principle be exploited. §3 shows that even
    exploiting perfect copies is unsafe, because near-copies are
    indistinguishable, which cuts both ways.
12. **Measuring the wrong thing.** Round 2 tie rules in Round 1 numbers, one map
    generator, opponent timing under load, self-family fields: each is fixed in
    the harness, and the first is also fixed in `engine.py`.

**Residual risks, stated rather than hidden:**
- **Two simultaneous games in one process for the same seat** would interleave
  boards. No design handles this without a game id the starter kit does not
  provide.
- **A game longer than 80 turns** would be played as a permanent final turn.
  The rulebook fixes 80.
- **The hardware round's physical failure modes** are outside anything a
  simulation here can measure.

---

## 6. Reproducing

```bash
python ship.py
```

```bash
python crossfield/xfield.py 1200 --seed=9 fused=file:bot.py main_v7=opp:main_v7 indep_v7=opp:indep_v7 evolved=opp:evolved evolved_tc=opp:evolved_tc v6=opp:v6
```

```bash
python crossfield/robustness.py
```

```bash
python crossfield/test_econ.py
```

```bash
python crossfield/exp_mirror.py
```

```bash
python crossfield/xfield.py 800 --seed=2 ref=opp:evolved cand=file:fusion.py+sym:-1
```

`ship.py` builds `bot.py` and runs every acceptance check. The `xfield.py` runs
reproduce the headline table and test any `FLAGS`, `ECON_GENOME` or
`ROUTE_PARAMS` override; `robustness.py` regenerates the interface matrix for
every branch's bot. `test_econ.py` proves the port and the fused bot are
identical to the research bot, and `exp_mirror.py` reproduces the copy-detection
negative result.

`crossfield/` holds the other branches' bots (`bots/`), the independent field
(`newfield.py`) and the research population (`research/`, with `configs.json`),
copied so that this branch can reproduce everything without checking any other
branch out. Main's own suites on the fixed `mybot.py`:
- **Pass:** `test_engine` (50 checks), `test_tracker` (exact except the same 25
  ambiguous cooldowns of 3,200), `test_guards`, `test_determinism`,
  `test_timing`, `test_amnesia`, `audit` (the bot unflagged), and `diag_seat`
  (1.50 per seat).
- **`test_robust`:** same as unmodified `main`, slightly better on the defaults
  (2.60 vs 2.55) and on four of five rule flips. It still flags one row:
  `frozen_stay_counts = True` (1.96; 1.99 on unmodified `main`). That rule is a
  counterfactual the organisers ruled out.
- **Not run:** `test_gpuenv` (needs torch, not installed here), and the
  strength-only `test_transfer`, `test_fields` and `test_oppmodel`, which the
  cross-author field supersedes.
