"""Figure 1 -- the database, and the judge's view of it.

Panels carry only their letter; what each is for belongs in the caption, which this prints so it
can be pasted into the paper. Numbers come from the checks, which print the same values.
"""
import pandas as pd

from _style import ROUTE, ROUTES, VERDICT, bars, canvas, caption, heatmap, save
from curated import matrix as matrix_check
from database import chemistry as chem
from database import corpus as corpus_check
from database import verdicts as verdicts_check

REACHABLE = "#0E7C6B"

CAPTION = r"""\textbf{What the database contains, and what the judge made of it.}
(a) Most papers report a handful of experiments and a few report dozens: the median is __MEDIAN__
and the largest single paper gives __LARGEST__. (b) Glycolysis dominates, which is why the grader
study was built on it; the other two routes together are under a third of the records.
(c) Conditions are almost always reported and outcomes often are not --- catalyst and solvent
appear in essentially every record, selectivity in __SELECTIVITY__\%. A blank is the literature
not reporting, not a failed extraction, and it bounds what any downstream model can learn.
(d) __CATALYSTS__ distinct catalyst names, the commonest being no catalyst at all; the long tail is
why a grader that compares catalyst names by spelling struggles here. (e) Judge against metric on
every record of the curated papers, no human involved: the pair the database uses sits off the
diagonal, so the judge never grades its own output. (f) On the database itself the judge accepts
__ACCEPTED__\% of records outright. (g) What it corrects is dominated by the three masses, which
are typically stated once in a methods paragraph and then varied implicitly down a table --- the
hardest thing in this schema to read correctly, and the same fields the metric grader finds
hardest."""


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    judged = verdicts_check.compute()
    agreement = matrix_check.compute()

    figure, panel = canvas(2, 4, width=9.4, height=4.8)

    per_paper = corpus["per paper"]
    panel[0].hist(per_paper, bins=range(1, 42), color=REACHABLE)
    panel[0].set_xlabel("records per paper")
    panel[0].set_ylabel("papers")

    routes = chemistry["by route"]["records"].reindex(ROUTES).dropna()
    bars(panel[1], routes, colour=[ROUTE[name] for name in routes.index], ylabel="records")
    panel[1].tick_params(axis="x", labelrotation=30)

    completeness = chemistry["completeness"] * 100
    bars(panel[2], completeness, colour=REACHABLE, horizontal=True,
         xlabel="% of records reporting it")

    bars(panel[3], chemistry["catalysts"].head(10), colour=REACHABLE, horizontal=True,
         xlabel="records")

    heatmap(panel[4], agreement.pivot(index="judge", columns="extraction", values="agreement"),
            xlabel="extraction", ylabel="judge")

    counts = {k: v for k, v in judged["counts"].items() if k != "records judged"}
    series = pd.Series(counts)
    series.index = ["accepted", "corrected", "dropped"]
    bars(panel[5], series, colour=[VERDICT[name] for name in series.index], ylabel="records")

    fields = judged["fields"].head(9)
    fields.index = [str(name).replace("_", " ") for name in fields.index]
    bars(panel[6], fields, colour=VERDICT["corrected"], horizontal=True,
         xlabel="records the judge would change")

    panel[7].set_title("")          # no letter over an empty cell
    panel[7].axis("off")

    save(figure, "fig1_database")
    print("\n" + caption(
        CAPTION,
        median=int(per_paper.median()), largest=int(per_paper.max()),
        selectivity=f"{completeness.min():.0f}", catalysts=chemistry["distinct catalysts"],
        accepted=f"{100 * series['accepted'] / series.sum():.0f}"))


if __name__ == "__main__":
    main()
