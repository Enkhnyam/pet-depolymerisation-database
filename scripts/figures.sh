#!/usr/bin/env bash
# Draw the paper's figures into artifacts/figures/.
#
# Each module imports its numbers from the check that prints them, so a panel and
# scripts/checks.sh cannot disagree. Nothing is recomputed for a plot.
#
#   scripts/figures.sh                    all of them
#   scripts/figures.sh fig2_chemistry.py  just one
set -u; cd "$(dirname "$0")/.."

MODULES="${*:-$(ls figures/fig*.py | xargs -n1 basename)}"
for module in $MODULES; do
  ./.venv/bin/python -W ignore "figures/$module" || echo "!!! $module FAILED"
done
