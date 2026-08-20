"""The curated answer key: how big it is, what it leaves blank, and whether it holds together.

Everything else in the project is measured against this table, so its own faults matter more than
any score computed from it. The last block is the one check that needs no external truth: yield
should equal conversion x selectivity, and a wide spread means the three numbers were transcribed
from different tables.
"""
from _setup import CURATED, FIELDS, OUTCOMES, curated, show, sources

MEASURED = ["temperature_c", "reaction_time_min", "PET_amount_g", "catalyst_amount_g"]


def main() -> None:
    sources(answer_key=CURATED)
    table = curated()
    percentages = table[OUTCOMES]
    amounts = table[FIELDS].select_dtypes("number")

    show("size", {
        "papers": table.doi.nunique(),
        "experiments": len(table),
        "distinct catalysts": table.catalyst.nunique(),
    }, fmt="{:.0f}")

    show("faults", {
        "entered twice": table.duplicated(subset=["doi"] + FIELDS).sum(),
        "no outcome at all": percentages.isna().all(axis=1).sum(),
        "percentage outside 0-100": ((percentages < 0) | (percentages > 100)).sum().sum(),
        "negative amount": (amounts < 0).sum().sum(),
        "citing no source chunk": table.source_chunk_ids.map(len).eq(0).sum(),
    }, fmt="{:.0f}")

    show("share of experiments where the field is blank",
         table[FIELDS].isna().mean().sort_values(ascending=False), fmt="{:.0%}")

    complete = table.dropna(subset=OUTCOMES)
    implied = complete.conversion_percent * complete.selectivity_percent / 100
    error = (complete.yield_percent - implied).abs()
    print(f"\nreporting all three outcomes: {len(complete)} of {len(table)}")
    show("reported minus implied yield", error.describe())


if __name__ == "__main__":
    main()
