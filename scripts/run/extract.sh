#!/usr/bin/env bash
# Run an extraction. Bills Azure for the luna configs; the oss configs are unmetered.
#
# Not resumable: every paper is re-extracted from the start, so an interrupted run costs twice.
#
#   CONFIRM=1 scripts/run/extract.sh                        the 447-paper database
#   CONFIG=extract_luna CONFIRM=1 scripts/run/extract.sh    the 24-paper benchmark
set -u; cd "$(dirname "$0")/../.."

CONFIG="${CONFIG:-mass_luna}"
if [ "${CONFIRM:-}" != "1" ]; then
  echo "Extraction is not resumable and bills Azure."
  echo "  CONFIG=$CONFIG CONFIRM=1 $0"
  exit 1
fi

mkdir -p logs
exec ./.venv/bin/python -W ignore -u cli/run.py extract \
  --config "configs/extract/$CONFIG.yaml" 2>&1 | tee -a "logs/$CONFIG.log"
