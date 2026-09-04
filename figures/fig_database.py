"""What the database contains, and where it is thin.

Five panels. The judge x extraction agreement grid used to sit here as a sixth, which put a
grader result inside the database figure; it belongs with the other grader panels and is in
fig_graders now.

Two things in here are answers to being asked what a panel meant, and both were defects rather
than explanations:

  The records-per-paper panel was drawn on a log y axis, so a reader could not read a count off
  it. It is linear over the full range now -- one spike at a single record and a tail to 84 --
  which is what the distribution honestly looks like.

  The catalyst panel ranked *spellings*. frame.catalyst.value_counts() counts strings, and the
  literature writes zinc acetate at least five ways; between them those spellings hold more
  records than sodium hydroxide, while each one holds fewer. So the panel put NaOH first and
  zinc acetate fourth, which is the wrong catalyst. It groups by resolved structure now, via
  the curated lookup core.smiles already carries.
"""
from _style import (EMPHASIS, ROUTE, canvas, headroom, pie, ranked_bars, save, step_hist)
from core.schema import OTHER_ROUTE
from database import chemistry as chem
from database import corpus as corpus_check
from database import verdicts as verdicts_check


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    judged = verdicts_check.compute()

    figure, panel = canvas(2, 3, height=4.22)

    # --- a: how many experiments a paper reports ---------------------------------------------
    # Linear, full range, top tick above the peak. Bins follow the data: a fixed upper edge
    # silently cropped the tail when the corpus grew.
    per_paper = corpus["per paper"]
    step_hist(panel[0], per_paper, bins=int(per_paper.max()),
              xlabel="experiments reported per paper", ylabel="papers")
    counts, _ = __import__("numpy").histogram(per_paper, bins=int(per_paper.max()))
    headroom(panel[0], float(counts.max()))

    # --- b: which route, as a part of the whole ----------------------------------------------
    # A pie, because every record has exactly one route and the four sum to the database. The
    # unassigned share is the point of including it: route is inferred from the solvent, so a
    # solvent written unusually lands in "other" rather than being dropped.
    routes = chemistry["by route"]["records"]
    ordered = routes.reindex([name for name in ROUTE if name in routes.index]).dropna()
    # The routes are named in full. They were abbreviated to gly/hyd/met to buy back the width
    # the labels cost, and "met" is not a word a reader of a chemistry paper should have to
    # decode; the count and the share moved to a second line instead, which is where the width
    # actually was.
    names = {OTHER_ROUTE: "unassigned"}
    ordered.index = [names.get(name, str(name)) for name in ordered.index]
    pie(panel[1], ordered, colours=[ROUTE[name] for name in routes.index if name in ROUTE],
        title=f"route, of {int(ordered.sum()):,} records")

    # --- c: how often each field is reported at all ------------------------------------------
    ranked_bars(panel[2], chemistry["completeness"] * 100,
                xlabel="records reporting the field (%)", fmt="{:.0f}%")

    # --- d: the commonest catalysts, by substance --------------------------------------------
    # "none" is the uncatalysed baselines and the largest single group, which is the finding, so
    # it takes the dark end of the ramp. Emphasis by weight, not by a second hue.
    ranked_bars(panel[3], chemistry["substances"].head(10), accent=EMPHASIS,
                xlabel="records (catalysts grouped by structure)")

    # --- e: what the judge rewrote -----------------------------------------------------------
    fields = judged["fields"].head(9)
    fields.index = [str(name).replace("_", " ") for name in fields.index]
    ranked_bars(panel[4], fields, accent=EMPHASIS,
                xlabel="records whose field the judge corrected")

    # --- f: what stops a record getting a route ----------------------------------------------
    # The unassigned slice in (b) is the largest thing on this figure that is nobody's finding,
    # and this is the panel that makes it actionable: route is read off the solvent, so every
    # unrouted record has a solvent the rules do not recognise. Naming them is what shortens
    # the list -- DEG and H2O were 178 records until the rules learned the abbreviations.
    unrouted = chemistry["unrouted solvents"].head(9)
    ranked_bars(panel[5], unrouted, accent=EMPHASIS,
                xlabel=f"solvent, {int(chemistry['unrouted solvents'].sum()):,} unrouted")

    save(figure, "fig_database")


if __name__ == "__main__":
    main()
