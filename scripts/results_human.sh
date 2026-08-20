#!/usr/bin/env bash
# The 48 records two chemists adjudicated: how each grader compares with them, whether the
# difference is significant, and what a conclusive comparison would cost.
#
# Read human/power.py last -- it says what to do next, and why the records we hold cannot be
# carried into a new round.
#
#   scripts/results_human.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  human/composition.py \
  human/scorecard.py \
  human/significance.py \
  human/power.py \
  human/disagreements.py \
  human/rescues.py \
  human/catalyst_gate.py \
  human/growth.py
