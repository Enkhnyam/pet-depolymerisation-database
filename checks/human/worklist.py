"""Which records the next adjudication round should use, and how many.

The question changed, so the sampling has to. McNemar needed disagreements; precision and recall
need a sample you can weight back to the population, and a disagreements-only sample cannot be.

It also changed which bundle makes sense. On the 24 curated papers the shipped judge flags only
15 records out of 296 -- labelling every one of them would still leave its precision uncertain to
about a fifth. On the database it flags 590 of 2128, which is enough to measure. The cost is that
the database has no curated answer key, so this round measures the judge alone, not the judge
against the metric. That is the right trade: the judge is what vouches for the database, and the
database is what the paper makes claims about.

Stratified, not random: sampling 120 records at random would catch about 33 flagged ones. Drawing
the two strata separately and reweighting gives the same budget far more information about the
half that matters.
"""
import numpy as np
import pandas as pd

from _setup import DATABASE, DATABASE_JUDGE, judged, records, show, sources

PER_STRATUM = 60          # flagged and accepted alike; 120 decisions in total
SEED = 20260821


def compute() -> pd.DataFrame:
    """The sample to adjudicate, with the stratum weight each record carries."""
    verdicts = judged(run=DATABASE_JUDGE)
    extracted = records(DATABASE)[["doi", "index", "catalyst", "temperature_c",
                                   "reaction_time_min", "yield_percent"]]
    frame = verdicts.merge(extracted, on=["doi", "index"])
    frame["stratum"] = np.where(frame.judge == "incorrect", "judge flagged", "judge accepted")

    generator = np.random.default_rng(SEED)
    chosen = []
    for name, group in frame.groupby("stratum"):
        take = min(PER_STRATUM, len(group))
        picked = group.iloc[generator.choice(len(group), take, replace=False)].copy()
        # what one labelled record stands for, so the strata can be weighted back together
        picked["weight"] = len(group) / take
        chosen.append(picked)

    return pd.concat(chosen).sort_values(["doi", "index"]).reset_index(drop=True)


def main() -> None:
    sources(extraction=DATABASE, judge=DATABASE_JUDGE)

    verdicts = judged(run=DATABASE_JUDGE)
    flagged = int((verdicts.judge == "incorrect").sum())
    show("the population this round samples", {
        "records in the database": len(verdicts),
        "the judge flagged": flagged,
        "the judge accepted": len(verdicts) - flagged,
    }, fmt="{:.0f}")

    sample = compute()
    show("the sample", sample.groupby("stratum").agg(
        records=("doi", "size"), papers=("doi", "nunique"),
        stands_for=("weight", "first")), fmt="{:.1f}")

    print(f"\n{len(sample)} decisions, spread over {sample.doi.nunique()} papers")

    # what that budget buys, on the stratum each quantity is estimated from
    half = lambda n, p=0.7: 1.96 * np.sqrt(p * (1 - p) / n)
    show("half-width of a 95% interval, for a rate near 0.7", {
        "judge precision (from the flagged stratum)": half(PER_STRATUM),
        "human rejection rate among accepted": half(PER_STRATUM),
    }, fmt="{:.2f}")
    print("\n  recall and F1 follow from those two, reweighted by the stratum sizes above.")


if __name__ == "__main__":
    main()
