#!/usr/bin/env bash
# Grading campaign 2: Apex and Zenith graded on the same games.
#
# The same 8 tasks (map, seats, human-like line-up, token, interface) for both,
# every other turn graded, 4 samples per candidate. Apex and Zenith run their own
# searches inside every rollout, so this is slow: about 15 minutes per bot on 4 cores.
set -e
cd "$(dirname "$0")/../../.."
G=zenith/grader/grade.py
R=zenith/grader/runs
for B in apex zenith; do
  python3 $G batch 8 --focus gen:$B --mode humans --seed 201 --samples 4 --stride 2 --out $R/${B}_humans.jsonl > $R/${B}_humans.log 2>&1
  gzip -9 -f $R/${B}_humans.jsonl
done
python3 $G analyze $R/apex_humans.jsonl.gz $R/zenith_humans.jsonl.gz --top 10 > $R/campaign2_analysis.txt
