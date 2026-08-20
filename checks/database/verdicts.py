"""The judge's verdicts on the database.

No curated table exists for this corpus, which is the point: this is the number the agreement
study licenses us to read as a quality estimate.

It measures precision, not recall. The judge only ever sees records that exist, so an experiment
the extractor missed is invisible to it.
"""
import json
from collections import Counter

import pandas as pd

from _setup import DATABASE, DATABASE_JUDGE, show, sources


def main() -> None:
    sources(extraction=DATABASE, judge=DATABASE_JUDGE)
    verdicts = []
    for path in (DATABASE_JUDGE / "verdicts").glob("*.json"):
        verdicts += json.loads(path.read_text())["verdicts"]

    accepted = sum(1 for verdict in verdicts if verdict["verdict"] == "correct")
    rejected = [verdict for verdict in verdicts if verdict["verdict"] != "correct"]
    corrected = sum(1 for verdict in rejected if verdict["bad_fields"])

    show("verdicts", {
        "records judged": len(verdicts),
        "accepted": accepted,
        "rejected, with a correction": corrected,
        "rejected outright": len(rejected) - corrected,
    }, fmt="{:.0f}")
    print(f"\npass rate {accepted / len(verdicts):.1%}")

    fields = Counter(field for verdict in rejected for field in verdict["bad_fields"])
    show("fields corrected", pd.Series(fields).sort_values(ascending=False), fmt="{:.0f}")


if __name__ == "__main__":
    main()
