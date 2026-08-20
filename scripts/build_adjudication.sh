#!/usr/bin/env bash
# Collect the records the two graders disagree about, for a chemist to adjudicate.
#
# Only disagreements are worth labelling: each one becomes an informative McNemar pair the moment
# a human decides it, because one grader must be the one that matched. checks/judge/power.py says
# how many are needed.
#
# Needs a curated answer key, so it runs on a benchmark extraction, not the mass corpus.
#
#   scripts/build_adjudication.sh                          the shipped pair, evaluable records
#   ALL=1 scripts/build_adjudication.sh                    include records the reference lacks
#   JUDGE=luna TARGET=terra scripts/build_adjudication.sh  any other cell
set -u; cd "$(dirname "$0")/.."

JUDGE="${JUDGE:-oss}"
TARGET="${TARGET:-luna}"
EXTRACTION="extract_${TARGET}/extract_${TARGET}_n4_r1"
VERDICTS="judge_${JUDGE}_on_${TARGET}/judge_${JUDGE}_on_${TARGET}"

if [ ! -d "artifacts/runs/$VERDICTS/verdicts" ]; then
  echo "no judge run at artifacts/runs/$VERDICTS"; exit 1
fi

./.venv/bin/python -W ignore tools/build_adjudication.py \
  --extraction "$EXTRACTION" --judge "$VERDICTS" ${ALL:+--all}

echo
echo "how many decisions this needs:"
./.venv/bin/python -W ignore checks/run.py judge/power.py 2>&1 | sed -n '/what it would take/,$p'
