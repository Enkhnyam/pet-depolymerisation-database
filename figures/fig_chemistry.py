"""Figure 2 -- what the extracted conditions look like, and whether they behave.

Distributions rather than scatters: with five thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The exceptions are the last two panels, where the relationship is the point.
"""
from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, cloud, headroom, histogram,
                    note, save, stack_tops)
from database import chemistry as chem


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(3, 3, height=5.73)

    # (a)-(g), each with the number of records behind it. The counts differ by a factor of two
    # across these panels and that is the answer to why: the literature reports a temperature
    # far more often than it reports a solvent charge. Without the count on the panel a reader
    # has to hold fig_database's completeness panel in their head to know it.
    #
    # headroom() puts the top tick at or above the tallest stack. matplotlib picks ticks to span
    # the data rather than to sit above it, so a 631-record column under a 600 top tick is the
    # default -- and a reader cannot then read the peak off the axis.
    spec = [(0, "temperature_c", "temperature (°C)", False, frame),
            (1, "reaction_time_min", "reaction time (min)", True, frame),
            (2, "yield_percent", "yield (%)", False, frame[frame.yield_percent <= 100]),
            (3, "conversion_percent", "conversion (%)", False, frame),
            (4, "catalyst_amount_g", "catalyst (g)", True, frame),
            (5, "PET_amount_g", "PET (g)", True, frame),
            (6, "solvent_amount_g", "solvent (g)", True, frame)]
    for index, column, label, log, source in spec:
        reported = int(source[column].notna().sum())
        histogram(panel[index], source, column, logx=log,
                  xlabel=f"{label}\n{reported:,} records report it",
                  ylabel="records" if index % 3 == 0 else "", **stack)
        headroom(panel[index], stack_tops(panel[index]))

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
    # On the line, not in the caption: the panel is one argument about this one line.
    panel[7].annotate("yield = conversion", (58, 58), rotation=45, rotation_mode="anchor",
                      fontsize=5.5, color=DIM, ha="left", va="bottom",
                      transform_rotates_text=True, zorder=5)
    # Two numbers, because the panel and the caption were disagreeing. 40 marks sit above
    # y = x; the check counts 28, because it allows one percentage point for the rounding in
    # the source papers -- a yield of 95.2 against a conversion of 95.0 is rounding, not a
    # violated identity. So the allowance is drawn as well as applied, and both counts are
    # stated. Without this the panel showed 40 under a caption saying 28.
    identity = result["identity"]
    slack = identity["rounding slack"]
    panel[7].plot([0, 100 - slack], [slack, 100], color=DIM, lw=0.5, ls=(0, (3, 2)), zorder=4)
    note(panel[7], f"{identity['above the line']} above the line\n"
                   f"{identity['yield above conversion']} beyond the {slack:g}-point\n"
                   f"rounding allowance (dashed)", x=0.04, y=0.84)

    # The ninth cell carries the route key rather than being blank. A legend above the canvas
    # sat where the panel letters are; here it is beside the panels it explains and costs no
    # plotting area, because removing the ninth panel is what freed the cell.
    panel[8].axis("off")
    panel[8].set_title("")
    handles, labels = panel[0].get_legend_handles_labels()
    panel[8].legend(handles, labels, loc="center left", title="route, inferred from the solvent",
                    frameon=False, handlelength=1.2, handleheight=1.0, labelspacing=0.6,
                    borderpad=0, alignment="left")
    panel[8].get_legend().get_title().set_fontsize(6.5)

    save(figure, "fig_chemistry")


if __name__ == "__main__":
    main()
