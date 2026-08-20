#!/usr/bin/env bash
# One extraction per model, all against the same 24 papers with the same prompt, shots and seed.
#
# The five Azure models are billed; the two RWTH ones are not. FREE=1 runs only the free ones.
# Safe to re-run: a finished run is skipped rather than repeated.
#
#   FREE=1 scripts/matrix_extractions.sh          # gpt-oss-120b, mistral-small
#   CONFIRM=1 scripts/matrix_extractions.sh       # all seven, including the five Azure models
set -u; cd "$(dirname "$0")/../.."

FREE_MODELS="oss mistral"
PAID_MODELS="sol luna terra mini mlarge"

if [ -n "${ONLY:-}" ]; then
  MODELS="$ONLY"
elif [ "${FREE:-}" = "1" ]; then
  MODELS="$FREE_MODELS"
elif [ "${CONFIRM:-}" = "1" ]; then
  MODELS="$FREE_MODELS $PAID_MODELS"
else
  echo "The Azure models are billed. Choose one:"
  echo "  FREE=1 $0        free RWTH models only"
  echo "  CONFIRM=1 $0     all five, roughly \$12-25 for the two paid ones"
  exit 1
fi

mkdir -p logs
for m in $MODELS; do
  echo "=== extract_$m ($(date +%H:%M)) ==="
  uv run python cli/ablation.py --config "extract_$m.yaml" --shots 4 --repeats 1 \
      >> "logs/extract_$m.log" 2>&1 \
    || echo "!!! extract_$m FAILED — see logs/extract_$m.log"
done
echo "=== finished $(date +%H:%M) ==="
