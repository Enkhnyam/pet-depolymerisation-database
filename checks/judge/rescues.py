"""Pairs the metric rejected purely because the catalyst names differ.

Where both graders say correct, the names are the same substance spelled differently and the
metric was wrong. Where both say incorrect, the extracted name is a placeholder, so rejecting
it was right for the wrong reason.
"""
from _setup import *

rejected = scored(run=LABELLED).query("verdict == 'MISMATCH' and catalyst_match == False")
names = pd.DataFrame({"doi": rejected.doi, "index": rejected["index"],
                      "curated": [f["catalyst"]["curated"] for f in rejected.fields],
                      "extracted": [f["catalyst"]["extracted"] for f in rejected.fields]})
merged = names.merge(golden()[["doi", "index", "judge", "human"]], on=["doi", "index"])

print(f"\n{len(rejected)} matches rejected on the catalyst name, "
      f"{len(merged)} of them labelled")
show("names", merged[["judge", "human", "curated", "extracted"]].reset_index(drop=True))
show("judge against the chemists here", pd.crosstab(merged.judge, merged.human), fmt="{:.0f}")
