"""What the metric did to each record, crossed with what the judge said about it.

A MISMATCH is a pair that was matched and then rejected, so it counts as both a false positive
and a false negative -- which is why the reported FP and FN exceed the counts printed here.
"""
import pandas as pd

from _setup import judged, scored, show


def main() -> None:
    labels = scored()
    show("the metric's verdict on every record", labels.verdict.value_counts(), fmt="{:.0f}")

    rejected = labels.query("verdict == 'MISMATCH'")
    show("rejected matches", {
        "total": len(rejected),
        "on the catalyst name": (rejected.catalyst_match == False).sum(),  # noqa: E712
    }, fmt="{:.0f}")

    both = labels.merge(judged(), on=["doi", "index"])
    show("judge against metric situation",
         pd.crosstab(both.situation, both.judge), fmt="{:.0f}")


if __name__ == "__main__":
    main()
