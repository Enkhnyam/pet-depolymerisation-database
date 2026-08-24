#!/usr/bin/env bash
# Extract the 1,027-paper corpus at one shot, then judge it. Meant to be started and slept on.
#
#   1. extract  mass_luna_1shot   ~3 h, bills Azure about $8.40
#   2. judge    mass_oss_1shot    ~7 h, free (the RWTH endpoint is unmetered)
#
# It stops there. checks/_setup.py still points DATABASE at the old mass_luna run, so the figures
# and checks keep reporting that until you repoint them by hand -- deliberately, so a run becomes
# "the database" only once you have looked at it.
#
# Both stages now survive a single bad paper: a paper whose call fails is recorded and stepped
# over rather than aborting the run, and both write per paper, so nothing already done is lost.
# That is what makes this safe to leave unattended -- before it, one rate limit in hour three
# threw away everything.
#
# Both stages resume. If this dies overnight, running it again costs only what it had not reached.
#
#   CONFIRM=1 scripts/run/overnight_1shot.sh
set -u
cd "$(dirname "$0")/../.."

EXTRACT_CONFIG="mass_luna_1shot"
JUDGE_CONFIG="mass_oss_1shot"
EXTRACT_RUN="artifacts/runs/$EXTRACT_CONFIG"
JUDGE_RUN="artifacts/runs/$JUDGE_CONFIG/$JUDGE_CONFIG"
CORPUS="artifacts/data/corpus_markdown"
LOG="logs/overnight_1shot.log"
mkdir -p logs

say() { echo "[$(date +%H:%M)] $*" | tee -a "$LOG"; }

if [ "${CONFIRM:-}" != "1" ]; then
  echo "Extracts $(ls $CORPUS/*.md 2>/dev/null | wc -l) papers (bills Azure ~\$8.40), then judges them (free)."
  echo "Expect it to run most of the night."
  echo "  CONFIRM=1 $0"
  exit 1
fi

# A resumed extraction with a complete bundle already in place does no work and reports success,
# which overnight is indistinguishable from having run. Say so instead.
DONE=$(ls "$EXTRACT_RUN"/extractions/*.json 2>/dev/null | wc -l)
CORPUS_N=$(ls "$CORPUS"/*.md 2>/dev/null | wc -l)
if [ "$DONE" -gt 0 ]; then
  say "$EXTRACT_RUN already holds $DONE extractions of $CORPUS_N papers."
  say "A fresh run would resume, not re-extract. Move it aside first, or let it resume knowingly:"
  say "  mv $EXTRACT_RUN ${EXTRACT_RUN}_prev"
  [ "${RESUME:-}" = "1" ] || exit 1
  say "RESUME=1 given; continuing with whatever is missing"
fi

say "=== 1/2 extracting $EXTRACT_CONFIG ($CORPUS_N papers) ==="
CONFIG="$EXTRACT_CONFIG" CONFIRM=1 ./scripts/run/extract.sh >> "$LOG" 2>&1 \
  || { say "extraction failed; see $LOG"; exit 1; }

EXTRACTED=$(ls "$EXTRACT_RUN"/extractions/*.json 2>/dev/null | wc -l)
say "extractions on disk: $EXTRACTED / $CORPUS_N"

# Judging a mostly-empty extraction wastes the night, so check before starting the long half.
if [ "$EXTRACTED" -lt $((CORPUS_N * 9 / 10)) ]; then
  say "fewer than 90% of papers extracted; stopping rather than judging a broken run"
  exit 1
fi

say "=== 2/2 judging $JUDGE_CONFIG ==="
CONFIG="$JUDGE_CONFIG" CONFIRM=1 ./scripts/run/judge.sh >> "$LOG" 2>&1 \
  || { say "judging failed; see $LOG"; exit 1; }

say "=== for the morning ==="
say "extractions  $(ls "$EXTRACT_RUN"/extractions/*.json 2>/dev/null | wc -l)"
say "verdicts     $(ls "$JUDGE_RUN"/verdicts/*.json 2>/dev/null | wc -l)"
for meta in "$EXTRACT_RUN/run_meta.json" "$JUDGE_RUN/judge_meta.json"; do
  [ -f "$meta" ] && ./.venv/bin/python -c "
import json,sys
m=json.load(open('$meta'))
keep=('n_papers','n_records','cost_usd','parse_failed_papers','parse_failed_records','skipped_papers')
print('  $meta')
for k in keep:
    if k in m: print(f'    {k:22s} {m[k]}')
" 2>&1 | tee -a "$LOG"
done
say "papers that failed and were skipped are listed above; rerunning this script retries only those"
say "checks/_setup.py still points DATABASE at mass_luna -- repoint it when you are happy"
say "done"
