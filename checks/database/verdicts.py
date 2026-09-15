"""The judge's verdicts on the database.

No curated table exists for this corpus, which is the point: this is the number the agreement
study licenses us to read as a quality estimate.

It measures precision, not recall. The judge only ever sees records that exist, so an experiment
the extractor missed is invisible to it.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from _setup import DATABASE, DATABASE_JUDGE, show, sources
from core.schema import canonical_field


def released_keys() -> set:
    """(doi, record index) for every row the database actually releases.

    The judge read all 5,563 extracted records, but 1,621 of them are heterogeneous or
    unverified-phase and the release removes them. A correction proposed on a record nobody can
    download says nothing about the published data, so the field-correction panel counts only
    the released ones. Read from the released CSV rather than re-derived, so the panel and the
    file cannot drift apart.
    """
    path = Path(__file__).resolve().parents[2] / "data" / "pet_homogeneous_catalysis.csv"
    with path.open(encoding="utf-8") as handle:
        return {(row["doi"], int(row["record_index"])) for row in csv.DictReader(handle)
                if row.get("record_index", "").strip().lstrip("-").isdigit()}


def compute(released_only: bool = False) -> dict:
    """One verdict per record, and the fields the judge proposed changing.

    `released_only` restricts to the records the database ships; see released_keys().
    """
    keep = released_keys() if released_only else None
    verdicts = []
    for path in (DATABASE_JUDGE / "verdicts").glob("*.json"):
        payload = json.loads(path.read_text())
        for verdict in payload["verdicts"]:
            if keep is not None and (payload["doi"], verdict["extracted_index"]) not in keep:
                continue
            verdicts.append(verdict)

    # Partition on drop_record, the judge's own instruction to remove a record, because that is
    # what cli/apply_fixes.py acts on. Counting "rejected outright" as "rejected
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
