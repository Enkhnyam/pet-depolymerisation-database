#!/usr/bin/env bash
# Every check, in the order the paper uses them. Takes a few minutes: nothing is cached, so each
# score is recomputed against the curated table as it stands now.
#
#   scripts/results_all.sh              print to the terminal
#   scripts/results_all.sh > out.txt    keep a copy
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python -W ignore checks/run.py
