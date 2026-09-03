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
from core.schema import canonical_field


def compute() -> dict:
    """One verdict per record, and the fields the judge proposed changing."""
    verdicts = []
    for path in (DATABASE_JUDGE / "verdicts").glob("*.json"):
        verdicts += json.loads(path.read_text())["verdicts"]

    # Partition on drop_record, the judge's own instruction to remove a record, because that is
    # what cli/release.py and cli/apply_fixes.py act on. Counting "rejected outright" as "rejected
    # with no field fixes" instead put 66 records that the judge asked to drop into the corrected
    # column, and left the paper reporting 29 drops against the 95 the released files perform.
    accepted = sum(1 for verdict in verdicts if verdict["verdict"] == "correct")
    rejected = [verdict for verdict in verdicts if verdict["verdict"] != "correct"]
    dropped = [verdict for verdict in rejected if verdict.get("drop_record")]
    corrected = len(rejected) - len(dropped)

    return {
        "counts": {"records judged": len(verdicts),
                   "accepted": accepted,
                   "rejected, with a correction": corrected,
                   "rejected outright": len(dropped)},
        "pass rate": accepted / len(verdicts) if verdicts else 0,
        # through canonical_field: the judge spells the PET mass both PET_amount_g and
        # pet_amount_g, and counting the spellings separately split one field into two rows
        # (255 and 23) and understated the field the paper reports as its third commonest fix.
        "fields": pd.Series(Counter(
            canonical_field(field) or field
            for verdict in rejected for field in verdict["bad_fields"])).sort_values(ascending=False),
    }


def main() -> None:
    sources(extraction=DATABASE, judge=DATABASE_JUDGE)
    result = compute()
    show("verdicts", result["counts"], fmt="{:.0f}")
    print(f"\npass rate {result['pass rate']:.1%}")
    show("fields corrected", result["fields"], fmt="{:.0f}")


if __name__ == "__main__":
    main()
