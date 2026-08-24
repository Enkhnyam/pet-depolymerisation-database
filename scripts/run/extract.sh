#!/usr/bin/env bash
# Run an extraction. Bills Azure for the luna configs; the oss configs are unmetered.
#
# Resumable: a paper already in the run's extractions/ is skipped, so an interrupted run costs
# only what it had not reached, and enlarging the corpus costs the new papers. Pass
# resume: false in harness_params to force the whole corpus again.
#
#   CONFIG=mass_luna_1shot CONFIRM=1 scripts/run/extract.sh   the 1,027-paper database, 1 shot
#   CONFIRM=1 scripts/run/extract.sh                          the same corpus at 4 shots
#   CONFIG=extract_luna CONFIRM=1 scripts/run/extract.sh      the 24-paper benchmark
# pipefail: the run is piped into tee, and without it the pipeline reports tee's exit
# status, so a crashed run looks like a successful one to any caller.
set -u; set -o pipefail; cd "$(dirname "$0")/../.."

CONFIG="${CONFIG:-mass_luna}"
if [ "${CONFIRM:-}" != "1" ]; then
  echo "Extraction bills Azure (resumable: papers already done are skipped)."
  echo "  CONFIG=$CONFIG CONFIRM=1 $0"
  exit 1
fi

mkdir -p logs
exec ./.venv/bin/python -W ignore -u cli/run.py extract \
  --config "configs/extract/$CONFIG.yaml" 2>&1 | tee -a "logs/$CONFIG.log"
