#!/usr/bin/env bash
# The 447-paper database: where the corpus came from, what the extraction produced, what the
# judge said about it, and whether the records point at text that exists.
#
# There is no curated answer key for this corpus, which is the point of the project.
#
#   scripts/results_database.sh
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py \
  database/corpus.py \
  database/verdicts.py \
  database/provenance.py \
  database/chemistry.py
