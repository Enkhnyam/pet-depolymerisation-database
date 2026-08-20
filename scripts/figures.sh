#!/usr/bin/env bash
# Draw the paper's figures. Each module imports its numbers from the check that prints them, so a
# panel and `scripts/results_*.sh` cannot disagree -- nothing is recomputed for the plot.
#
# Writes PNGs to artifacts/figures/.
#
#   scripts/figures.sh                 all of them
#   scripts/figures.sh quality.py      just one
set -u; cd "$(dirname "$0")/.."

MODULES="${*:-$(ls figures/*.py | grep -v _style | xargs -n1 basename)}"
for module in $MODULES; do
  echo "=== $module ==="
  ./.venv/bin/python -W ignore "figures/$module" || echo "!!! $module FAILED"
done
