#!/usr/bin/env bash
# Serve the provenance page: bundle -> check -> macro -> manuscript and figures, with buttons
# that run the real checks.
#
# Every number on the page is read off disk when the page is requested, so it cannot disagree
# with artifacts/paper_numbers.tex or paper_rsc.tex. It is served rather than written to a file
# because checks/run.py takes minutes and the output has to arrive while it runs.
#
#   scripts/dashboard.sh              http://127.0.0.1:8000
#   scripts/dashboard.sh --port 9000
set -u; cd "$(dirname "$0")/.."
exec ./.venv/bin/python tools/dashboard.py "$@"
