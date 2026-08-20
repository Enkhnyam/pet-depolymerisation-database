#!/usr/bin/env bash
# Wait for the corpus expansion in the pipeline repo, then extract, judge and redraw.
#
# Extraction resumes, so only papers without a result are sent -- enlarging the corpus costs the
# new papers, not the whole thing. Judging resumes the same way.
#
# Every stage logs to logs/overnight.log and the script stops at the first real failure rather
# than carrying a broken corpus into an expensive stage.
#
#   CONFIRM=1 scripts/run/overnight.sh
set -u
cd "$(dirname "$0")/../.."

PIPELINE="../information-extraction-pipeline-for-polymer-data"
CORPUS="artifacts/data/corpus_markdown"
LOG="logs/overnight.log"
mkdir -p logs

say() { echo "[$(date +%H:%M)] $*" | tee -a "$LOG"; }

if [ "${CONFIRM:-}" != "1" ]; then
  echo "This extracts and judges the enlarged corpus, and bills Azure for the new papers."
  echo "  CONFIRM=1 $0"
  exit 1
fi

BEFORE=$(ls "$CORPUS"/*.md 2>/dev/null | wc -l)
say "corpus starts at $BEFORE papers; waiting for the expansion to finish"

# The expansion runs in the other repo. Wait for its process to leave, with a ceiling so a hung
# download cannot keep this script waiting all night.
WAITED=0
while pgrep -f "expand_corpus.sh" >/dev/null 2>&1; do
  sleep 60
  WAITED=$((WAITED + 1))
  if [ $((WAITED % 30)) -eq 0 ]; then
    say "  still expanding (${WAITED} min), corpus at $(ls "$CORPUS"/*.md 2>/dev/null | wc -l)"
  fi
  if [ "$WAITED" -ge 480 ]; then
    say "expansion still running after 8 hours; going ahead with whatever landed"
    break
  fi
done

AFTER=$(ls "$CORPUS"/*.md 2>/dev/null | wc -l)
say "corpus is now $AFTER papers (was $BEFORE)"

if [ "$AFTER" -le "$BEFORE" ]; then
  say "no new papers arrived; nothing to extract, stopping"
  exit 1
fi

say "=== extracting the new papers ==="
./.venv/bin/python -W ignore -u cli/run.py extract \
  --config configs/extract/mass_luna.yaml >> "$LOG" 2>&1 \
  || { say "extraction failed; see $LOG"; exit 1; }

EXTRACTED=$(ls artifacts/runs/mass_luna/extractions/*.json 2>/dev/null | wc -l)
say "extractions on disk: $EXTRACTED"

say "=== judging ==="
./.venv/bin/python -W ignore -u cli/judge.py \
  --config configs/judge/mass_oss.yaml >> "$LOG" 2>&1 \
  || { say "judging failed; see $LOG"; exit 1; }

say "=== redrawing the figures ==="
./scripts/figures.sh >> "$LOG" 2>&1 || say "a figure failed; see $LOG"

say "=== the numbers, for the morning ==="
./scripts/checks.sh database 2>&1 | tee -a "$LOG" | grep -vE "^\[|^$"

say "done"
