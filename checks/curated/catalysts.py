"""Separates 'our matcher is broken' from 'this subfield cannot be looked up'.

Where both names in a rejected pair are ordinary chemical names, the metric paired the wrong
experiments -- a real defect. Everywhere else at least one name is a mixture, a supported
material, or a code the paper coined for something it made, none of which any string comparison
could resolve.
"""
import pandas as pd

from _setup import curated, records, scored, show

BOTH_PLAIN = "plain chemical name / plain chemical name"


def kind_of(name: object) -> str:
    """Classify a catalyst name by whether anything could look it up."""
    text = str(name)
    lowered = text.lower()
    if "/" in text or "+" in text or " and " in lowered:
        return "mixture of two"
    if "@" in text:
        return "supported on a carrier"
    if lowered.startswith(("pil", "cat-", "il-", "des")):
        return "code the paper coined"
    return "plain chemical name"


def main() -> None:
    names = sorted(set(curated().catalyst.dropna()) | set(records().catalyst.dropna()))
    population = pd.Series([kind_of(name) for name in names]).value_counts()
    show(f"all {len(names)} distinct catalyst names", population, fmt="{:.0f}")

    rejected = scored().query("verdict == 'MISMATCH' and catalyst_match == False")
    pairs = pd.DataFrame({
        "curated": [row["catalyst"]["curated"] for row in rejected.fields],
        "extracted": [row["catalyst"]["extracted"] for row in rejected.fields],
    })
    pairs["kinds"] = [f"{kind_of(a)} / {kind_of(b)}"
                      for a, b in zip(pairs.curated, pairs.extracted)]
    show(f"the {len(pairs)} pairs rejected on the name", pairs.kinds.value_counts(), fmt="{:.0f}")

    mispaired = pairs[pairs.kinds == BOTH_PLAIN]
    show(f"both names ordinary -- mispaired, not misnamed ({len(mispaired)})",
         mispaired[["curated", "extracted"]].reset_index(drop=True))


if __name__ == "__main__":
    main()
