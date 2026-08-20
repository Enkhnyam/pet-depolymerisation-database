#!/usr/bin/env bash
# Does showing the model more worked examples help? Sweeps n_shots 0..6, three runs each, on
# luna over the 24 curated papers.
#
# 21 runs, about $8 on Azure. Safe to re-run: a condition that already finished is skipped, so an
# interrupted sweep resumes where it stopped.
#
# n_shots caps at 6: seven papers are open-licensed enough to redistribute as examples, minus the
# held-out target.
#
#   CONFIRM=1 scripts/ablation_shots.sh          the full sweep
#   LIMIT=3 CONFIRM=1 scripts/ablation_shots.sh  three papers per run, to test the wiring first
set -u; cd "$(dirname "$0")/../.."

if [ "${CONFIRM:-}" != "1" ]; then
  echo "This bills Azure: 21 runs, about \$8."
  echo "  CONFIRM=1 $0"
  echo "  LIMIT=3 CONFIRM=1 $0     cheap wiring test first"
  exit 1
fi

if [ -n "${LIMIT:-}" ] && [ -d "artifacts/runs/shots_luna" ]; then
  echo "artifacts/runs/shots_luna already holds runs; a LIMIT run would be mistaken for a"
  echo "finished condition and skipped later. Remove it first."; exit 1
fi

mkdir -p logs
./.venv/bin/python -W ignore -u cli/ablation.py \
  --config shots_luna.yaml --shots 0 1 2 3 4 5 6 --repeats 3 \
  ${LIMIT:+--limit $LIMIT} 2>&1 | tee -a logs/ablation_shots.log

echo
./.venv/bin/python -W ignore checks/run.py curated/shots.py
