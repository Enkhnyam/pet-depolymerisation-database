#!/usr/bin/env bash
# Print the numbers. Every check names the bundles it reads before its results, so any figure in
# the paper can be traced back to the files behind it.
#
#   scripts/checks.sh                  every check
#   scripts/checks.sh curated          one group
#   scripts/checks.sh database human   several
#
# Groups: curated (the 24-paper benchmark), database (the 447-paper corpus),
#         human (the 48 adjudicated records).
set -u; cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  exec ./.venv/bin/python -W ignore checks/run.py
fi

CHOSEN=""
for group in "$@"; do
  if [ ! -d "checks/$group" ]; then
    echo "no such group: $group   (curated, database, human)"; exit 1
  fi
  CHOSEN="$CHOSEN $(ls checks/$group/*.py | sed 's|checks/||' | tr '\n' ' ')"
done
exec ./.venv/bin/python -W ignore checks/run.py $CHOSEN
