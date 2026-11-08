#!/usr/bin/env bash
# Zenith's acceptance benchmark: does it beat every previous generation, and the
# human-like players that beat Apex?
#
#   bash zenith/lab/benchmark.sh [games] [seed]
#
# trio:X   Zenith against three copies of X. X against itself scores exactly 1.50
#          of 3 by symmetry, so anything above 1.50 means Zenith beats X.
# gens     three opponents drawn from the previous generations (v7, indep_v7,
#          evolved, fused, apex); the head-to-head table is Zenith's credit
#          against each generation inside mixed line-ups.
# humans   three human-like exploiters (zenith/lab/humanlike).
# field    three drawn group-first from every author group, the generations and
#          the human-like players.
# Every mode is paired: Apex plays the identical games in the same seat.
set -e
cd "$(dirname "$0")/../.."
N=${1:-200}
S=${2:-1000}
A=zenith/lab/genarena.py
for X in v7 indep_v7 evolved fused apex; do
  echo "=== trio:$X"
  python3 $A "$N" "trio:$X" --seed=$S apex=gen:apex zenith=gen:zenith | sed -n 2,5p
done
for M in gens humans field; do
  echo "=== $M"
  python3 $A "$N" "$M" --seed=$S --per apex=gen:apex zenith=gen:zenith
done
