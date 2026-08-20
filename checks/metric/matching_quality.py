"""Is the pairing algorithm the bottleneck? Re-pairs greedily (closest first) and compares
with the optimal Hungarian assignment. If both find the same matches, the metric loses records
after pairing, when judging a pair acceptable -- not while choosing pairs."""
import numpy as np
from _setup import *
from core.evaluation import record_penalty

reference = load_curated(data_path(CURATED))
extraction = experiments()
greedy = 0

for doi, curated_rows in reference.items():
    extracted_rows = extraction.get(doi, [])
    if not curated_rows or not extracted_rows:
        continue
    cost, accepts = {}, {}
    for i, left in enumerate(curated_rows):
        for j, right in enumerate(extracted_rows):
            penalty, matched, _ = record_penalty(left, right, CATALYST, TOLERANCE)
            cost[i, j] = penalty if matched else 10.0
            accepts[i, j] = matched and penalty < ACCEPT
    taken_left, taken_right = set(), set()
    for _, i, j in sorted((c, i, j) for (i, j), c in cost.items()):
        if i in taken_left or j in taken_right:
            continue
        taken_left.add(i); taken_right.add(j)
        greedy += accepts[i, j]

hungarian = totals()["tp"]
show("correct matches found", {"optimal (Hungarian)": hungarian,
                               "closest-first (greedy)": greedy,
                               "difference": hungarian - greedy}, fmt="{:.0f}")
