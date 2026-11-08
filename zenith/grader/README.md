# The move grader

`movegrade.py` grades every decision a Zone Rush seat makes by **how it changed that
seat's chance of finishing above its rivals**, measured to the end of the game. It is
the Zone Rush equivalent of a chess engine's game review, and it is what Zenith was
built with (see `../README.md`).

## What a grade means

For a decision at turn *t*, every distinct legal action *a* (a move into an occupied
cell plays exactly like STAY, so it is not counted twice) gets a value

> **Q(a)** = expected pairwise result, 0 to 3, if the seat plays *a* now and every bot at
> the table, the seat's own continuation included, then plays on to turn 80.

The unit is the Round 1 unit: pairwise wins out of 3 (beating all three rivals is 3,
losing to all three is 0). **Win share** is Q / 3.

**How Q is measured.** The grader forks the whole process, engine and the four live
bots with their module memory, once per candidate action and per sample. Each child
forces its action, then lets the game run to the end with real bots. Sample 0 is the
exact future. Samples 1 to K−1 add a little noise to every seat after the decision
(each bot plays a random legal action with probability `eps`, default 4% per turn), so
a move is not rated on one butterfly-effect future. All candidates of a sample share
one noise stream (common random numbers), so the *differences* between candidates are
far less noisy than the values. The score of one finished game is the **soft**
pairwise result

    sum over rivals r of 1 / (1 + exp(-(S_me - S_r) / 60))

so a 5-point win and a 500-point win differ while a decided game stays decided.

**Loss**, the cost of the move played, is `Q(best) − Q(played)`, debiased:

* *Cross-fitting.* Choosing the best action and measuring its advantage on the same
  samples overstates the loss, because it is a maximum of noisy estimates. (The same
  trap made this repository's tuner select luck; see EXPLAINED.md section 8.2.)
  So the samples are split in two folds: the best action is chosen on one fold and
  its advantage measured on the other, both ways round. On the first 2,217 graded
  moves this cut the average measured loss from 0.135 (naive) to 0.031 PW per move
  before clipping.
* *Significance.* A move is only called a Mistake or a Blunder if its loss exceeds
  two standard errors of the paired difference. Otherwise it is at most an
  Inaccuracy.

## Categories

| category | symbol | rule (loss in pairwise wins out of 3) |
|---|---|---|
| Brilliant | !! | the only good move: every alternative is worse by ≥ 0.30 (significantly), *and* it gives something up now (a shield, progress walked away from, or fewer points this turn than an alternative) |
| Great | ! | the only good move, by ≥ 0.30 |
| Best | | loss ≤ 0.02 |
| Excellent | | loss ≤ 0.06 |
| Good | | loss ≤ 0.15 |
| Inaccuracy | ?! | loss ≤ 0.30, or larger but within the noise |
| Mistake | ? | loss ≤ 0.60, significant |
| Blunder | ?? | loss > 0.60, significant |
| Forced | | one effective choice (frozen, or every move blocked) |

**Accuracy** per move is the lichess / chess.com curve applied to win-share percentage
points lost: `103.1668 · exp(−0.04354 · L) − 3.1669`, clipped to 0–100, averaged over
a game.

**Critical-move accuracy** averages only the moves that mattered: those whose
candidates' values spread by at least 0.15 PW. Plain accuracy flatters a lost game. Once
a game is decided every move is worth the same, so a player who only ever pressed STAY
scored 98.2% accuracy in a test game, with 158 points and last place. On its five
critical moves (the opening, where the game was lost) it scored 72.4%. Read critical
accuracy and total loss first.

## Grading a human

A recorded game (`zenith/play.py` writes one per game) is replayed turn by turn. The
bots see every turn exactly as they did, so their memory follows the real game. At each
of your decisions the table is forked as above. After the forced move, your seat is
played by a reference engine (`--continuation`, default Zenith), the way a chess
engine grades a human: "how good was this move, if a strong player finishes the game
from here?"

## Commands

```bash
# one game, one seat, every move printed
python zenith/grader/grade.py game --lineup apex,fused,evolved,v7 --seat 1 --samples 6

# one bot over many games, in parallel; --store keeps positions for distill.py
python zenith/grader/grade.py batch 64 --focus gen:evolved --mode humans --samples 6 --store --out g.jsonl

# a recorded game
python zenith/grader/grade.py review zenith/games/<file>.json

# where the loss concentrates: phase, action kind, cell, progress, line-up, costliest moves
python zenith/grader/grade.py analyze g.jsonl
```

Cost: one graded decision is (candidates × samples) full rollouts. For a table of fast
bots that is about 1 s per decision on one core; with Apex or Zenith at the table, whose
searches run inside the rollouts, it is 5–10 times that.
