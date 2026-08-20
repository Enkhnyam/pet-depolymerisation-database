#!/usr/bin/env bash
# The 48 records two chemists adjudicated.
#
# The headline is human/significance.py: the two graders agree on 44 of the 48, leaving four
# informative pairs, and four cannot separate them however they fall. It also prints what a
# conclusive round would cost and how large the pool for one is.
#
#   scripts/results_human.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  human/composition.py \
  human/scorecard.py \
  human/significance.py \
  human/disagreements.py \
  human/catalyst_gate.py \
  human/growth.py
