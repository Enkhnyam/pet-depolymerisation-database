"""Is the metric grader behaving, and where does it lose records?

Three things it could be blamed for, answered in order.

Pairing: it uses an optimal assignment; a greedy closest-first pass finds the same matches, so the
algorithm is not the bottleneck. Whatever it loses, it loses after pairing.

Thresholds: a MISMATCH is a pair matched and then rejected, which counts as both a false positive
and a false negative -- that is why reported FP and FN exceed the visible counts.

Names: where both catalyst names in a rejected pair are ordinary chemical names, the metric paired
the wrong experiments, which is a real defect. Everywhere else at least one name is a mixture, a
supported material, or a code the paper coined, and no string comparison could have resolved it.
"""
import pandas as pd

from _setup import (ACCEPT, CATALYST, CURATED, EXTRACTION, TOLERANCE, curated, experiments,
                    records, scored, show, sources, totals)
from core.evaluation import record_penalty
from core.paths import data_path
from core.schema import load_curated

UNPAIRABLE = 10.0
BOTH_PLAIN = "plain chemical name / plain chemical name"


def kind_of(name: object) -> str:
    """Classify a catalyst name by whether anything could look it up."""
    text, lowered = str(name), str(name).lower()
    if "/" in text or "+" in text or " and " in lowered:
        return "mixture of two"
    if "@" in text:
        return "supported on a carrier"
    if lowered.startswith(("pil", "cat-", "il-", "des")):
        return "code the paper coined"
    return "plain chemical name"


def greedy_matches(curated_rows: list, extracted_rows: list) -> int:
    """Pair closest-first, each row used once, and count the pairs that would be accepted."""
    cost, accepts = {}, {}
    for i, left in enumerate(curated_rows):
        for j, right in enumerate(extracted_rows):
            penalty, matched, _ = record_penalty(left, right, CATALYST, TOLERANCE)
            cost[i, j] = penalty if matched else UNPAIRABLE
            accepts[i, j] = matched and penalty < ACCEPT

    taken_left, taken_right, found = set(), set(), 0
    for _, i, j in sorted((c, i, j) for (i, j), c in cost.items()):
        if i not in taken_left and j not in taken_right:
            taken_left.add(i); taken_right.add(j); found += accepts[i, j]
    return found


def main() -> None:
    sources(answer_key=CURATED, extraction=EXTRACTION)

    reference = load_curated(data_path(CURATED))
    extraction = experiments()
    greedy = sum(greedy_matches(rows, extraction.get(doi, []))
                 for doi, rows in reference.items() if rows and extraction.get(doi))
    hungarian = totals()["tp"]
    show("is the pairing algorithm the bottleneck?", {
        "optimal (Hungarian)": hungarian,
        "closest-first (greedy)": greedy,
        "difference": hungarian - greedy,
    }, fmt="{:.0f}")

    labels = scored()
    show("the metric's verdict on every record", labels.verdict.value_counts(), fmt="{:.0f}")
    show("field disagreements among matched pairs",
         pd.Series(totals()["field_error_counts"]).sort_values(ascending=False), fmt="{:.0f}")
    show(f"penalty of accepted matches (accepted below {ACCEPT:.2f})",
         labels.query("verdict == 'TP'").avg_penalty.describe())

    names = sorted(set(curated().catalyst.dropna()) | set(records().catalyst.dropna()))
    show(f"all {len(names)} distinct catalyst names",
         pd.Series([kind_of(n) for n in names]).value_counts(), fmt="{:.0f}")

    rejected = labels.query("verdict == 'MISMATCH' and catalyst_match == False")
    pairs = pd.DataFrame({"curated": [r["catalyst"]["curated"] for r in rejected.fields],
                          "extracted": [r["catalyst"]["extracted"] for r in rejected.fields]})
    pairs["kinds"] = [f"{kind_of(a)} / {kind_of(b)}" for a, b in zip(pairs.curated, pairs.extracted)]
    show(f"the {len(pairs)} pairs rejected on the name", pairs.kinds.value_counts(), fmt="{:.0f}")
    mispaired = pairs[pairs.kinds == BOTH_PLAIN]
    show(f"both names ordinary -- mispaired, not misnamed ({len(mispaired)})",
         mispaired[["curated", "extracted"]].reset_index(drop=True))


if __name__ == "__main__":
    main()
