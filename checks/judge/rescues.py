"""Pairs the metric rejected purely because the two catalyst names differ.

Where both graders say correct, the names are the same substance spelled differently and the
metric was simply wrong. Where both say incorrect, the extracted name is a placeholder that
identifies no substance, so rejecting it was right for the wrong reason.
"""
import pandas as pd

from _setup import LABELLED, golden, scored, show


def main() -> None:
    rejected = scored(run=LABELLED).query("verdict == 'MISMATCH' and catalyst_match == False")
    names = pd.DataFrame({
        "doi": rejected.doi,
        "index": rejected["index"],
        "curated": [row["catalyst"]["curated"] for row in rejected.fields],
        "extracted": [row["catalyst"]["extracted"] for row in rejected.fields],
    })
    merged = names.merge(golden()[["doi", "index", "judge", "human"]], on=["doi", "index"])

    print(f"\n{len(rejected)} matches rejected on the catalyst name, "
          f"{len(merged)} of them labelled")
    show("names", merged[["judge", "human", "curated", "extracted"]].reset_index(drop=True))
    show("judge against the chemists here",
         pd.crosstab(merged.judge, merged.human), fmt="{:.0f}")


if __name__ == "__main__":
    main()
