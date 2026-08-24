"""Figure 1 -- the database, and the judge's view of it.

Panels carry only their letter; what each is for belongs in the caption, which this prints so it
can be pasted into the paper. Numbers come from the checks, which print the same values.
"""
import pandas as pd

from _style import (NEUTRAL, ROUTE, ROUTES, bars, canvas, caption, heatmap,
                    legend_above, save)
from curated import matrix as matrix_check
from database import chemistry as chem
from database import corpus as corpus_check
from database import verdicts as verdicts_check

# every panel but (b) counts something uncategorised, so only (b) spends colour, and the
# route key above the canvas can only be read as belonging to it
REACHABLE = NEUTRAL

CAPTION = r"""\textbf{What the database contains, and where it is thin.}
The corpus is shaped like the literature it came from: most papers report a handful of
experiments and a few report dozens (\textbf{a}, median __MEDIAN__, largest __LARGEST__), and
glycolysis outnumbers hydrolysis and methanolysis combined by __RATIO__ to one (\textbf{b}) ---
which is why the grader study was built on glycolysis, and why the transfer to the other two
routes is assumed rather than measured.

What the records contain is uneven in a way that matters downstream. Reaction conditions are
almost always present, but outcomes frequently are not (\textbf{c}): selectivity appears in
__SELECTIVITY__\% of records. A blank here is the paper not reporting, not the extraction
failing, so it is a ceiling on what any model trained on this database could learn rather than a
defect we could fix by extracting harder. The catalyst field is the opposite problem --- not
missing but unbounded, with __CATALYSTS__ distinct names in a long tail (\textbf{d}), which is
precisely what defeats a grader that compares catalysts by spelling.

The two graders agree on roughly seven of every ten records of the curated papers (\textbf{e}),
with no human involved; the pair the database uses sits off the diagonal, so the judge never
grades its own output. Where the judge does intervene, the two fields it rewrites most are the
catalyst and solvent charges (\textbf{f}, __TOPFIELD__ and __SECONDFIELD__ records), which
papers state once in a methods paragraph and then vary implicitly down a table. Those are the
hardest fields in the schema to read correctly, and the same ones the metric grader finds
hardest --- the two graders fail in the same place, which is mild evidence they are measuring the
same thing."""


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    judged = verdicts_check.compute()
    agreement = matrix_check.compute()

    figure, panel = canvas(2, 3, width=8.4, height=5.0)

    per_paper = corpus["per paper"]
    # bins follow the data: a fixed upper edge silently cropped the tail when the corpus grew,
    # leaving the panel stopping at 41 while the caption reported a largest paper of 84
    panel[0].hist(per_paper, bins=range(1, int(per_paper.max()) + 2), color=REACHABLE)
    panel[0].set_xlabel("records per paper")
    panel[0].set_ylabel("papers")

    # the route colours carry the same meaning here as in Figure 2, so they get the same key
    # rather than rotated tick labels: one legend read once serves both figures
    routes = chemistry["by route"]["records"].reindex(ROUTES).dropna()
    bars(panel[1], routes, colour=[ROUTE[name] for name in routes.index], ylabel="records")
    panel[1].set_xticks(range(len(routes)), [""] * len(routes))
    for name in routes.index:
        panel[1].bar(0, 0, color=ROUTE[name], label=name)

    completeness = chemistry["completeness"] * 100
    bars(panel[2], completeness, colour=REACHABLE, horizontal=True,
         xlabel="% of records reporting it")

    bars(panel[3], chemistry["catalysts"].head(10), colour=REACHABLE, horizontal=True,
         xlabel="records")

    heatmap(panel[4], agreement.pivot(index="judge", columns="extraction", values="agreement"),
            xlabel="extraction", ylabel="judge")

    fields = judged["fields"].head(9)
    fields.index = [str(name).replace("_", " ") for name in fields.index]
    bars(panel[5], fields, colour=NEUTRAL, horizontal=True,
         xlabel="records the judge would change")

    legend_above(figure, panel[1])
    save(figure, "fig1_database", legend_room=True)
    print("\n" + caption(
        CAPTION,
        median=int(per_paper.median()), largest=int(per_paper.max()),
        selectivity=f"{completeness.min():.0f}",
        catalysts=f"{chemistry['distinct catalysts']:,}",
        ratio=f"{routes['glycolysis'] / routes.drop('glycolysis').sum():.1f}",
        topfield=int(fields.iloc[0]), secondfield=int(fields.iloc[1])))


if __name__ == "__main__":
    main()
