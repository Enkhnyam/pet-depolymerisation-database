"""Does the chemistry appear when each paper is compared with itself?

Pooled across the corpus, temperature and yield are uncorrelated (rho = +0.02 over 2,742
records), and so is everything else you would expect to move together. Taken at face value that
says the database is noise.

It is not. Pooling is the wrong operation. Each paper reports a handful of runs around whatever
optimum that lab chose, on its own PET feedstock, catalyst and scale, so the between-paper
spread swamps the within-paper trend -- Simpson's paradox, in a corpus assembled from optimised
experiments. Comparing a paper only against itself removes the lab as a variable, and the
expected relationships reappear: hotter runs give more, more catalyst gives more, and hotter runs
finish sooner.

This is the strongest available check on data nobody curated. Nothing in the prompt or the schema
mentions these relationships, so an extraction that invented plausible-looking numbers would have
no reason to reproduce them paper by paper while showing nothing in the pooled view.

A paper counts only when it reports at least MIN_RECORDS runs with both fields and genuinely
varies both -- a paper that ran everything at 190 degC says nothing about temperature. The test is
a Wilcoxon signed-rank on the per-paper correlations against zero, which asks whether papers lean
the same way rather than whether any single paper is individually significant.
"""
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from _setup import DATABASE, records, show, sources
from database.chemistry import compute as chemistry

# Below five runs a rank correlation is mostly noise; below three distinct values on either axis
# the paper did not vary the thing being tested.
MIN_RECORDS = 5
MIN_DISTINCT = 3

# Each pair is a relationship chemistry predicts the sign of, stated as the expectation.
PAIRS = [
    ("temperature_c", "yield_percent", "hotter gives more", +1),
    ("catalyst_amount_g", "yield_percent", "more catalyst gives more", +1),
    ("temperature_c", "reaction_time_min", "hotter finishes sooner", -1),
    ("reaction_time_min", "yield_percent", "longer gives more", +1),
]


def per_paper(frame: pd.DataFrame, x: str, y: str) -> pd.Series:
    """Spearman rho within each paper that varied both fields enough to have an opinion."""
    found = {}
    for doi, group in frame.groupby("doi"):
        pair = group[[x, y]].dropna()
        if len(pair) < MIN_RECORDS:
            continue
        if pair[x].nunique() < MIN_DISTINCT or pair[y].nunique() < MIN_DISTINCT:
            continue
        rho = pair[x].corr(pair[y], method="spearman")
        if pd.notna(rho):
            found[doi] = rho
    return pd.Series(found, dtype=float)


def compute() -> dict:
    frame = chemistry()["records"]

    rows, curves = [], {}
    for x, y, expectation, sign in PAIRS:
        pooled = frame[[x, y]].dropna()
        rho_pooled = pooled[x].corr(pooled[y], method="spearman")
        rhos = per_paper(frame, x, y)
        curves[expectation] = rhos
        agree = float((np.sign(rhos) == sign).mean()) if len(rhos) else np.nan
        rows.append({
            "relationship": expectation,
            "x": x, "y": y, "expected": "+" if sign > 0 else "-",
            "pooled": rho_pooled, "pooled n": len(pooled),
            "within": rhos.median() if len(rhos) else np.nan,
            "papers": len(rhos),
            "as predicted": agree,
            # against zero, not against the pooled value: the question is whether papers lean
            # the same way at all, which is what pooling destroys
            "p": wilcoxon(rhos).pvalue if len(rhos) > 8 else np.nan,
        })

    return {"table": pd.DataFrame(rows).set_index("relationship"),
            "per paper": curves, "records": frame}


def main() -> None:
    sources(corpus="corpus_markdown", extraction=DATABASE)
    result = compute()

    table = result["table"].copy()
    table["as predicted"] = (table["as predicted"] * 100).round(0)
    # p is formatted, not rounded: these run to 1e-06 and .round() would print every one as 0.000
    table["p"] = table["p"].map(lambda v: "-" if pd.isna(v) else f"{v:.1e}")
    show("pooled across the corpus vs within each paper (Spearman rho)",
         table[["expected", "pooled", "pooled n", "within", "papers", "as predicted", "p"]]
         .round({"pooled": 3, "within": 3}))

    print("\n'within' is the median of the per-paper correlations; 'as predicted' is the share of")
    print("papers whose sign matches the expectation. A relationship that is flat pooled and")
    print("consistent within papers is one the corpus reproduces and the pooled view hides.")

    lead = result["table"].loc["hotter gives more"]
    print(f"\ntemperature and yield: pooled {lead['pooled']:+.3f} over {int(lead['pooled n'])} "
          f"records, {lead['within']:+.3f} within each of {int(lead['papers'])} papers")


if __name__ == "__main__":
    main()
