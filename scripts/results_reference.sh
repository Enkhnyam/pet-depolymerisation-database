#!/usr/bin/env bash
# The curated answer key everything else is measured against: its size, its faults, whether its
# numbers are internally consistent, and how the metric grader behaves on it.
#
#   scripts/results_reference.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  ground_truth/dataset.py \
  ground_truth/curation_quality.py \
  ground_truth/outcome_identity.py \
  metric/scores.py \
  metric/threshold_sensitivity.py \
  golden_set/growth.py
