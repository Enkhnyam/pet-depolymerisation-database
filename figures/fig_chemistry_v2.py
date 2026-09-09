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

(i) is the comparison against Gao et al., which stays in the main text. Two filled bivariate
densities, light at the edge and dark at the core, drawn from two declared ramps -- see kde2d in
_style.py for why the ramp is declared rather than derived. Every other field pair of the same
comparison is in the SI.
"""
from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, cloud, kde, kde2d,
                    legend_above, save)
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
        note = f", n={reported:,}" if share > 0.995 else f", {share:.0%} of {reported:,}"
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

    # --- i: against the hand-curated set, on the papers both describe -------------------------
    space = gao_overlap.condition_space(gao_overlap.records())
    long = __import__("pandas").concat([
        space["this work"].assign(dataset="this work"),
        space["hand-curated"].assign(dataset="Gao et al."),
    ])
    kde2d(panel[8], long, "temperature_c", "yield_percent", hue="dataset",
          order=["this work", "Gao et al."], clip=((140, 210), (0, 100)),
          xlabel="temperature (°C)", ylabel="yield (%)")
    # Yield is populated across its whole range, so the density is nonzero at both bounds and
    # ran edge to edge with no white anywhere around it. The margin is what makes the cut at 0
    # and 100% read as the bound it is rather than as a shape leaving its frame.
    panel[8].set_xlim(136, 214)
    panel[8].set_ylim(-10, 110)

    # Nine panels leaves no spare cell for the route key, so it goes above the canvas with
    # room reserved for it -- dropped into a panel it sits on the data, which is where the
    # first attempt put it.
    legend_above(figure, panel[0])
    save(figure, "fig_chemistry_v2", legend_room=True)


if __name__ == "__main__":
    main()
