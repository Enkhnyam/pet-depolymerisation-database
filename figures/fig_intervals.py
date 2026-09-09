"""SI -- the sparse fields as binned intervals, one bar per route, beside the smooth version.

Suggested rather than invented, and it earns its place for a reason worth writing down: it is
the only form of these panels that shows no number the data does not contain.

The main text draws these fields as kernel densities, which solve the comparison problem --
each route normalised to itself, so a route with a sixth of the records is as legible as the
biggest -- at the cost of inventing values between observations. Catalyst mass is the clearest
case: the literature reports round numbers, so the true distribution is spikes at 0.05, 0.1,
0.5, 1 g, and a kernel smooths those into a hill that no experiment sits on. A reader asking
"how many hydrolysis runs used between half a gram and a gram" gets an answer from a bar and a
shrug from a curve.

So the two forms answer different questions and both belong somewhere:

  a density   what shape does this field have, and does the shape differ by route
  an interval how many records of each route fall in this range

The bars are percentages within each route rather than counts, which is the same choice
common_norm=False makes for the density and for the same reason: on counts, methanolysis at a
sixth of glycolysis is a stub beside a tower, and the comparison the panel exists for is lost.
The count behind each percentage is on the axis label, so nothing is hidden by the rescaling.

Edges are round numbers a chemist would choose, not quantiles: quantile edges would make every
route's bars sum to the same shape by construction, which is the opposite of the point.
"""
import numpy as np
import pandas as pd
import seaborn as sns

from matplotlib.patches import Patch

from _style import ROUTE, ROUTES, canvas, save
from database import chemistry as chem

# Field, label, and the edges. Round values, chosen to bracket the way these are reported:
# milligram-scale catalyst loadings, gram-scale PET, and solvent by the tens of grams.
FIELDS = [("catalyst_amount_g", "catalyst (g)",
           [0, 0.05, 0.1, 0.25, 0.5, 1, 2, np.inf]),
          ("PET_amount_g", "PET (g)",
           [0, 0.5, 1, 2, 5, 10, 25, np.inf]),
          ("solvent_amount_g", "solvent (g)",
           [0, 5, 10, 25, 50, 100, 200, np.inf]),
          ("temperature_c", "temperature (°C)",
           [0, 80, 120, 160, 180, 200, 240, np.inf])]


def edge_labels(edges: list) -> list[str]:
    """Interval names a reader can read off, with the open last one marked as open."""
    names = []
    for low, high in zip(edges, edges[1:]):
        low_text = f"{low:g}"
        names.append(f"$\\geq${low_text}" if high == np.inf else f"{low_text}–{high:g}")
    return names


def main() -> None:
    frame = chem.compute()["records"]
    routed = frame[frame.route.isin(ROUTES)]

    figure, panel = canvas(2, 2, height=4.3)

    for index, (column, label, edges) in enumerate(FIELDS):
        axis = panel[index]
        part = routed[["route", column]].dropna()
        names = edge_labels(edges)
        part = part.assign(band=pd.cut(part[column], bins=edges, labels=names,
                                       right=False, include_lowest=True))

        # Percentage within route, so the three are comparable; the counts are on the label.
        share = (part.groupby(["route", "band"], observed=False).size()
                 .rename("records").reset_index())
        totals = share.groupby("route", observed=False).records.transform("sum")
        share["percent"] = 100 * share.records / totals

        # saturation=1 because seaborn desaturates bar fills to 0.75 by default, which painted
        # #305173, #8F4943 and #B39241 -- three colours in no palette, caught by the audit
        # rather than by looking, since a slightly duller blue is not visible as an error.
        sns.barplot(data=share, x="band", y="percent", hue="route", ax=axis, palette=ROUTE,
                    hue_order=ROUTES, order=names, width=0.78, legend=False, saturation=1,
                    edgecolor="white", linewidth=0.3, err_kws={"linewidth": 0})
        counts = part.groupby("route", observed=False).size().reindex(ROUTES)
        axis.set_xlabel(f"{label} — n = "
                        + " / ".join(f"{int(n):,}" for n in counts))
        axis.set_ylabel("share of that route's records (%)" if index % 2 == 0 else "")
        axis.tick_params(axis="x", length=0, labelsize=5.4)
        for tick in axis.get_xticklabels():
            tick.set_rotation(28)
            tick.set_ha("right")
        axis.set_ylim(0, max(46, share.percent.max() * 1.12))

    # legend_above() reads handles off an axes, and barplot(legend=False) labels none, so the
    # key came out empty. The handles are built here instead, which also keeps the swatch order
    # fixed to ROUTES rather than to whatever seaborn drew first.
    figure.legend([Patch(facecolor=ROUTE[name]) for name in ROUTES], list(ROUTES),
                  loc="upper center", ncol=len(ROUTES), handletextpad=0.4,
                  columnspacing=1.6, bbox_to_anchor=(0.5, 1.02))
    save(figure, "fig_intervals", legend_room=True)


if __name__ == "__main__":
    main()
