"""SI -- this extraction against Gao et al.'s hand curation, over every field pair worth asking.

The main text asks one pair of fields -- temperature against yield -- and the question is the
same for every other pair the two datasets share, while the answers are not: two datasets can
agree on where the reactions were run and still disagree on what came out of them.

This began as tools/overlap_grid.py, a diagnostic, and is promoted here unchanged in substance.
Four attempts at restyling it as filled kernel densities all produced panels whose shapes ran
edge to edge, so the styling it already had is the styling it keeps: for each dataset the
smallest area holding 90% of its experiments, one filled and one hatched so both stay readable
where they coincide.

What makes it fit, and what the rebuilt versions kept getting wrong:

  The frame comes from the drawn shapes, not from the data. overlap() returns the bounds of the
  regions it actually drew -- a 90% region smoothed out of a kernel reaches past the
  observations it was built from -- and the axis is set to those. A frame drawn at the data
  range grows with the shape inside it, so no amount of margin ever separates the two.

  Every view is the 2nd to 98th percentile of the two datasets pooled, so one record charged in
  kilograms cannot decide it.

  Masses, times and ratios are drawn on log axes, which checks/curated/gao_overlap.py takes
  before estimating the density rather than after, and the ticks are labelled in the units
  themselves: a chemist reads 1, 10, 100 g, not -0.3 to 2.1.

  An outcome axis is always 0-100, because cropping yield to the range it happens to occupy
  overstates a difference.

The record accounting, the per-field agreement and the per-field completeness are counts rather
than distributions and are fig_gao_records.
"""
import numpy as np
from matplotlib.patches import Rectangle

from _style import DIM, RAMP, canvas, overlap, save
from curated import gao_overlap

# (x, y, x label, y label). Three groups, in the order the questions come:
#
#   the conditions themselves   did the two datasets sample the same reactions at all
#   condition against outcome   do they agree on what those reactions produced
#   outcome against outcome     are the outcomes internally consistent on both sides
PAIRS = [
    ("temperature_c", "reaction_time_min", "temperature (°C)", "time (min, log)"),
    ("PET_amount_g", "solvent_amount_g", "PET (g, log)", "solvent (g, log)"),
    ("catalyst_loading_wt", "solvent_ratio", "catalyst (wt%, log)", "solvent : PET (log)"),

    ("temperature_c", "yield_percent", "temperature (°C)", "yield (%)"),
    ("reaction_time_min", "yield_percent", "time (min, log)", "yield (%)"),
    ("catalyst_loading_wt", "yield_percent", "catalyst (wt%, log)", "yield (%)"),

    ("temperature_c", "conversion_percent", "temperature (°C)", "conversion (%)"),
    ("conversion_percent", "yield_percent", "conversion (%)", "yield (%)"),
    ("conversion_percent", "selectivity_percent", "conversion (%)", "selectivity (%)"),
]

OUTCOMES = {"yield_percent", "conversion_percent", "selectivity_percent"}
LOG_AXES = gao_overlap.LOG_AXES


def frame_for(sets: dict, x: str, y: str) -> tuple:
    """The view for a panel: percentile bounds, except outcomes, which are always 0-100.

    An outcome axis cropped to the range the data happens to occupy overstates a difference, and
    a reader cannot tell 60-95 from 0-100 at a glance. Everything else takes the 2nd to 98th
    percentile of both datasets pooled, so one outlier does not decide the frame.
    """
    view = []
    for field in (x, y):
        pooled = np.concatenate([part[field].to_numpy() for part in sets.values()])
        if field in OUTCOMES:
            view.append((0, 100))
        else:
            low, high = np.percentile(pooled, [2, 98])
            pad = (high - low) * 0.08 or 1.0
            view.append((low - pad, high + pad))
    return tuple(view)


def ticks(axis, field: str, which: str, bounds: tuple) -> None:
    """Physical ticks, whatever the view is.

    An outcome keeps 0-100 because nothing above it is ever a real yield. A log axis is drawn on
    log10 values, so its ticks go at the integers and are labelled with the number itself -- a
    chemist reads 1, 10, 100 g, not -0.3 to 2.1.
    """
    setter = axis.set_xticks if which == "x" else axis.set_yticks
    if field in OUTCOMES:
        setter([v for v in (0, 25, 50, 75, 100) if bounds[0] <= v <= bounds[1]])
    elif field in LOG_AXES:
        powers = [p for p in range(-4, 8) if bounds[0] <= p <= bounds[1]]
        labels = [f"{10.0 ** p:g}" for p in powers]
        setter(powers, labels)


def main() -> None:
    records = gao_overlap.records()

    figure, panels = canvas(3, 3, height=6.9)
    drawn = skipped = 0
    for axis, (x, y, xlabel, ylabel) in zip(panels, PAIRS):
        sets = gao_overlap.condition_space(records, x, y)
        ours, curated = sets["this work"], sets["hand-curated"]

        # a 2-D kernel density needs points and genuine variation on both axes; and overlap()
        # refuses to draw a region it cannot close inside the view. Either way the panel says
        # so rather than showing a shape that means nothing.
        note = None
        if min(len(ours), len(curated)) < 20 or min(ours.nunique().min(),
                                                    curated.nunique().min()) < 3:
            note = f"too few records\n({len(ours)} ours, {len(curated)} curated)"
        else:
            try:
                shapes = overlap(axis, (ours[x], ours[y]), (curated[x], curated[y]),
                                 view=frame_for(sets, x, y))
                # the frame comes from the shapes, not the data range: a 90% region smoothed out
                # of a kernel reaches past the observations it was built from
                axis.set_xlim(*shapes["bounds"][0])
                axis.set_ylim(*shapes["bounds"][1])
                ticks(axis, x, "x", shapes["bounds"][0])
                ticks(axis, y, "y", shapes["bounds"][1])
                drawn += 1
            except (AssertionError, ValueError, np.linalg.LinAlgError) as failure:
                note = f"no closed region\n({type(failure).__name__})"

        if note:
            axis.text(0.5, 0.5, note, ha="center", va="center", fontsize=6, color=DIM,
                      transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
            skipped += 1
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)

    # The key goes above the grid, not inside panel a. Inside, its two swatches sat a
    # millimetre from a real region at 155 degrees and read as part of the legend.
    for x, style, label in ((0.36, dict(facecolor=RAMP[4], edgecolor=RAMP[2]), "this work"),
                            (0.52, dict(facecolor="none", edgecolor=RAMP[0], hatch="//////"),
                             "hand-curated")):
        figure.add_artist(Rectangle((x, 0.978), 0.018, 0.013, transform=figure.transFigure,
                                    linewidth=0.9, **style))
        figure.text(x + 0.023, 0.9845, label, fontsize=6.2, va="center", color=RAMP[0])
    figure.text(0.5, 0.955, "each shape is the smallest area holding 90% of that set's "
                            "experiments, on the 19 papers both describe",
                ha="center", fontsize=5.8, color=DIM)

    save(figure, "fig_gao", legend_room=True)
    print(f"{drawn} panel(s) drawn, {skipped} skipped for want of records")


if __name__ == "__main__":
    main()
