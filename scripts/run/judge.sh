#!/usr/bin/env bash
# Judge an extraction. Free on the RWTH endpoint, but slow: the 447-paper database takes about
# three hours. It asks first for that reason, not for cost.
#
# Resumable: a paper that already has a verdict is skipped, so interrupting is safe.
#
#   CONFIRM=1 scripts/run/judge.sh                            the database
#   CONFIG=judge_oss_on_luna CONFIRM=1 scripts/run/judge.sh   a matrix cell
# pipefail: the run is piped into tee, and without it the pipeline reports tee's exit
# status, so a crashed run looks like a successful one to any caller.
set -u; set -o pipefail; cd "$(dirname "$0")/../.."

CONFIG="${CONFIG:-mass_oss}"

if [ ! -f "configs/judge/$CONFIG.yaml" ]; then
  echo "no config at configs/judge/$CONFIG.yaml"; exit 1
fi

if [ "${CONFIRM:-}" != "1" ]; then
  echo "Judging $CONFIG is free but takes hours. It resumes, so interrupting is safe."
  echo "  CONFIG=$CONFIG CONFIRM=1 $0"
  exit 1
fi

mkdir -p logs
exec ./.venv/bin/python -W ignore -u cli/judge.py \
  --config "configs/judge/$CONFIG.yaml" 2>&1 | tee -a "logs/$CONFIG.log"
