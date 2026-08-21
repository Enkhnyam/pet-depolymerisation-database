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

CAPTION = r"""\textbf{What the database contains, and where it is thin.}
The corpus is shaped like the literature it came from: most papers report a handful of
experiments and a few report dozens (\textbf{a}, median __MEDIAN__, largest __LARGEST__), and
glycolysis outnumbers the other two routes together by two to one (\textbf{b}) --- which is why
the grader study was built on glycolysis, and why the transfer to methanolysis and hydrolysis is
assumed rather than measured.

What the records contain is uneven in a way that matters downstream. Reaction conditions are
almost always present, but outcomes frequently are not (\textbf{c}): selectivity appears in
__SELECTIVITY__\% of records. A blank here is the paper not reporting, not the extraction
failing, so it is a ceiling on what any model trained on this database could learn rather than a
defect we could fix by extracting harder. The catalyst field is the opposite problem --- not
missing but unbounded, with __CATALYSTS__ distinct names in a long tail (\textbf{d}), which is
precisely what defeats a grader that compares catalysts by spelling.

The two graders agree on roughly seven of every ten records of the curated papers (\textbf{e}),
with no human involved; the pair the database uses sits off the diagonal, so the judge never
grades its own output. Where the judge does intervene it is overwhelmingly on the three masses
(\textbf{f}), which papers state once in a methods paragraph and then vary implicitly down a
table. Those are the hardest fields in the schema to read correctly, and the same ones the metric
grader finds hardest --- the two graders fail in the same place, which is mild evidence they are
measuring the same thing."""


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    judged = verdicts_check.compute()
    agreement = matrix_check.compute()

    figure, panel = canvas(2, 3, width=8.4, height=5.0)

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

    fields = judged["fields"].head(9)
    fields.index = [str(name).replace("_", " ") for name in fields.index]
    bars(panel[5], fields, colour=VERDICT["corrected"], horizontal=True,
         xlabel="records the judge would change")

    save(figure, "fig1_database")
    print("\n" + caption(
        CAPTION,
        median=int(per_paper.median()), largest=int(per_paper.max()),
        selectivity=f"{completeness.min():.0f}", catalysts=chemistry["distinct catalysts"]))


if __name__ == "__main__":
    main()
