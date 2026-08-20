#!/usr/bin/env bash
# What the human labels do and do not establish: each grader against the chemists, whether the
# difference is significant, and how much more adjudication a conclusive answer would need.
#
# Read judge/power.py last -- it is the one that says what to do next.
#
#   scripts/results_evidence.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  golden_set/composition.py \
  judge/scorecard.py \
  judge/significance.py \
  judge/power.py \
  golden_set/disagreements.py
