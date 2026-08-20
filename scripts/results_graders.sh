#!/usr/bin/env bash
# Judge against metric: the agreement matrix that licenses reading a judge's pass rate as a
# quality estimate, plus where the two graders disagree and why.
#
#   scripts/results_graders.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  judge/matrix.py \
  judge/field_types.py \
  metric/error_taxonomy.py \
  metric/catalyst_names.py
