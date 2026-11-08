#!/usr/bin/env bash
# Grading campaign 1: where does the current generation lose value?
#
# The evolved planner (Apex's base plan, and the fused bot.py's) graded on every
# move of 64 games against the human-like players, 6 rollout samples per
# candidate, positions and planner memory stored for distill.py.
# Output: evolved_humans.jsonl.gz (5,120 graded moves). About 40 minutes on 4 cores.
#
# Grading against the previous generations instead (--mode gens) is 5-10 times
# slower, because Apex and v7 run their own searches inside every rollout;
# campaign2.sh does a leaner version of that, every other turn.
set -e
cd "$(dirname "$0")/../../.."
G=zenith/grader/grade.py
R=zenith/grader/runs
python3 $G batch 64 --focus gen:evolved --mode humans --seed 101 --samples 6 --store --out $R/evolved_humans.jsonl > $R/evolved_humans.log 2>&1
gzip -9 -f $R/evolved_humans.jsonl
