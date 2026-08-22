"""Which records the next adjudication round should use, and how many.

The round runs on the 24 curated papers, not on the database. That is forced: the metric grader
has no verdict without a curated answer key, and comparing the two graders is the whole argument.
Adjudicating database records would measure the judge alone and leave the metric unevaluated,
which would mean curating a second answer key to get it back.

The question changed from McNemar to precision and recall, so the sampling has to. McNemar needed
disagreements; precision and recall need a sample that can be weighted back to the population, and
a disagreements-only sample cannot be.

Stratified over the four grader cells. The two cells where the judge flags a record are small
enough to take whole -- the shipped judge flags very little -- so its precision is estimated from
every such record that exists, and the interval around it is as tight as this bundle allows. The
two large cells are sampled and reweighted.
"""
import numpy as np
import pandas as pd

from _setup import RUNS_DIR, judged, records, scored, show, sources

JUDGE, TARGET = "oss", "luna"        # the pair the database ships
BUDGET = 120
SEED = 20260821

EXTRACTION = RUNS_DIR / f"extract_{TARGET}/extract_{TARGET}_n4_r1"
VERDICTS = RUNS_DIR / f"judge_{JUDGE}_on_{TARGET}/judge_{JUDGE}_on_{TARGET}"


def cells() -> pd.DataFrame:
    """Every record of the benchmark, labelled with which graders flagged it."""
    both = scored(run=EXTRACTION).merge(judged(run=VERDICTS), on=["doi", "index"])
    both["cell"] = np.select(
        [(both.metric == "incorrect") & (both.judge == "incorrect"),
         (both.metric == "correct") & (both.judge == "incorrect"),
         (both.metric == "incorrect") & (both.judge == "correct")],
        ["both flag", "judge only", "metric only"], default="neither flags")
    return both


def compute() -> pd.DataFrame:
    """The sample to adjudicate, with the weight each labelled record carries."""
    frame = cells()
    sizes = frame.cell.value_counts()

    # take the judge-flagged cells whole; they are small and they are the only place the judge's
    # precision can be estimated at all
    whole = [name for name in ("both flag", "judge only") if name in sizes]
    taken = int(sizes[whole].sum())
    remaining = max(BUDGET - taken, 0)

    large = [name for name in ("metric only", "neither flags") if name in sizes]
    share = {name: int(round(remaining * sizes[name] / sizes[large].sum())) for name in large}

    generator = np.random.default_rng(SEED)
    chosen = []
    for name, group in frame.groupby("cell"):
        take = len(group) if name in whole else min(share.get(name, 0), len(group))
        if not take:
            continue
        picked = group.iloc[generator.choice(len(group), take, replace=False)].copy()
        picked["weight"] = len(group) / take      # what one labelled record stands for
        chosen.append(picked)

    columns = ["doi", "index", "cell", "weight"]
    return pd.concat(chosen).sort_values(["doi", "index"])[columns].reset_index(drop=True)


def main() -> None:
    sources(extraction=EXTRACTION, judge=VERDICTS)

    frame = cells()
    show(f"the population, {JUDGE} judging {TARGET} on the curated papers",
         pd.crosstab(frame.metric, frame.judge), fmt="{:.0f}")

    sample = compute()
    summary = sample.groupby("cell").agg(sampled=("doi", "size"), stands_for=("weight", "first"))
    summary["in population"] = frame.cell.value_counts()
    show("the sample", summary[["in population", "sampled", "stands_for"]], fmt="{:.1f}")
    print(f"\n{len(sample)} decisions across {sample.doi.nunique()} papers")

    half = lambda n, p=0.7: 1.96 * np.sqrt(p * (1 - p) / n)
    flagged_judge = int(frame.cell.isin(["both flag", "judge only"]).sum())
    flagged_metric = int(sample.cell.isin(["both flag", "metric only"]).sum())
    show("half-width of a 95% interval, for a rate near 0.7", {
        "judge precision": half(flagged_judge),
        "metric precision": half(flagged_metric),
    }, fmt="{:.2f}")
    print(f"\n  the judge flags only {flagged_judge} records in the whole benchmark, so its")
    print("  precision cannot be pinned down more tightly than that on this bundle -- which is")
    print("  itself worth reporting: a grader that rarely objects is hard to characterise.")


if __name__ == "__main__":
    main()
