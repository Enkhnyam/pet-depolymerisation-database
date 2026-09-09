"""Figure 2 -- what the extracted conditions look like, and one identity they have to obey.

Eight panels and two forms, and the split between them is the whole design decision.

(a)-(c) are histograms because their *shape* is the finding: the reflux peak at 190-200 C, the
round protocol durations, the pile-up of yields against 100%. A reader wants counts off those,
and "1,247 records" is a number where a kernel density's 0.025 is not.

(d)-(g) are kernel densities with common_norm=False, which normalises every route to itself.
That is the answer to a problem four earlier forms all failed at in these very panels: methanolysis
holds a sixth of glycolysis's records, so on any shared count axis it was a flat line beside a
tall one. Stacked histograms, cumulative curves, quantile rows and violins were each drawn here
and each rejected for it. Under common_norm=False every route's curve integrates to one, so what
is compared is shape, which is what the panels are for.

Every density is clipped. A kernel does not know that a percentage stops at 100 or that a mass
cannot be negative, and unclipped it draws probability in both places.

The Gao et al. comparison used to be panel (i). It is a comparison against an external dataset
rather than a statement about this one, and it now has a section of the SI to itself with three
panels instead of a corner of this figure.
"""
from _style import (DIM, INK, RAMP, ROUTE, ROUTES, canvas, cloud, headroom, histogram, kde,
                    route_key, save, stack_tops)
from database import chemistry as chem


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    routed = frame[frame.route.isin(ROUTES)]

    figure, panel = canvas(3, 3, height=5.73)

    # --- a-c: the three fields whose shape is the finding -------------------------------------
    # Stacked counts, tail cut at a stated percentile rather than transformed, and headroom()
    # putting the top tick at or above the tallest stack -- matplotlib picks ticks to span the
    # data, so a 1,247-record column under a 1,200 tick is the default.
    shapes = [(0, "temperature_c", "temperature (°C)", None, frame),
              (1, "reaction_time_min", "reaction time (min)", 0.90, frame),
              (2, "yield_percent", "yield (%)", None, frame[frame.yield_percent <= 100])]
    for index, column, label, clip, source in shapes:
        reported = int(source[column].notna().sum())
        histogram(panel[index], source, column, clip=clip,
                  xlabel=f"{label}, n={reported:,}",
                  ylabel="records" if index % 3 == 0 else "",
                  split="route", palette=ROUTE, order=ROUTES)
        headroom(panel[index], stack_tops(panel[index]))

    # --- d-g: the four fields whose route comparison is the finding ---------------------------
    # The amounts span decades and the routes differ in size by sixfold, which is why a count
    # axis cannot hold them. Each curve is its own distribution; the axis is the field's own
    # units and the window is where the records are.
    spreads = [(3, "conversion_percent", "conversion (%)", (0, 100)),
               (4, "catalyst_amount_g", "catalyst (g)", (0, 3)),
               (5, "PET_amount_g", "PET (g)", (0, 30)),
               (6, "solvent_amount_g", "solvent (g)", (0, 200))]
    for index, column, label, window in spreads:
        inside = routed[(routed[column] >= window[0]) & (routed[column] <= window[1])]
        share = len(inside) / max(1, int(routed[column].notna().sum()))
        reach = "" if share > 0.995 else f", {share:.0%} in view"
        kde(panel[index], routed, column, hue="route", palette=ROUTE, order=ROUTES,
            clip=window, xlabel=f"{label}{reach}",
            ylabel="relative density" if index % 3 == 0 else "")
        panel[index].set_xlim(*window)

    # --- h: yield against conversion, an identity rather than a correlation -------------------
    # Dots, not a density: only the records reporting both land here, and at that count the
    # marks separate. The dashed line is the one percentage point of rounding allowance the
    # check applies, so the panel shows the boundary the quoted number actually uses.
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

    # --- i: the route key, given the cell rather than crammed above the canvas ----------------
    # Eight panels in a nine-cell grid leaves one over, and a key is a better use for it than
    # white space: above the figure it was 6.5 pt and competing with the title.
    route_key(panel[8], ROUTE, ROUTES, title="route, inferred from the solvent")

    save(figure, "fig_chemistry")


if __name__ == "__main__":
    main()
