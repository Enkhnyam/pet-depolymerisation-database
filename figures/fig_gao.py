"""SI -- this extraction against Gao et al.'s hand curation, over every field pair worth asking.

A port of tools/overlap_grid.py, which had this right and which I should have read three attempts
ago. Same nine pairs in the same three thematic groups, same frame logic, same tick logic; the
style is the new one, two filled bivariate densities in place of a solid region and a hatched one.

Three things that diagnostic does and my own attempts did not:

  The frame is a percentile view, not the data range. The 2nd to 98th percentile of the two
  datasets pooled, with a pad, so one record charged in kilograms cannot decide where the axis
  ends -- and the density then sits in the middle of its box instead of filling it corner to
  corner. That is what "the graphs overflow" was, and no amount of margin added to a frame drawn
  at the data range was ever going to fix it.

  A log axis is labelled in the units a chemist reads. gao_overlap takes the log before
  estimating the density, so the values are log10, but the ticks belong at the integers labelled
  1, 10, 100 -- not at -2, 0, 2, which is what mine printed.

  An outcome axis is always 0-100. Cropping yield to the range it happens to occupy overstates a
  difference, and 60-95 does not read as different from 0-100 at a glance.

The nine pairs come in three groups, in the order the questions come: did the two datasets sample
the same reactions at all, do they agree on what those reactions produced, and are the outcomes
internally consistent on both sides. The record accounting, the per-field agreement and the
per-field completeness are the next figure; they are bar charts and do not belong in a grid of
densities.
"""
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from _style import DIM, FILL_BLUE, FILL_RED, canvas, kde2d, save
from curated import gao_overlap

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
    """The view for a panel: percentile bounds, except outcomes, which are always 0-100."""
    view = []
    for field in (x, y):
        pooled = np.concatenate([part[field].to_numpy() for part in sets.values()])
        if field in OUTCOMES:
            view.append((0.0, 100.0))
        else:
            low, high = np.percentile(pooled, [2, 98])
            pad = (high - low) * 0.08 or 1.0
            view.append((low - pad, high + pad))
    return tuple(view)


def ticks(axis, field: str, which: str, bounds: tuple) -> None:
    """Physical ticks, whatever the view is: 1, 10, 100 g rather than -0.3 to 2.1."""
    setter = axis.set_xticks if which == "x" else axis.set_yticks
    if field in OUTCOMES:
        setter([v for v in (0, 25, 50, 75, 100) if bounds[0] <= v <= bounds[1]])
    elif field in LOG_AXES:
        powers = [p for p in range(-4, 8) if bounds[0] <= p <= bounds[1]]
        setter(powers, [f"{10.0 ** p:g}" for p in powers])


def main() -> None:
    records = gao_overlap.records()
    figure, panels = canvas(3, 3, height=6.9)

    drawn = skipped = 0
    for axis, (x, y, xlabel, ylabel) in zip(panels, PAIRS):
        sets = gao_overlap.condition_space(records, x, y)
        ours, curated = sets["this work"], sets["hand-curated"]

        # A 2-D kernel density needs points and genuine variation on both axes. A panel that
        # cannot have one says so rather than drawing a shape that means nothing.
        if min(len(ours), len(curated)) < 20 or min(ours.nunique().min(),
                                                    curated.nunique().min()) < 3:
            axis.text(0.5, 0.5, f"too few records\n({len(ours)} ours, {len(curated)} curated)",
                      ha="center", va="center", fontsize=6, color=DIM, transform=axis.transAxes)
            axis.set_xticks([])
            axis.set_yticks([])
            skipped += 1
        else:
            view = frame_for(sets, x, y)
            long = pd.concat([ours.assign(dataset="this work"),
                              curated.assign(dataset="Gao et al.")])
            kde2d(axis, long, x, y, hue="dataset", order=["this work", "Gao et al."],
                  clip=view, xlabel="", ylabel="", label=False)
            # The frame is the view, widened. The view is already a percentile of the pooled
            # data, so the density sits inside it; the extra keeps it off the spines.
            for setter, (low, high) in ((axis.set_xlim, view[0]), (axis.set_ylim, view[1])):
                pad = (high - low) * 0.09
                setter(low - pad, high + pad)
            ticks(axis, x, "x", axis.get_xlim())
            ticks(axis, y, "y", axis.get_ylim())
            axis.annotate(f"{len(ours)} / {len(curated)}", (1.0, 1.02),
                          xycoords="axes fraction", ha="right", va="bottom", fontsize=5.4,
                          color=DIM)
            drawn += 1

        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)

    # The key goes above the grid. Inside panel a its swatches sat a millimetre from a real
    # region at 155 degrees and read as part of the data.
    for left, ramp, label in ((0.335, FILL_BLUE, "this work"),
                              (0.520, FILL_RED, "Gao et al.")):
        for step, colour in enumerate(ramp[:4][::-1]):
            figure.add_artist(Rectangle((left + step * 0.013, 0.977), 0.013, 0.014,
                                        transform=figure.transFigure, facecolor=colour,
                                        edgecolor="none"))
        figure.text(left + 0.060, 0.984, label, fontsize=6.2, va="center", color=ramp[0])
    figure.text(0.5, 0.954,
                "two filled kernel densities per panel, light at the edge and dark at the core, "
                "on the 19 papers both datasets describe",
                ha="center", fontsize=5.8, color=DIM)

    save(figure, "fig_gao", legend_room=True)
    print(f"{drawn} panel(s) drawn, {skipped} skipped for want of records")


if __name__ == "__main__":
    main()
