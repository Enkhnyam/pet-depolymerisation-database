#!/usr/bin/env bash
# Build the adjudication worklist for a chemist.
#
# 120 records from the 24 curated papers, stratified over the four grader cells. It runs there,
# not on the database, because the metric grader has no verdict without a curated answer key and
# comparing the two graders is the point. The two judge-flagged cells are taken whole; the two
# large cells are sampled and reweighted.
#
# The page shows each record with its source text and hides what the judge said.
#
#   scripts/build_adjudication.sh
set -u; cd "$(dirname "$0")/.."

./.venv/bin/python -W ignore checks/run.py human/worklist.py
./.venv/bin/python -W ignore tools/build_adjudication.py
