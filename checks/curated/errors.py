"""What the metric did to each record, and how close its accepted matches were to the cutoff.

A MISMATCH is a pair that was matched and then rejected, so it counts as both a false positive
and a false negative -- which is why reported FP and FN exceed the counts here.

If accepted matches cluster just under the cutoff the threshold is carrying the result and it is
fragile; clustered near zero, the matches are comfortable.
"""
import pandas as pd

from _setup import (ACCEPT, CURATED, EXTRACTION, JUDGE, judged, scored, show, sources, totals)


def main() -> None:
    sources(answer_key=CURATED, extraction=EXTRACTION, judge=JUDGE)
    labels = scored()
    show("the metric's verdict on every record", labels.verdict.value_counts(), fmt="{:.0f}")

    rejected = labels.query("verdict == 'MISMATCH'")
    show("rejected matches", {
        "total": len(rejected),
        "on the catalyst name": (rejected.catalyst_match == False).sum(),  # noqa: E712
    }, fmt="{:.0f}")

    show("field disagreements among matched pairs",
         pd.Series(totals()["field_error_counts"]).sort_values(ascending=False), fmt="{:.0f}")

    show(f"penalty of accepted matches (accepted below {ACCEPT:.2f})",
         labels.query("verdict == 'TP'").avg_penalty.describe())

    both = labels.merge(judged(), on=["doi", "index"])
    show("judge against metric situation",
         pd.crosstab(both.situation, both.judge), fmt="{:.0f}")


if __name__ == "__main__":
    main()
