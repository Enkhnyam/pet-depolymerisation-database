"""Figure 2 -- what the extracted conditions look like.

Distributions rather than scatters: with two thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The one exception is the identity panel, where the relationship is the point.
"""
from _style import (ROUTE, ROUTES, WARN, canvas, caption, histogram, legend_above,
                    note, points, save)
from database import chemistry as chem

CAPTION = r"""\textbf{The conditions the corpus reports.} Stacked by route.
(a) Temperature is sharply peaked near 190--200\,\textdegree C, the range where ethylene glycol
refluxes; the tail past 400\,\textdegree C is mostly hydrolysis under pressure.
(b) Reaction time spans four orders of magnitude, clustering at the round numbers experimenters
choose --- 30, 60, 120 minutes --- which is a signature of real protocols rather than of
extraction noise. (c) Yields pile up against 100\%, as one expects from a literature that reports optimised
runs; __OVER__ records exceed 100\% and are impossible, a small but real error rate. (d) Conversion behaves the same way and is reported for __CONVERSION__\% of
records. (e) Catalyst loading covers six orders of magnitude, from milligrams to bulk solvent
quantities; a schema field that spans this range is one where a 20\% numeric tolerance means very
different things at either end. (f, g) PET and solvent charges, again heavily rounded.
(h) The one relationship worth a scatter, because it is an identity rather than a correlation:
yield cannot exceed conversion, so nothing may sit above the diagonal.
\textbf{Only __IMPOSSIBLE__ of __PAIRS__ records do} --- an internal consistency check the data
passes without having been told to."""


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(2, 4, width=9.4, height=4.8)

    histogram(panel[0], frame, "temperature_c", xlabel="temperature (°C)", **stack)
    histogram(panel[1], frame, "reaction_time_min", logx=True, xlabel="reaction time (min)",
              **stack)
    # a handful of yields exceed 100%; letting them set the axis wastes the panel
    histogram(panel[2], frame[frame.yield_percent <= 100], "yield_percent",
              xlabel="yield (%)", **stack)
    over = int((frame.yield_percent > 100).sum())
    note(panel[2], f"{over} above 100%, off scale", x=0.97, y=0.9, ha="right")
    histogram(panel[3], frame, "conversion_percent", xlabel="conversion (%)", **stack)
    histogram(panel[4], frame, "catalyst_amount_g", logx=True, xlabel="catalyst (g)", **stack)
    histogram(panel[5], frame, "PET_amount_g", logx=True, xlabel="PET (g)", **stack)
    histogram(panel[6], frame, "solvent_amount_g", logx=True, xlabel="solvent (g)", **stack)

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
