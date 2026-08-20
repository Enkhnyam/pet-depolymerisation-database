"""What is in the human-labelled set, and how it was drawn.

Records where the two graders disagreed on the catalyst were kept whole, since those decide
which grader is right. Records with no curated counterpart were sampled rather than taken whole,
there being too many. Records both graders accepted form a control group, where a grader
agreeing only by luck would show up.

The dev/test split was fixed before the final rubric was written, so the test half is a clean
estimate of anything tuned while looking at the other half.
"""
import hashlib

import pandas as pd

from _setup import LABELLED, LABELS, golden, show


def main() -> None:
    labelled = golden()

    show("set", {
        "records": len(labelled),
        "papers": labelled.doi.nunique(),
        "labels revised after criteria settled": labelled.correction.notna().sum(),
    }, fmt="{:.0f}")

    checksum = hashlib.sha256(LABELS.read_bytes()).hexdigest()
    print(f"\nsource run  {LABELLED.name}\nsha256      {checksum}")

    show("labels by split", pd.crosstab(labelled.split, labelled.human), fmt="{:.0f}")
    show("how the set was drawn", pd.crosstab(labelled.situation, labelled.human), fmt="{:.0f}")


if __name__ == "__main__":
    main()
