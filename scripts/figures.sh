#!/usr/bin/env bash
# Draw every figure the manuscript includes.
#
# The list is the manuscript's own \includegraphics, exactly as tools/sync_captions.py reads it,
# so a figure cannot be drawn that nothing uses and cannot be used that nothing draws. It used to
# be a hard-coded four names here and the same four names again in sync_captions.py; between them
# they drew fig4_choices for a paper that did not include it and skipped nothing that it did.
#
# Panels carry only their letter; what a panel argues belongs in the caption, which is written by
# hand in the manuscript. Numbers in a caption are macros, and checks/paper.py fails if a literal
# in one duplicates a value a macro already defines.
#
#   scripts/figures.sh              redraw
#   FIGURES_CHECK=1 scripts/figures.sh   report stale figures, write nothing (exit 1 if any)
#
# _style.save() renders to a buffer and compares bytes, and matplotlib's PDF output is
# byte-identical for identical input once CreationDate is stripped -- so under FIGURES_CHECK
# "stale" means the data behind a figure moved and the PDF on disk did not.
set -u; cd "$(dirname "$0")/.."

STALE=0

for figure in $(grep -o 'artifacts/figures/[a-z0-9_]*\.pdf' paper_rsc.tex \
                | sed 's|.*/||; s|\.pdf$||' | sort -u); do
  [ -f "figures/${figure}.py" ] || continue      # hand-drawn, nothing to run
  out=$(./.venv/bin/python -W ignore "figures/${figure}.py" 2>&1) || { echo "!!! ${figure} failed"; echo "$out"; exit 1; }
  echo "$out"
  case "$out" in *"stale artifacts/figures"*) STALE=$((STALE + 1));; esac
done

if [ "${FIGURES_CHECK:-}" ] && [ "$STALE" -gt 0 ]; then
  echo "$STALE figure(s) differ from what the checks say now; run scripts/figures.sh"
  exit 1
fi
