"""Why the two graders agree as much as they do.

Eight of the ten fields are numbers, and a number is inside tolerance or it is not -- there is
nothing to interpret, so both graders reach the same answer. Almost every disagreement sits on
the catalyst, the one field written as free text. On a schema this rigid, reading the paper and
matching against a table are doing nearly the same job.
"""
from collections import Counter

import pandas as pd

from _setup import judged, scored, show

TEXT_FIELDS = {"catalyst", "solvent"}
UNMATCHED = "no curated counterpart"


def main() -> None:
    comparable = scored().query("situation != @UNMATCHED")
    both = comparable.merge(judged(), on=["doi", "index"])

    show("on records the table could be compared against", {
        "records": len(both),
        "graders agree": (both.judge == both.metric).sum(),
    }, fmt="{:.0f}")

    flagged = both.query("judge == 'incorrect'")
    named = Counter(field for row in flagged.bad_fields for field in row)
    show(f"fields the judge names in the {len(flagged)} it rejects",
         pd.Series(named).sort_values(ascending=False), fmt="{:.0f}")
    on_text = sum(1 for row in flagged.bad_fields if TEXT_FIELDS & set(row))
    print(f"  of those, naming a text field: {on_text}")

    accepted = both.query("verdict == 'TP'")
    still_wrong = Counter(field for row in accepted.field_errors for field in row)
    numeric = sum(count for field, count in still_wrong.items() if field not in TEXT_FIELDS)
    show(f"wrong fields inside the {len(accepted)} pairs the metric accepted", {
        "total": sum(still_wrong.values()),
        "numeric": numeric,
    }, fmt="{:.0f}")


if __name__ == "__main__":
    main()
