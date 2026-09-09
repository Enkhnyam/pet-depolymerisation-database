"""Figure 2 -- what the extracted conditions look like, and whether they behave.

Distributions rather than scatters: with five thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The exceptions are the last two panels, where the relationship is the point.
"""
from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, cloud, headroom, histogram,
                    legend_above, overlap, save, stack_tops)
from curated import gao_overlap
from database import chemistry as chem


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(3, 3, height=5.73)

    # --- a-g: the conditions the corpus reports, one field per panel -----------------------
    # Three changes from the version before this one, all asked for:
    #
    #   No log x. Four of these fields span six decades -- PET runs to 2.4 tonnes against a
    #   median of 3 g -- so a linear axis over the whole range is a spike at zero. They are
    #   linear and truncated at the 90th percentile instead, which is stated once in the caption
    #   rather than seven times on the panels.
    #
    #   The record count sits on the axis label, not on a second line: "temperature (°C), n=4,844".
    #   The counts differ by a factor of two across these panels and that is the answer to why
    #   temperature is in the thousands and solvent is not -- it is coverage, not a choice.
    #
    #   headroom() puts the top tick at or above the tallest stack, which matplotlib does not:
    #   it picks ticks to span the data, so a 631-record column under a 600 tick is the default
    #   and a reader cannot read the peak off the axis.
    # All seven are histograms, and they are histograms after three other chart types were
    # drawn and rejected here -- cumulative curves, quantile rows, violins. The shape is what a
    # reader of these panels wants, and the four skewed fields are handled the way (b) already
    # was: the tail is cut at a stated percentile rather than transformed. No log axis anywhere.
    shapes = [(0, "temperature_c", "temperature (°C)", None, frame),
              (1, "reaction_time_min", "reaction time (min)", 0.90, frame),
              (2, "yield_percent", "yield (%)", None, frame[frame.yield_percent <= 100]),
              (3, "conversion_percent", "conversion (%)", None,
               frame[frame.conversion_percent <= 100]),
              (4, "catalyst_amount_g", "catalyst (g)", 0.90, frame),
              (5, "PET_amount_g", "PET (g)", 0.90, frame),
              (6, "solvent_amount_g", "solvent (g)", 0.90, frame)]
    for index, column, label, clip, source in shapes:
        reported = int(source[column].notna().sum())
        histogram(panel[index], source, column, clip=clip,
                  xlabel=f"{label}, n={reported:,}",
                  ylabel="records" if index % 3 == 0 else "", **stack)
        headroom(panel[index], stack_tops(panel[index]))

    # --- h: yield against conversion, an identity the data has to obey ---------------------
    # 1,423 records is a scatter, not a density. The density was here because five thousand
    # points elsewhere on this page are ink rather than information -- but only the records
    # reporting both metrics land in this panel, and at that count the marks separate. It also
    # cost a key: a shaded panel has to say what the shade counts, and the ramp is spending
    # itself on route in the seven panels around it. Dots need no key, and the claim reads off
    # them directly -- the twenty-eight above the line are twenty-eight marks, not a pale haze.
    pair = frame[["conversion_percent", "yield_percent"]].dropna()
    cloud(panel[7], pair.conversion_percent, pair.yield_percent, colour=RAMP[2], size=1.4)
    panel[7].set_xlim(0, 100)
    panel[7].set_ylim(0, 100)
    panel[7].set_xlabel("conversion (%)")
    panel[7].set_ylabel("yield (%)")
    # A casing under the reference: unavoidably it runs through the densest part of the cloud,
    # and 0.35 pt of white a side is what keeps it a line rather than one more mark.
    panel[7].plot([0, 100], [0, 100], color="white", lw=1.5, zorder=3)
    panel[7].plot([0, 100], [0, 100], color=INK, lw=0.8, zorder=4)

    # The rounding allowance is drawn but not annotated. 40 marks sit above y = x and the check
    # counts 28, because it allows one percentage point for the rounding in the source papers;
    # both numbers belong in the caption, which is where they now are. The dashed line is the
    # allowance, so the panel shows the boundary the number uses without three lines of text
    # over the data.
    identity = result["identity"]
    slack = identity["rounding slack"]
    panel[7].plot([0, 100 - slack], [slack, 100], color=DIM, lw=0.5, ls=(0, (3, 2)), zorder=4)

    # --- i: our extraction against hand curation, on the papers both cover ------------------
    # Restored. Two filled regions, each the smallest area holding 90% of that set's
    # experiments, and the overlap is the claim: hand curation reaches almost nowhere the
    # extraction does not. Restricted to the 19 papers both describe -- our whole glycolysis
    # corpus against their 19-paper set would show a large cloud containing a small one, which
    # would look the same if we had extracted nothing from their papers.
    #
    # No in-panel key and no legend: the two shapes are named on the axis label, and which is
    # which is settled by the caption.
    space = gao_overlap.compute()["condition space"]
    ours, curated = space["this work"], space["hand-curated"]
    drawn = overlap(panel[8],
                    (ours.temperature_c, ours.yield_percent),
                    (curated.temperature_c, curated.yield_percent),
                    view=((140, 205), (0, 100)))
    # the frame comes from the shapes, not from the view: a patch does not autoscale its axes,
    # and clipping to the view cut both regions off where they ran past it
    panel[8].set_xlim(*drawn["bounds"][0])
    panel[8].set_ylim(*drawn["bounds"][1])
    panel[8].set_xlabel("temperature (°C)")
    panel[8].set_ylabel("yield (%)")
    panel[8].set_title("i", loc="left", fontsize=9, fontweight="bold", pad=5)

    # The route key goes above the canvas with space reserved for it, which is what
    # legend_room is for -- the ninth cell is panel i again, so there is nowhere inside the grid
    # to put it, and dropped into a panel it would sit on the data.
    legend_above(figure, panel[0])
    save(figure, "fig_chemistry", legend_room=True)


if __name__ == "__main__":
    main()
