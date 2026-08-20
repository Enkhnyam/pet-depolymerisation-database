#!/usr/bin/env bash
# The 24-paper benchmark: the curated answer key, how the extraction models score against it, how
# the metric grader behaves, and how far each judge agrees with the metric.
#
# No human labels are involved here -- this is grader against grader on papers we curated.
#
#   scripts/results_curated.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  curated/answer_key.py \
  curated/extractions.py \
  curated/thresholds.py \
  curated/matching.py \
  curated/catalysts.py \
  curated/errors.py \
  curated/matrix.py \
  curated/field_types.py \
  curated/shots.py \
  curated/source_tracking.py
