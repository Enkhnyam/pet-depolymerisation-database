#!/usr/bin/env bash
# Draw every figure the manuscript includes, and print each one's caption.
#
# The list is the manuscript's own \includegraphics, exactly as tools/sync_captions.py reads it,
# so a figure cannot be drawn that nothing uses and cannot be used that nothing draws. It used to
# be a hard-coded four names here and the same four names again in sync_captions.py; between them
# they drew fig4_choices for a paper that did not include it and skipped nothing that it did.
#
# Panels carry only their letter: what a panel argues belongs in the caption, where it can be
# said properly. The captions are generated from the same checks as the panels, so a number in
# a caption cannot drift from the number in the figure.
#
#   scripts/figures.sh
set -u; cd "$(dirname "$0")/.."

for figure in $(grep -o 'artifacts/figures/[a-z0-9_]*\.pdf' paper_rsc.tex \
                | sed 's|.*/||; s|\.pdf$||' | sort -u); do
  [ -f "figures/${figure}.py" ] || continue      # hand-drawn, nothing to run
  echo "=============================================================================="
  ./.venv/bin/python -W ignore "figures/${figure}.py" || echo "!!! ${figure} failed"
done
