#!/usr/bin/env bash
# Every judge model against every extraction. With seven models that is 49 cells, and the point is
# the heatmap: how much each judge agrees with the metric grader, and at what cost.
#
# Run the extractions first; a cell whose extraction is missing is skipped with a note.
# Safe to re-run: finished papers inside a run are skipped rather than re-judged.
#
#   FREE=1 scripts/matrix_judges.sh        free judges on free extractions (9 cells)
#   CONFIRM=1 scripts/matrix_judges.sh     all 49 cells, including the paid Azure judges
set -u; cd "$(dirname "$0")/.."

FREE_MODELS="oss mistral"
PAID_MODELS="sol luna terra mini mlarge"

if [ -n "${JUDGES_ONLY:-}${TARGETS_ONLY:-}" ]; then
  JUDGES="${JUDGES_ONLY:-$FREE_MODELS}"; TARGETS="${TARGETS_ONLY:-$FREE_MODELS}"
elif [ "${FREE:-}" = "1" ]; then
  JUDGES="$FREE_MODELS"; TARGETS="$FREE_MODELS"
elif [ "${CONFIRM:-}" = "1" ]; then
  JUDGES="$FREE_MODELS $PAID_MODELS"; TARGETS="$FREE_MODELS $PAID_MODELS"
else
  echo "The Azure judges are billed. Choose one:"
  echo "  FREE=1 $0        4 free cells"
  echo "  CONFIRM=1 $0     all 49 cells"
  exit 1
fi

mkdir -p logs
for j in $JUDGES; do
  for t in $TARGETS; do
    if [ ! -d "artifacts/runs/extract_$t/extract_${t}_n4_r1/extractions" ]; then
      echo "--- skip judge_${j}_on_${t}: no extraction for $t yet"
      continue
    fi
    echo "=== judge_${j}_on_${t} ($(date +%H:%M)) ==="
    uv run python cli/judge.py --config "configs/judge/judge_${j}_on_${t}.yaml" \
        >> "logs/judge_${j}_on_${t}.log" 2>&1 \
      || echo "!!! judge_${j}_on_${t} FAILED — see logs/judge_${j}_on_${t}.log"
  done
done
echo "=== finished $(date +%H:%M) ==="
