"""The funnel from search to corpus, and what the extraction produced on it.

The drop from papers that passed the filter to papers we actually hold is licensing, not
relevance: we have a text-and-data-mining entitlement with Elsevier and with nobody else.
"""
import csv
from collections import Counter

import pandas as pd

from _setup import DATABASE, records, show
from core.paths import data_path

ELSEVIER = "10.1016"
PUBLISHERS = {ELSEVIER: "Elsevier", "10.1002": "Wiley", "10.1021": "ACS",
              "10.1039": "RSC", "10.1007": "Springer", "10.3390": "MDPI"}


def main() -> None:
    with data_path("corpus_candidates.csv").open(encoding="utf-8") as handle:
        candidates = list(csv.DictReader(handle))
    kept = [row for row in candidates if row["keep"].lower() == "true"]

    funnel = {"candidates found": len(candidates)}
    dropped = Counter(row["reason"] for row in candidates if row["keep"].lower() != "true")
    for reason, count in dropped.most_common():
        funnel[f"dropped, {reason}"] = -count
    funnel["passed the filter"] = len(kept)
    funnel["of those, Elsevier"] = sum(1 for row in kept if row["doi"].startswith(ELSEVIER))
    funnel["converted to chunked text"] = len(list(data_path("corpus_markdown").glob("*.md")))
    show("funnel", funnel, fmt="{:.0f}")

    by_publisher = Counter(PUBLISHERS.get(row["doi"].split("/")[0], "other") for row in kept)
    show("relevant papers by publisher",
         pd.Series(by_publisher).sort_values(ascending=False), fmt="{:.0f}")

    extracted = records(DATABASE)
    per_paper = extracted.groupby("doi").size()
    processed = len(list((DATABASE / "extractions").glob("*.json")))
    show("extraction", {
        "papers processed": processed,
        "papers yielding records": len(per_paper),
        "papers yielding none": processed - len(per_paper),
        "records": len(extracted),
        "median records per yielding paper": per_paper.median(),
        "largest single paper": per_paper.max(),
    }, fmt="{:.0f}")


if __name__ == "__main__":
    main()
