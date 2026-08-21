#!/usr/bin/env bash
# Draw every figure, and print each one's caption so it can be pasted into the paper.
#
# Panels carry only their letter: what a panel argues belongs in the caption, where it can be
# said properly. The captions are generated from the same checks as the panels, so a number in
# a caption cannot drift from the number in the figure.
#
#   scripts/figures.sh
set -u; cd "$(dirname "$0")/.."

for figure in fig1_database fig2_chemistry fig3_graders fig4_choices; do
  echo "=============================================================================="
  ./.venv/bin/python -W ignore "figures/${figure}.py" || echo "!!! ${figure} failed"
done
