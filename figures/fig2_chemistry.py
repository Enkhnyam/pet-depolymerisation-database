"""Figure 2 -- what the extracted conditions look like.

Distributions rather than scatters: with two thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The one exception is the identity panel, where the relationship is the point.
"""
from _style import (ROUTE, ROUTES, WARN, canvas, caption, histogram, legend_above,
                    note, points, save)
from database import chemistry as chem

CAPTION = r"""\textbf{The conditions the corpus reports, stacked by route.} Counts are records
throughout; only the leftmost panel in each row is labelled.


The corpus looks like chemistry, which is the only check available on data nobody curated.
Temperature is sharply peaked at 190--200\,\textdegree C (\textbf{a}), where ethylene glycol
refluxes, with a thin tail past 400\,\textdegree C that is mostly pressurised hydrolysis.
Reaction times span four orders of magnitude but cluster on the round numbers experimenters
actually choose --- 30, 60, 120 minutes (\textbf{b}) --- a signature of real protocols rather
than of a model inventing plausible values.

The outcome fields behave as a literature of optimised runs should: yields and conversions pile
up against 100\% (\textbf{c}, \textbf{d}). They also expose the error rate. \textbf{__OVER__
records report a yield above 100\%}, which is impossible, and conversion is reported for only
__CONVERSION__\% of records.

The three charge fields (\textbf{e}--\textbf{g}) each span five or six orders of magnitude, from
milligrams of catalyst to bulk solvent. That range is worth noting because the metric grader
accepts numbers within 20\%, and 20\% means something very different at the two ends of a
six-decade axis.

The last panel is the one real test. Yield cannot exceed conversion --- it is an identity, not a
correlation --- so nothing may sit above the diagonal (\textbf{h}). \textbf{Only __IMPOSSIBLE__
of __PAIRS__ records do.} Nothing in the prompt or the schema enforces that relationship, so the
extraction is reproducing a constraint of the chemistry rather than merely of its instructions."""


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(2, 4, width=9.4, height=4.8)

    histogram(panel[0], frame, "temperature_c", xlabel="temperature (°C)", **stack)
    histogram(panel[1], frame, "reaction_time_min", logx=True, ylabel="",
              xlabel="reaction time (min)", **stack)
    # a handful of yields exceed 100%; letting them set the axis wastes the panel
    histogram(panel[2], frame[frame.yield_percent <= 100], "yield_percent",
              xlabel="yield (%)", ylabel="", **stack)
    over = int((frame.yield_percent > 100).sum())
    note(panel[2], f"{over} above 100%, off scale", x=0.97, y=0.9, ha="right")
    histogram(panel[3], frame, "conversion_percent", xlabel="conversion (%)", ylabel="", **stack)
    histogram(panel[4], frame, "catalyst_amount_g", logx=True, xlabel="catalyst (g)", **stack)
    histogram(panel[5], frame, "PET_amount_g", logx=True, xlabel="PET (g)", ylabel="", **stack)
    histogram(panel[6], frame, "solvent_amount_g", logx=True, xlabel="solvent (g)", ylabel="", **stack)

    points(panel[7], frame, "conversion_percent", "yield_percent",
           colour_by="route", palette=ROUTE, order=ROUTES,
           xlabel="conversion (%)", ylabel="yield (%)")
    panel[7].plot([0, 100], [0, 100], color=WARN, lw=1, ls="--", zorder=3)

    legend_above(figure, panel[0])
    save(figure, "fig2_chemistry")

    identity = result["identity"]
    print("\n" + caption(
        CAPTION,
        conversion=f"{100 * frame.conversion_percent.notna().mean():.0f}",
        over=int((frame.yield_percent > 100).sum()),
        impossible=identity["yield above conversion"], pairs=identity["pairs with both"]))


if __name__ == "__main__":
    main()
