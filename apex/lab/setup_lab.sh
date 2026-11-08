#!/usr/bin/env bash
# Recreate the measurement lab used to develop Apex.
#
# The strength numbers in apex/README.md were measured on a field that lives on
# other branches: the cross-branch field (crossfield/: main's v7, the independent
# v7, the evolved planner and its research population, the fused bot.py) from
# claude/eager-cannon-vq1vca, plus the 45 opponents in opponents/ from combined.
# This script assembles exactly that, pinned to the commits that were measured,
# in a separate git worktree, and copies Apex and the lab tools into it.
#
#   bash apex/lab/setup_lab.sh [lab-dir]          (default: ../apex-lab)
#
# Then, inside the lab:
#   python zarena.py 600 h2h   --seed=11 evolved=opp:evolved apex=file:apex/apex_bot.py
#   python zarena.py 600 field --seed=31 --per evolved=opp:evolved apex=file:apex/apex_bot.py
#   python zarena.py 200 trio  --seed=1  evolved=opp:evolved apex=file:apex/apex_bot.py
#   python apex/test_evosim.py 40        # simulator bank vs every public genome
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
LAB=${1:-"$ROOT/../apex-lab"}
CROSSFIELD=d31fff24325abc69cc7d53234be8d1f26f15857b   # claude/eager-cannon-vq1vca
OPPONENTS=45b55f0                                    # combined
git -C "$ROOT" fetch origin claude/eager-cannon-vq1vca combined
git -C "$ROOT" worktree add --detach "$LAB" "$CROSSFIELD"
git -C "$ROOT" archive "$OPPONENTS" opponents | tar -x -C "$LAB"
cp "$ROOT"/apex/lab/*.py "$LAB"/
mkdir -p "$LAB/apex"
cp "$ROOT"/apex/src/*.py "$ROOT"/apex/build.py "$ROOT"/apex/apex_bot.py "$LAB/apex/"
cp "$ROOT"/apex/lab/apex/*.py "$LAB/apex/"
echo "lab ready at $LAB"
