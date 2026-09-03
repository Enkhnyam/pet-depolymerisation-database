"""Figure 1 -- the database, and the judge's view of it.

Panels carry only their letter; what each is for belongs in the which this prints so it
can be pasted into the paper. Numbers come from the checks, which print the same values.
"""
from _style import (INK, ROUTE, ROUTES, WARN, bars, canvas, heatmap, ranked_bars,
                    save, step_hist)
from curated import matrix as matrix_check
from database import chemistry as chem
from database import corpus as corpus_check
from database import verdicts as verdicts_check


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    judged = verdicts_check.compute()
    agreement = matrix_check.compute()

    figure, panel = canvas(2, 3, height=4.22)

    per_paper = corpus["per paper"]
    # the caption quotes what database/corpus.py reports, rather than recomputing it here: the
    # check counts per *yielding* paper, and a median taken over a different set is a different
    # number that would silently disagree with scripts/checks.sh
    # bins follow the data: a fixed upper edge silently cropped the tail when the corpus grew,
    # leaving the panel stopping at 41 while the caption reported a largest paper of 84
    # log y: the count peaks at one record and runs to 84, so on a linear axis this panel was a
    # single spike over an empty box and the tail the caption quotes was invisible
    step_hist(panel[0], per_paper, bins=int(per_paper.max()), logy=True,
              xlabel="records per paper", ylabel="papers")

    # Named on the axis, not in the key. The three bars used to carry no tick labels and three
    # invisible bar(0, 0) proxies feeding the shared legend, so route was encoded in colour
    # alone -- and glycolysis teal against hydrolysis rose is the pair that fails deuteranopia
    # simulation. bars() hatches them as well, which is what carries the panel in greyscale.
    routes = chemistry["by route"]["records"].reindex(ROUTES).dropna()
    bars(panel[1], routes, colour=[ROUTE[name] for name in routes.index], ylabel="records")

    completeness = chemistry["completeness"] * 100
    ranked_bars(panel[2], completeness, xlabel="records reporting it (%)", fmt="{:.0f}%")

    # "none" -- the uncatalysed baselines -- is the largest single group and that is the finding,
    # so it is the one accented bar rather than another shade of the same grey
    ranked_bars(panel[3], chemistry["catalysts"].head(10), accent=INK, xlabel="records")

    heatmap(panel[4], agreement.pivot(index="judge", columns="extraction", values="agreement"),
            xlabel="extraction", ylabel="judge")

    fields = judged["fields"].head(9)
    fields.index = [str(name).replace("_", " ") for name in fields.index]
    ranked_bars(panel[5], fields, accent=WARN, xlabel="records changed")

    save(figure, "fig1_database")


if __name__ == "__main__":
    main()
