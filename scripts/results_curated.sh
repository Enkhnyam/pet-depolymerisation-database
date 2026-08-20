#!/usr/bin/env bash
# The 24-paper benchmark: the curated answer key, how the metric grader behaves on it, how the
# extraction models score, and how far each judge agrees with the metric.
#
# No human labels are involved here -- this is grader against grader on papers we curated.
#
#   scripts/results_curated.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  curated/answer_key.py \
  curated/faults.py \
  curated/consistency.py \
  curated/extractions.py \
  curated/penalties.py \
  curated/thresholds.py \
  curated/matching.py \
  curated/catalysts.py \
  curated/errors.py \
  curated/matrix.py \
  curated/field_types.py
