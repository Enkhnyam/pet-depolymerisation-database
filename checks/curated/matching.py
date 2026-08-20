"""Is the pairing algorithm the bottleneck?

The metric pairs curated and extracted records with an optimal (Hungarian) assignment. This
re-pairs them greedily -- closest pair first -- and compares the number of correct matches. If
both find the same, the metric loses records *after* pairing, when deciding whether a pair is
acceptable, not while choosing which pairs to make.
"""
from _setup import (ACCEPT, CATALYST, CURATED, EXTRACTION, TOLERANCE, experiments, show,
                    sources, totals)
from core.paths import data_path
from core.schema import load_curated
from core.evaluation import record_penalty

UNPAIRABLE = 10.0   # stand-in cost for a pair the catalyst gate refuses outright


def greedy_matches(curated_rows: list, extracted_rows: list) -> int:
    """Pair closest-first, each row used once, and count the pairs that would be accepted."""
    cost = {}
    accepts = {}
    for i, curated_row in enumerate(curated_rows):
        for j, extracted_row in enumerate(extracted_rows):
            penalty, catalyst_matched, _ = record_penalty(
                curated_row, extracted_row, CATALYST, TOLERANCE)
            cost[i, j] = penalty if catalyst_matched else UNPAIRABLE
            accepts[i, j] = catalyst_matched and penalty < ACCEPT

    taken_curated = set()
    taken_extracted = set()
    matched = 0
    for _, i, j in sorted((penalty, i, j) for (i, j), penalty in cost.items()):
        if i in taken_curated or j in taken_extracted:
            continue
        taken_curated.add(i)
        taken_extracted.add(j)
        matched += accepts[i, j]
    return matched


def main() -> None:
    sources(answer_key=CURATED, extraction=EXTRACTION)
    reference = load_curated(data_path(CURATED))
    extraction = experiments(EXTRACTION)

    greedy = 0
    for doi, curated_rows in reference.items():
        extracted_rows = extraction.get(doi, [])
        if curated_rows and extracted_rows:
            greedy += greedy_matches(curated_rows, extracted_rows)

    hungarian = totals()["tp"]
    show("correct matches found", {
        "optimal (Hungarian)": hungarian,
        "closest-first (greedy)": greedy,
        "difference": hungarian - greedy,
    }, fmt="{:.0f}")


if __name__ == "__main__":
    main()
