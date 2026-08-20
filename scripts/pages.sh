#!/usr/bin/env bash
# Build the reviewable HTML pages into artifacts/.
#
#   scripts/pages.sh            both
#   scripts/pages.sh review     every database record with its verdict and source text
#   scripts/pages.sh adjudicate the grader disagreements, for a chemist to decide
set -u; cd "$(dirname "$0")/.."

WHAT="${1:-both}"

if [ "$WHAT" = "review" ] || [ "$WHAT" = "both" ]; then
  ./.venv/bin/python -W ignore tools/review_database.py \
    --extraction mass_luna --judge mass_oss/mass_oss --corpus corpus_markdown
fi

if [ "$WHAT" = "adjudicate" ] || [ "$WHAT" = "both" ]; then
  ./.venv/bin/python -W ignore tools/build_adjudication.py \
    --extraction "extract_${TARGET:-luna}/extract_${TARGET:-luna}_n4_r1" \
    --judge "judge_${JUDGE:-oss}_on_${TARGET:-luna}/judge_${JUDGE:-oss}_on_${TARGET:-luna}"
fi
