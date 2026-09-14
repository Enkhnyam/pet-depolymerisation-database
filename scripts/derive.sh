#!/usr/bin/env bash
# Regenerate everything the checks produce, in the one order that keeps it consistent.
#
#   1. paper_numbers.py   every quoted number -> artifacts/paper_numbers.tex, plus an artifact hash
#   2. figures.sh         redraw the figures from the same checks
#   3. derivation.py      docs/derivation.md: how each of those numbers is arrived at
#
# A reviewer once found the manuscript irreconcilable -- 5,563 records in the abstract against
# 2,128 in a table whose rows summed to 4,402 -- because numbers were typed by hand and re-typed
# when a run changed. Nothing here is typed. If a number is wrong it is wrong in a check, in one
# place, and every copy of it moves together. That is the whole point of this script.
#
#   scripts/derive.sh            regenerate
#   scripts/derive.sh --check    fail if anything is stale, and change nothing (for CI)
set -u
cd "$(dirname "$0")/.."

PY="./.venv/bin/python -W ignore"

if [ "${1:-}" = "--check" ]; then
  echo "=== numbers ==="
  $PY tools/paper_numbers.py --check || { echo "paper_numbers.tex is stale; run scripts/derive.sh"; exit 1; }
  echo "=== figures ==="
  FIGURES_CHECK=1 ./scripts/figures.sh > /dev/null || {
    echo "a figure PDF is stale; run scripts/derive.sh"; exit 1; }
  echo "=== the derivation report ==="
  $PY tools/derivation.py --check || exit 1
  echo "everything is current"
  exit 0
fi

echo "=== 1/3 regenerating the numbers ==="
$PY tools/paper_numbers.py || exit 1

echo
echo "=== 2/3 redrawing the figures ==="
./scripts/figures.sh > /dev/null || exit 1
ls artifacts/figures_pdf/*.pdf | sed 's/^/  /'

echo
echo "=== 3/3 how every number is arrived at ==="
$PY tools/derivation.py || exit 1

echo
grep -m1 "artifact set" artifacts/paper_numbers.tex | sed 's/^% */these numbers describe /'
