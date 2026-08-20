"""Shape of the answer key: how big it is, and which fields the literature simply omits."""
from _setup import FIELDS, curated, show


def main() -> None:
    table = curated()

    size = {
        "papers": table.doi.nunique(),
        "experiments": len(table),
        "distinct catalysts": table.catalyst.nunique(),
    }
    blank = table[FIELDS].isna().mean().sort_values(ascending=False)

    show("size", size, fmt="{:.0f}")
    show("share of experiments where the field is blank", blank, fmt="{:.0%}")


if __name__ == "__main__":
    main()
