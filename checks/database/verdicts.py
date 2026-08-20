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


def compute() -> dict:
    """One verdict per record, and the fields the judge proposed changing."""
    verdicts = []
    for path in (DATABASE_JUDGE / "verdicts").glob("*.json"):
        verdicts += json.loads(path.read_text())["verdicts"]

    accepted = sum(1 for verdict in verdicts if verdict["verdict"] == "correct")
    rejected = [verdict for verdict in verdicts if verdict["verdict"] != "correct"]
    corrected = sum(1 for verdict in rejected if verdict["bad_fields"])

    return {
        "counts": {"records judged": len(verdicts),
                   "accepted": accepted,
                   "rejected, with a correction": corrected,
                   "rejected outright": len(rejected) - corrected},
        "pass rate": accepted / len(verdicts) if verdicts else 0,
        "fields": pd.Series(Counter(field for verdict in rejected
                                    for field in verdict["bad_fields"])).sort_values(ascending=False),
    }


def main() -> None:
    sources(extraction=DATABASE, judge=DATABASE_JUDGE)
    result = compute()
    show("verdicts", result["counts"], fmt="{:.0f}")
    print(f"\npass rate {result['pass rate']:.1%}")
    show("fields corrected", result["fields"], fmt="{:.0f}")


if __name__ == "__main__":
    main()
