"""Figure 2, rebuilt -- the conditions the corpus reports, one identity, and the external check.

Written to fig_chemistry_v2.pdf, not fig_chemistry.pdf. paper_rsc.tex is in review and includes
the latter; redrawing that file changes a figure in a manuscript nobody asked to change, which
is what happened once already. Two names, two manuscripts, no coupling.

Nine panels and one form for the seven that are distributions. (a)-(g) are kernel densities with
common_norm=False, so each route's curve integrates to itself: methanolysis holds a sixth of
glycolysis's records, and on a shared count axis it was a flat line beside a tall one -- the
failure that defeated stacked histograms, cumulative curves, quantile rows and violins in turn
in these same panels. Their vertical axes carry no numbers, because the height of a
self-normalised density is not a quantity a reader can act on; only the shapes are compared.

(h) is a scatter, because it tests an identity rather than showing a distribution: yield cannot
exceed conversion, so a mark above the line is an error and each one should be countable.

(i) is the comparison against Gao et al., which stays in the main text: for each dataset the
smallest area holding 90% of its experiments, one filled and one hatched so both stay readable
where they coincide. Every other field pair of the same comparison is in the SI.
"""
from matplotlib.patches import Patch

from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, cloud, kde,
                    overlap, save)
from curated import gao_overlap
from database import chemistry as chem

# Each panel: the field, its label, and the window the density is drawn over. The three bounded
# fields need no window; the four amounts do, and the share of records inside it is stated on
# the axis rather than left for a reader to wonder about.
PANELS = [("temperature_c", "temperature (°C)", (0, 320)),
          ("reaction_time_min", "reaction time (min)", (0, 500)),
          ("yield_percent", "yield (%)", (0, 100)),
          ("conversion_percent", "conversion (%)", (0, 100)),
          ("catalyst_amount_g", "catalyst (g)", (0, 3)),
          ("PET_amount_g", "PET (g)", (0, 30)),
          ("solvent_amount_g", "solvent (g)", (0, 200))]


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    routed = frame[frame.route.isin(ROUTES)]

    figure, panel = canvas(3, 3, height=5.73)

    for index, (column, label, window) in enumerate(PANELS):
        reported = int(routed[column].notna().sum())
        inside = int(routed[column].between(*window).sum())
        share = inside / max(1, reported)
        # "97% of 4,102 in view" = 4,102 records report a temperature, and 97% of those fall
        # inside the drawn window. It is NOT field completeness -- that is Fig. 3c, over a
        # different denominator -- and the caption said so for a while, which invited the
        # reading that temperature is 97% complete when Fig. 3c puts it at 87%.
        note = (f", n={reported:,}" if share > 0.995
                else f", {share:.0%} of {reported:,} in view")
        kde(panel[index], routed, column, hue="route", palette=ROUTE, order=ROUTES,
            clip=window, xlabel=f"{label}{note}",
            ylabel="relative density" if index % 3 == 0 else "")
        panel[index].set_xlim(*window)

    # --- h: yield against conversion ----------------------------------------------------------
    pair = frame[["conversion_percent", "yield_percent"]].dropna()
    cloud(panel[7], pair.conversion_percent, pair.yield_percent, colour=RAMP[2], size=1.4)
    panel[7].set_xlim(0, 100)
    panel[7].set_ylim(0, 100)
    panel[7].set_xlabel("conversion (%)")
    panel[7].set_ylabel("yield (%)")
    panel[7].plot([0, 100], [0, 100], color="white", lw=1.5, zorder=3)
    panel[7].plot([0, 100], [0, 100], color=INK, lw=0.8, zorder=4)
    slack = result["identity"]["rounding slack"]
    panel[7].plot([0, 100 - slack], [slack, 100], color=DIM, lw=0.5, ls=(0, (3, 2)), zorder=4)

    # --- i: against the hand-curated set, on the papers both describe ------------------------
    # The same styling as the SI grid, and for the same reason: overlap() returns the bounds of
    # the regions it drew, and setting the frame to those is what keeps a shape off its own
    # spines. A filled kernel density here was tried four times and every version ran edge to
    # edge, because a frame drawn at the data range grows with the shape inside it.
    space = gao_overlap.condition_space(gao_overlap.records())
    ours, curated = space["this work"], space["hand-curated"]
    drawn = overlap(panel[8],
                    (ours.temperature_c, ours.yield_percent),
                    (curated.temperature_c, curated.yield_percent),
                    view=((140, 205), (0, 100)))
    panel[8].set_xlim(*drawn["bounds"][0])
    panel[8].set_ylim(*drawn["bounds"][1])
    panel[8].set_xlabel("temperature (°C)")
    panel[8].set_ylabel("yield (%)")

    # Nine panels leaves no spare cell for the route key, so it goes above the canvas with room
    # reserved for it. The handles are built here rather than read off an axes: kde() draws with
    # legend=False, so there is nothing labelled for legend_above() to find, and the key came
    # out empty -- the same way it did in fig_intervals.
    figure.legend([Patch(facecolor=ROUTE[name], edgecolor=ROUTE[name]) for name in ROUTES],
                  list(ROUTES), loc="upper center", ncol=len(ROUTES), frameon=False,
                  handletextpad=0.4, columnspacing=1.8, bbox_to_anchor=(0.5, 1.012))
    save(figure, "fig_chemistry_v2", legend_room=True)


if __name__ == "__main__":
    main()
