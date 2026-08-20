#!/usr/bin/env bash
# Does requiring the model to cite its source chunks change what it extracts? Two arms differing
# in one flag, three runs each, at n_shots=4.
#
# 6 runs, about $3 on Azure. Safe to re-run: finished conditions are skipped.
#
#   CONFIRM=1 scripts/ablation_source.sh
#   LIMIT=3 CONFIRM=1 scripts/ablation_source.sh   cheap wiring test first
set -u; cd "$(dirname "$0")/.."

if [ "${CONFIRM:-}" != "1" ]; then
  echo "This bills Azure: 6 runs, about \$3."
  echo "  CONFIRM=1 $0"
  echo "  LIMIT=3 CONFIRM=1 $0     cheap wiring test first"
  exit 1
fi

if [ -n "${LIMIT:-}" ] && [ -d "artifacts/runs/src_luna_on" ]; then
  echo "artifacts/runs/src_luna_on already holds runs; a LIMIT run would be mistaken for a"
  echo "finished condition and skipped later. Remove it first."; exit 1
fi
if [ -n "${LIMIT:-}" ] && [ -d "artifacts/runs/src_luna_off" ]; then
  echo "artifacts/runs/src_luna_off already holds runs; a LIMIT run would be mistaken for a"
  echo "finished condition and skipped later. Remove it first."; exit 1
fi

mkdir -p logs
for arm in on off; do
  echo "=== src_luna_$arm ($(date +%H:%M)) ==="
  # one --shots value, so the sweep is over repeats alone
  ./.venv/bin/python -W ignore -u cli/ablation.py \
    --config "src_luna_$arm.yaml" --shots 4 --repeats 3 \
    ${LIMIT:+--limit $LIMIT} 2>&1 | tee -a "logs/ablation_src_$arm.log"
done

echo
./.venv/bin/python -W ignore checks/run.py curated/source_tracking.py
