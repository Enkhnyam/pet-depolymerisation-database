"""Regression test on hand-curation. Run it after any supervisor edit to the answer key."""
from _setup import FIELDS, OUTCOMES, curated, show

MEASURED = ["temperature_c", "reaction_time_min", "PET_amount_g", "catalyst_amount_g"]


def main() -> None:
    table = curated()
    percentages = table[OUTCOMES]
    amounts = table[FIELDS].select_dtypes("number")

    faults = {
        "experiments": len(table),
        "entered twice": table.duplicated(subset=["doi"] + FIELDS).sum(),
        "no outcome at all": percentages.isna().all(axis=1).sum(),
        "percentage outside 0-100": ((percentages < 0) | (percentages > 100)).sum().sum(),
        "negative amount": (amounts < 0).sum().sum(),
        "citing no source chunk": table.source_chunk_ids.map(len).eq(0).sum(),
    }
    ranges = table[MEASURED].agg(["min", "max"]).T

    show("faults", faults, fmt="{:.0f}")
    show("value ranges", ranges)


if __name__ == "__main__":
    main()
