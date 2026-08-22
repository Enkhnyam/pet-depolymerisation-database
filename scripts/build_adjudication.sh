#!/usr/bin/env bash
# Build the adjudication worklist for a chemist.
#
# 120 records drawn from the database, stratified: half the judge flagged, half it accepted. That
# split is what lets precision and recall both be estimated and weighted back to all 2,128
# records -- a random sample would have spent most of the budget on records the judge accepts.
#
# The page shows each record with its source text and hides what the judge said.
#
#   scripts/build_adjudication.sh
set -u; cd "$(dirname "$0")/.."

./.venv/bin/python -W ignore checks/run.py human/worklist.py
./.venv/bin/python -W ignore tools/build_adjudication.py
