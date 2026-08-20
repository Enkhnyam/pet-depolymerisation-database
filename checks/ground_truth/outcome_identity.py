"""Yield should equal conversion x selectivity.

This needs no external truth -- the identity has to hold. A wide spread means the three numbers
were transcribed from different tables, or one of them means something the schema does not
assume.
"""
from _setup import OUTCOMES, curated, show


def main() -> None:
    table = curated()
    complete = table.dropna(subset=OUTCOMES)

    implied = complete.conversion_percent * complete.selectivity_percent / 100
    error = (complete.yield_percent - implied).abs()

    print(f"\nexperiments reporting all three outcomes: {len(complete)} of {len(table)}")
    show("reported minus implied yield", error.describe())


if __name__ == "__main__":
    main()
