"""The funnel from search to corpus, and what the extraction produced on it.

The drop from papers that passed the filter to papers we actually hold is licensing, not
relevance: we have a text-and-data-mining entitlement with Elsevier and with nobody else.
"""
import csv
import json
import re
from collections import Counter

import pandas as pd

from _setup import DATABASE, records, show, sources
from core.paths import data_path

ELSEVIER = "10.1016"

# Why a paper produced no records. Read off the title, in order, so the classification is
# reproducible rather than a hand count that only exists in a figure.
EMPTY_REASONS = [
    ("enzymatic or biological", r"enzym|petase|cutinase|hydrolase|esterase|lipase|bacter|microb|"
                                r"biolog|biodegrad|fungal|biocatal|whole-cell|coli"),
    ("review article", r"\breview\b|recent advance|advances in|perspective|outlook|progress in|"
                       r"state of the art"),
    ("other route or material", r"pyrolys|incinerat|combust|gasific|composite|membrane|fib(er|re)|"
                                r"elastomer|resin|coating|adsorb|electrode|microplastic|migration|"
                                r"copolyester|nanocage"),
]
PUBLISHERS = {ELSEVIER: "Elsevier", "10.1002": "Wiley", "10.1021": "ACS",
              "10.1039": "RSC", "10.1007": "Springer", "10.3390": "MDPI"}

# How a paper's full text reached us, tagged the way the manuscript's macros name it.
SOURCE_TAGS = {"Elsevier XML": "ElsevierXml", "Europe PMC JATS": "EuropePmc", "PDF": "Pdf"}


def compute() -> dict:
    """The funnel, the publishers behind it, and what the extraction produced."""
    with data_path("corpus_candidates.csv").open(encoding="utf-8") as handle:
        candidates = list(csv.DictReader(handle))
    kept = [row for row in candidates if row["keep"].lower() == "true"]

    funnel = {"candidates found": len(candidates)}
    for reason, count in Counter(row["reason"] for row in candidates
                                 if row["keep"].lower() != "true").most_common():
        funnel[f"dropped, {reason}"] = -count
    funnel["passed the filter"] = len(kept)
    funnel["of those, Elsevier"] = sum(1 for row in kept if row["doi"].startswith(ELSEVIER))
    funnel["converted to chunked text"] = len(list(data_path("corpus_markdown").glob("*.md")))
    # the corpus can be ahead of the extraction while new papers are still being processed;
    # reporting only the corpus size would overstate what the database is actually built from
    funnel["extracted so far"] = len(list((DATABASE / "extractions").glob("*.json")))

    publishers = Counter(PUBLISHERS.get(row["doi"].split("/")[0], "other") for row in kept)

    titles = {row["doi"].lower(): row["title"] for row in kept}

    extracted = records(DATABASE)
    per_paper = extracted.groupby("doi").size()

    # How each converted paper arrived, and the size of the largest one the judge had to read.
    # Both were computed in tools/paper_numbers.py, which re-read corpus_candidates.csv and
    # re-globbed corpus_markdown to do it, and sized the largest paper by parsing every
    # extraction file twice -- once in a generator's condition and again for its value.
    formats = {row["doi"].lower(): row["format"] for row in
               csv.DictReader(data_path("source_format.csv").open(encoding="utf-8"))}
    by_source = Counter()
    largest_chars = 0

    empty = Counter()
    processed = 0
    for path in (DATABASE / "extractions").glob("*.json"):
        paper = json.loads(path.read_text())
        processed += 1
        markdown = data_path("corpus_markdown") / (
            paper["doi"].replace("/", "@").lower() + ".md")
        if markdown.exists():
            largest_chars = max(largest_chars, markdown.stat().st_size)
        if paper["records"]:
            continue
        title = titles.get(paper["doi"].lower(), "")
        if not title:
            empty["abstract only or no metadata"] += 1
            continue
        for label, pattern in EMPTY_REASONS:
            if re.search(pattern, title, re.I):
                empty[label] += 1
                break
        else:
            empty["unclassified"] += 1

    kept_dois = {row["doi"].lower() for row in kept}
    for path in data_path("corpus_markdown").glob("*.md"):
        doi = path.stem.replace("@", "/").lower()
        if doi in kept_dois:
            by_source[SOURCE_TAGS.get(formats.get(doi), "OtherSource")] += 1

    return {
        "empty papers": pd.Series(empty).sort_values(ascending=False),
        "funnel": funnel,
        "obtained by": by_source,
        # roughly four characters to a token; the paper quotes this to say the judge's context
        # window was never the binding constraint
        "largest judged tokens": largest_chars // 4,
        "publishers": pd.Series(publishers).sort_values(ascending=False),
        "per paper": per_paper,
        "extraction": {
            "papers processed": processed,
            "papers yielding records": len(per_paper),
            "papers yielding none": processed - len(per_paper),
            "records": len(extracted),
            "median records per yielding paper": per_paper.median(),
            "largest single paper": per_paper.max(),
        },
    }


def main() -> None:
    sources(funnel="corpus_candidates.csv", corpus="corpus_markdown", extraction=DATABASE)
    result = compute()
    show("funnel", result["funnel"], fmt="{:.0f}")
    show("why papers yielded no records", result["empty papers"], fmt="{:.0f}")
    show("relevant papers by publisher", result["publishers"], fmt="{:.0f}")
    show("extraction", result["extraction"], fmt="{:.0f}")
    show("how the full text was obtained", result["obtained by"], fmt="{:.0f}")
    print(f"\nlargest paper the judge read: ~{result['largest judged tokens']:,} tokens")


if __name__ == "__main__":
    main()
