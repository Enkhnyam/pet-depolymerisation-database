#!/usr/bin/env bash
# Draw every figure.
#
# The list is figures/*.py, one module per figure. It used to be the manuscript's own
# \includegraphics, so that a figure could not be drawn that nothing used -- a real guard when
# the manuscript lived here, and impossible now that it does not. One module per figure is the
# same guarantee from the other side: nothing is drawn that has no source, and nothing has source
# that is not drawn.
#
# Panels carry only their letter; what a panel argues belongs in its caption, which is written by
# hand alongside the manuscript. Numbers in a caption come from tools/paper_numbers.py.
#
#   scripts/figures.sh              redraw
#   FIGURES_CHECK=1 scripts/figures.sh   report stale figures, write nothing (exit 1 if any)
#
# _style.save() renders to a buffer and compares bytes, and matplotlib's PDF output is
# byte-identical for identical input once CreationDate is stripped -- so under FIGURES_CHECK
# "stale" means the data behind a figure moved and the PDF on disk did not.
set -u; cd "$(dirname "$0")/.."

STALE=0

for figure in $(ls figures/fig_*.py | sed 's|figures/||; s|\.py$||' | sort); do
  out=$(./.venv/bin/python -W ignore "figures/${figure}.py" 2>&1) || { echo "!!! ${figure} failed"; echo "$out"; exit 1; }
  echo "$out"
  case "$out" in *"stale artifacts/figures_pdf"*) STALE=$((STALE + 1));; esac
done

if [ "${FIGURES_CHECK:-}" ] && [ "$STALE" -gt 0 ]; then
  echo "$STALE figure(s) differ from what the checks say now; run scripts/figures.sh"
  exit 1
fi
