"""Does the extracted database behave like chemistry?

Nobody curated this corpus, so the data cannot be checked against a reference. What can be
checked is whether known relationships fall out of it: yield cannot exceed conversion, hotter
runs finish sooner, and the three routes should separate on the conditions they use.

The classification helpers live here rather than in the figure, because a route assignment that
only exists inside a plot is a number nobody can audit.
"""
import re

import pandas as pd

from _setup import DATABASE, records, show, sources

ROUTE_FROM_SOLVENT = [
    ("glycolysis", r"ethylene glycol|\beg\b|glycol(?!ic)|diethylene|propylene glycol"),
    ("methanolysis", r"methanol|\bmeoh\b"),
    ("hydrolysis", r"water|aqueous|\bnaoh\b|\bkoh\b|h2so4|h3po4|acid solution|steam"),
]

CATALYST_CLASSES = [
    ("none", r"^(none|no catalyst|-|nan|without catalyst)$"),
    ("deep eutectic", r"\bdes\b|deep eutectic"),
    ("ionic liquid", r"\[.*\]|imidazol|\bil\b|phosphonium"),
    ("metal salt", r"\bzn|\bmn|\bco\(|\bfe|\bcu|\bti|\bmg|\bca\(|acetate|carbonate|chloride|oxide"),
    ("acid or base", r"naoh|koh|hydroxide|h2so4|sulfuric|hcl|nitric|amine|\btbd\b|\bdbu\b"),
]

PAIRS = [
    ("temperature_c", "yield_percent"),
    ("reaction_time_min", "yield_percent"),
    ("temperature_c", "reaction_time_min"),
    ("catalyst_amount_g", "yield_percent"),
    ("conversion_percent", "yield_percent"),
    ("catalyst_amount_g", "PET_amount_g"),
]


def classify(value: object, rules: list, default: str) -> str:
    text = str(value).strip().lower()
    for label, pattern in rules:
        if re.search(pattern, text):
            return label
    return default


def compute() -> dict:
    """The database with route and catalyst class attached, plus the relationships to plot."""
    frame = records(DATABASE)
    frame["route"] = [classify(s, ROUTE_FROM_SOLVENT, "other/unclear") for s in frame.solvent]
    frame["catalyst class"] = [classify(c, CATALYST_CLASSES, "other") for c in frame.catalyst]
    frame["catalyst per g PET"] = frame.catalyst_amount_g / frame.PET_amount_g

    correlations = []
    for left, right in PAIRS:
        pair = frame[[left, right]].dropna()
        correlations.append({
            "x": left, "y": right, "points": len(pair),
            "spearman": pair[left].corr(pair[right], method="spearman"),
        })

    # yield cannot exceed conversion: an identity, so anything above the line is an error
    both = frame[["conversion_percent", "yield_percent"]].dropna()
    impossible = (both.yield_percent > both.conversion_percent + 1).sum()

    # percentages cannot exceed 100 either, and a record that says so is simply wrong
    out_of_range = {}
    for column in ("yield_percent", "conversion_percent", "selectivity_percent"):
        values = frame[column].dropna()
        over = frame[frame[column] > 100]
        out_of_range[column] = {"reported": len(values), "above 100%": len(over),
                                "papers": over.doi.nunique(), "highest": values.max()}

    return {
        "records": frame,
        "by route": frame.groupby("route").agg(
            records=("doi", "size"),
            papers=("doi", "nunique"),
            median_yield=("yield_percent", "median"),
            median_temp=("temperature_c", "median")),
        "by catalyst class": frame.groupby("catalyst class").agg(
            records=("doi", "size"),
            median_yield=("yield_percent", "median")).sort_values("records", ascending=False),
        "correlations": pd.DataFrame(correlations).set_index(["x", "y"]),
        "out of range": pd.DataFrame(out_of_range).T,
        "identity": {"pairs with both": len(both),
                     "yield above conversion": int(impossible),
                     "share impossible": impossible / len(both) if len(both) else 0},
    }


def main() -> None:
    sources(corpus="corpus_markdown", extraction=DATABASE)
    result = compute()

    show("records by route (assigned from the solvent)", result["by route"])
    show("records by catalyst class", result["by catalyst class"])
    show("relationships, Spearman rank correlation", result["correlations"])
    show("percentages that cannot be right", result["out of range"], fmt="{:.0f}")
    show("yield vs conversion, which is an identity not a correlation", result["identity"])


if __name__ == "__main__":
    main()
