"""Figure 2 -- what the extracted conditions look like, and whether they behave.

Distributions rather than scatters: with five thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The exceptions are the last two panels, where the relationship is the point.
"""
from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, density, histogram,
                    legend_above, overlap, save)
from curated import gao_overlap
from database import chemistry as chem


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(3, 3, height=5.73)

    histogram(panel[0], frame, "temperature_c", xlabel="temperature (°C)", **stack)
    histogram(panel[1], frame, "reaction_time_min", logx=True, ylabel="",
              xlabel="reaction time (min)", **stack)
    # a handful of yields exceed 100%; letting them set the axis wastes the panel
    histogram(panel[2], frame[frame.yield_percent <= 100], "yield_percent",
              xlabel="yield (%)", ylabel="", **stack)
    # from the check, not recounted: chemistry.py already publishes this and the two definitions
    # must not be allowed to drift apart
    histogram(panel[3], frame, "conversion_percent", xlabel="conversion (%)", **stack)
    histogram(panel[4], frame, "catalyst_amount_g", logx=True, xlabel="catalyst (g)",
              ylabel="", **stack)
    histogram(panel[5], frame, "PET_amount_g", logx=True, xlabel="PET (g)", ylabel="", **stack)
    histogram(panel[6], frame, "solvent_amount_g", logx=True, xlabel="solvent (g)", **stack)

    # A binned density, not a cloud of 1,400 translucent dots. The claim is that nothing sits
    # above the diagonal -- an identity, so it holds route by route trivially and needs no route
    # split -- and a density shows where the mass is, which an overplotted cloud cannot. The
    # diagonal is a solid hairline: it is a reference, and a dashed one read as data.
    density(panel[7], frame, "conversion_percent", "yield_percent",
            xlabel="conversion (%)", ylabel="yield (%)", xlim=(0, 100), ylim=(0, 100))
    panel[7].plot([0, 100], [0, 100], color=INK, lw=0.8, zorder=3)

    # Panel i: do our extracted conditions and hand curation cover the same ground? Three
    # regions -- ours alone, theirs alone, and where they coincide -- each the smallest area
    # holding 90% of that set's own experiments. Regions and not dots because temperature piles
    # onto the round values experimenters choose, 150, 160, 180, 190, 200, so a scatter of the
    # two sets came out as columns of marks and hid the overlap, which is all the panel is for.
    space = gao_overlap.compute()["condition space"]
    ours, curated = space["this work"], space["hand-curated"]
    overlap(panel[8],
            (ours.temperature_c, ours.yield_percent),
            (curated.temperature_c, curated.yield_percent),
            xlim=(140, 215), ylim=(0, 100))
    panel[8].set_xlabel("temperature (°C)")
    panel[8].set_ylabel("yield (%)")
    # Above the axes, on one line, each in the colour of the region it names. Inside the panel
    # there is nowhere to put three labels: the regions reach both the top and the bottom of the
    # yield axis, and a top-left placement sat on the fill.
    #
    # Positions are measured rather than guessed. Hand-picked offsets ran the three labels into
    # each other and into the panel letter, because how wide "hand-curated only" is at 5.2 pt is
    # not something to estimate.
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    left = 0.075                      # clear of the bold panel letter
    for text, colour in (("both", RAMP[0]), ("this work only", RAMP[3]),
                         ("hand-curated only", RAMP[2])):
        drawn = panel[8].annotate(text, (left, 1.02), xycoords="axes fraction", fontsize=5.2,
                                  color=colour, fontweight="bold", va="bottom")
        box = drawn.get_window_extent(renderer)
        edges = panel[8].transAxes.inverted().transform([(0, 0), (box.width, 0)])
        left += edges[1][0] - edges[0][0] + 0.035

    legend_above(figure, panel[0])
    save(figure, "fig2_chemistry")


if __name__ == "__main__":
    main()
