#!/usr/bin/env bash
# Build the adjudication worklist for a chemist.
#
# Records from the 24 curated papers, not from the database: the metric grader has no verdict
# without a curated answer key, and comparing the two graders is the point. Every disagreement is
# taken whole, so is the handful both graders flagged -- those two censuses are what precision
# rests on -- and the records both accepted are sampled and reweighted, which is what recall
# rests on. Built at two sizes; checks/human/precision.py says what each size buys.
#
# The page shows each record with its source text and hides what the judge said.
#
#   scripts/build_adjudication.sh
set -u; cd "$(dirname "$0")/.."

./.venv/bin/python -W ignore checks/run.py human/worklist.py
./.venv/bin/python -W ignore checks/run.py human/precision.py
./.venv/bin/python -W ignore tools/build_adjudication.py --agreements 20
./.venv/bin/python -W ignore tools/build_adjudication.py --agreements 50
