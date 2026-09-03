#!/usr/bin/env bash
# Ingest the chemists' adjudications and score the two graders against them.
#
# The exports come out of the adjudication page one per chemist, overlapping and disagreeing in
# places. The ingest verifies each decision against the record it names, resolves the overlaps,
# and works out what each answered record stands for; the check turns that into precision,
# recall, F1, kappa and McNemar.
#
#   scripts/adjudication.sh
set -eu; cd "$(dirname "$0")/.."

./.venv/bin/python -W ignore cli/ingest_adjudications.py \
  --from karim=artifacts/gold/decisions/adjudication_karim.json \
  --from mohammad=artifacts/gold/decisions/adjudication_mohammad.json

./.venv/bin/python -W ignore checks/run.py human/adjudicated.py
