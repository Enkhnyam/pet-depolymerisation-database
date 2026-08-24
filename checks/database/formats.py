"""Does it matter which format a paper arrived in?

The corpus is no longer one thing. Papers reached it three ways: Elsevier full-text XML under the
text-and-data-mining agreement, Europe PMC JATS for the open-access deposits publishers refuse to
serve automatically, and PDFs put through docling for everything else. Roughly half the database
now comes from a PDF rather than from publisher markup.

That is a choice the database has to defend, because the three are not equally faithful. XML
carries tables as markup; docling has to recover them from a rendering. If the format decided
what came out, the corpus would be a mixture of two different things wearing one name, and any
result computed over it would be partly a result about acquisition.

So the comparison is made rather than assumed. What it shows is that format barely moves whether
a paper yields records at all, moves field completeness somewhat, and moves the judge's pass rate
by a few points -- differences worth stating, and far smaller than the difference between having
the paper and not having it.

Read alongside the completeness column: XML papers are the most complete and also the most
corrected, which is the same fact twice. A record with more fields filled gives the judge more to
object to, so a high pass rate is partly a reward for leaving fields blank.
"""
import csv
import glob
import json

import pandas as pd

from _setup import DATABASE, DATABASE_JUDGE, data_path, records, show, sources

FORMATS = "source_format.csv"
FIELDS = ["temperature_c", "reaction_time_min", "yield_percent", "PET_amount_g",
          "catalyst_amount_g", "conversion_percent", "solvent_amount_g"]
ORDER = ["Elsevier XML", "Europe PMC JATS", "PDF"]


def format_of() -> dict:
    """doi -> the format it arrived in, from the manifest the corpus build writes."""
    with data_path(FORMATS).open(encoding="utf-8") as handle:
        return {row["doi"].lower(): row["format"] for row in csv.DictReader(handle)}


def compute() -> dict:
    source = format_of()

    # every extracted paper, including the ones that yielded nothing: "did this paper produce
    # records at all" is the first thing format could plausibly change
    papers = []
    for path in glob.glob(str(DATABASE / "extractions/*.json")):
        payload = json.loads(open(path, encoding="utf-8").read())
        doi = payload["doi"].lower()
        papers.append({"doi": doi, "format": source.get(doi), "records": len(payload["records"])})
    papers = pd.DataFrame(papers).dropna(subset=["format"])

    reach = papers.groupby("format").agg(
        papers=("records", "size"),
        yielding=("records", lambda s: int((s > 0).sum())),
        records=("records", "sum"))
    reach["% yielding"] = (100 * reach.yielding / reach.papers).round(0)

    frame = records(DATABASE)
    frame["format"] = frame.doi.str.lower().map(source)
    completeness = (frame.dropna(subset=["format"]).groupby("format")[FIELDS]
                    .apply(lambda block: block.notna().mean() * 100).round(0))

    # the judge's view: a record it would rewrite or drop is one it did not pass
    graded = []
    for path in glob.glob(str(DATABASE_JUDGE / "verdicts/*.json")):
        payload = json.loads(open(path, encoding="utf-8").read())
        doi = payload["doi"].lower()
        for verdict in payload["verdicts"]:
            changed = bool(verdict.get("bad_fields")) or bool(verdict.get("drop_record"))
            graded.append({"format": source.get(doi), "changed": changed})
    graded = pd.DataFrame(graded).dropna(subset=["format"])
    passes = graded.groupby("format").agg(records=("changed", "size"),
                                          changed=("changed", "sum"))
    passes["pass rate %"] = (100 * (1 - passes.changed / passes.records)).round(1)

    return {"reach": reach.reindex(ORDER).dropna(how="all"),
            "completeness": completeness.reindex(ORDER).dropna(how="all"),
            "judge": passes.reindex(ORDER).dropna(how="all")}


def main() -> None:
    sources(corpus="corpus_markdown", extraction=DATABASE, judge=DATABASE_JUDGE)
    result = compute()

    show("papers and records by the format they arrived in", result["reach"])
    show("share of records reporting each field, by format (%)", result["completeness"].T)
    show("what the judge made of them", result["judge"])

    reach = result["reach"]
    spread = reach["% yielding"].max() - reach["% yielding"].min()
    rates = result["judge"]["pass rate %"]
    print(f"\nwhether a paper yields records at all varies by {spread:.0f} points across formats; "
          f"the judge's pass rate varies by {rates.max() - rates.min():.1f}.")
    print("Neither is nothing, and neither is the difference between two different corpora.")


if __name__ == "__main__":
    main()
