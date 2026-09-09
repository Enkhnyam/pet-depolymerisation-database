"""SI -- this extraction against Gao et al.'s hand-curated set, on the papers both describe.

Three panels, because "do the two datasets agree" is three questions and the manuscript answered
it with one corner of a figure.

(a) Do they cover the same ground? Two filled bivariate densities. This replaces a primitive that
    extracted contour paths by hand, ran a Gaussian filter to close rings the grid had cut, and
    carried an assertion because regions still escaped the frame; seaborn does it in a call, and
    thresholds on density rather than on an enclosed fraction, so two sets of unequal size stay
    comparable.

(b) Why do the sets differ in size? Not two pie charts. A pie cannot show that the sets overlap
    at all -- two circles side by side say nothing about their intersection -- and the reasons
    here are signed: some push Gao's count up, one pushes ours up. A diverging bar reads left for
    "only Gao", right for "only this work", against a single axis of records, and the reasons sit
    where the reader can compare their sizes directly.

(c) Where both hold a record, do they say the same thing? This is the actual claim of the section
    and it was one sentence of prose. Per field, the share of shared records that agree, on the
    tolerance the metric grader uses everywhere else so that "agrees" means one thing in this
    project.

Every category in (b) was settled by a person reading the paper: an automatic rule proposed each
one and a chemist overruled it fourteen times. That is why this is a fixed table in
artifacts/data/gao/ and not a computation.
"""
import pandas as pd

from _style import CATEGORICAL, DIM, INK, RAMP, canvas, kde2d, save
from curated import gao_overlap

# Why a record is in one dataset and not the other. Ordered largest first, and coloured by whose
# count it raises: the ramp for Gao's reasons, red for the one that is our fault, blue for ours.
REASONS = [("chart", "Gao read it off a plotted curve", RAMP[1]),
           ("si", "in Supporting Information we do not hold", RAMP[2]),
           ("rule", "a design table our scope rules skip", RAMP[3]),
           ("missed", "our extraction missed it", CATEGORICAL["red"])]


def main() -> None:
    result = gao_overlap.compute()
    counts = gao_overlap.records().category.value_counts()

    figure, panel = canvas(1, 3, height=2.42)

    # --- a: the condition space each dataset covers -------------------------------------------
    space = pd.concat([
        result["condition space"]["this work"].assign(dataset="this work"),
        result["condition space"]["hand-curated"].assign(dataset="Gao et al."),
    ])
    palette = {"this work": CATEGORICAL["blue"], "Gao et al.": CATEGORICAL["red"]}
    kde2d(panel[0], space, "temperature_c", "yield_percent", hue="dataset", palette=palette,
          order=["this work", "Gao et al."], xlabel="temperature (°C)", ylabel="yield (%)",
          clip=((140, 210), (0, 100)))
    panel[0].set_ylim(0, 100)
    for index, (name, colour) in enumerate(palette.items()):
        panel[0].annotate(name, (0.04, 0.94 - index * 0.08), xycoords="axes fraction",
                          fontsize=6, color=colour, fontweight="bold")

    # --- b: why the two sets differ, signed ---------------------------------------------------
    axis = panel[1]
    shared = int(counts["both"])
    ours_only = int(counts["ours"])
    rows = [(label, -int(counts[key]), colour) for key, label, colour in REASONS]
    rows.append(("we hold it and Gao does not", ours_only, CATEGORICAL["blue"]))
    for position, (label, value, colour) in enumerate(rows):
        y = len(rows) - 1 - position
        axis.barh(y, value, height=0.62, color=colour)
        # Counts sit inside a bar long enough to hold one and outside a short one. Outside on
        # every bar put "173" on top of its own row label, since the labels are sentences.
        inside = abs(value) > 60
        toward_zero = 5 if value < 0 else -5
        away = -4 if value < 0 else 4
        axis.annotate(f"{abs(value)}", (value, y),
                      xytext=(toward_zero if inside else away, 0), textcoords="offset points",
                      ha=("left" if value < 0 else "right") if inside
                         else ("right" if value < 0 else "left"),
                      va="center", fontsize=6, color="white" if inside else DIM)
    axis.axvline(0, color=INK, lw=0.8)
    axis.set_yticks(range(len(rows)), [label for label, *_ in reversed(rows)], fontsize=5.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(-215, 150)
    # Absolute tick labels: the sign carries "whose set" and is already said by the axis label,
    # so a "-200" on a count of records is only a chance to misread it.
    ticks = [-200, -100, 0, 100]
    axis.set_xticks(ticks, [str(abs(v)) for v in ticks])
    axis.set_xlabel(f"← only Gao et al.   records, {shared} shared   only this work →")

    # --- c: on the records both hold, do they agree -------------------------------------------
    axis = panel[2]
    agree = result["agreement"].sort_values("share")
    for position, (field, row) in enumerate(agree.iterrows()):
        axis.barh(position, row["share"] * 100, height=0.62,
                  color=CATEGORICAL["blue"] if row["share"] >= 0.9 else CATEGORICAL["red"])
        axis.annotate(f"{row['share']:.0%} of {int(row['both report it'])}",
                      (row["share"] * 100, position), xytext=(3, 0),
                      textcoords="offset points", va="center", fontsize=5.4, color=DIM)
    axis.set_yticks(range(len(agree)),
                    [str(name).replace("_", " ") for name in agree.index], fontsize=5.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 138)
    axis.set_xticks([0, 50, 100])
    axis.set_xlabel("shared records agreeing, per field")

    save(figure, "fig_gao")


if __name__ == "__main__":
    main()
