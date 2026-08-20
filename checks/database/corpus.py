"""The funnel from search to corpus, and what the extraction produced on it.

The drop from papers that passed the filter to papers we hold is licensing, not relevance:
we have a text-and-data-mining entitlement with Elsevier and with nobody else.
"""
import csv
from collections import Counter
from _setup import *

rows = list(csv.DictReader(data_path("corpus_candidates.csv").open(encoding="utf-8")))
kept = [r for r in rows if r["keep"].lower() == "true"]
funnel = {"candidates found": len(rows)}
for reason, n in Counter(r["reason"] for r in rows if r["keep"].lower() != "true").most_common():
    funnel[f"dropped, {reason}"] = -n
funnel["passed the filter"] = len(kept)
funnel["of those, Elsevier"] = sum(1 for r in kept if r["doi"].startswith("10.1016"))
funnel["converted to chunked text"] = len(list(data_path("corpus_markdown").glob("*.md")))
show("funnel", funnel, fmt="{:.0f}")

publishers = {"10.1016": "Elsevier", "10.1002": "Wiley", "10.1021": "ACS",
              "10.1039": "RSC", "10.1007": "Springer", "10.3390": "MDPI"}
counts = Counter(publishers.get(r["doi"].split("/")[0], "other") for r in kept)
show("relevant papers by publisher", pd.Series(counts).sort_values(ascending=False), fmt="{:.0f}")

extracted = records(DATABASE)
per_paper = extracted.groupby("doi").size()
processed = len(list((DATABASE / "extractions").glob("*.json")))
show("extraction", {"papers processed": processed,
                    "papers yielding records": len(per_paper),
                    "papers yielding none": processed - len(per_paper),
                    "records": len(extracted),
                    "median records per yielding paper": per_paper.median(),
                    "largest single paper": per_paper.max()}, fmt="{:.0f}")
