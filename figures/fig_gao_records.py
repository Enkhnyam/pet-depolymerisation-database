"""SI -- the three things about the Gao comparison that are counts rather than distributions.

Split out of fig_gao, which is a grid of densities and had these three bar charts wedged into
its bottom row. Three panels, three questions, in the order a referee asks them:

  (a) Why do the two sets differ in size at all? Not two pie charts: a pie cannot show that the
      sets overlap -- two circles side by side say nothing about their intersection -- and the
      reasons are signed, four raising Gao's count and one raising ours. A diverging bar reads
      left for "only Gao" and right for "only this work" against a single axis of records.

  (b) Where both hold a record, do they say the same thing? At the tolerance the heuristic
      grader uses everywhere else in this project, so "agrees" means one thing throughout.

  (c) Does an extraction report as much per record as a person does? The question the other two
      do not answer. Hand curation fills every condition field on every record; this extraction
      fills 84 to 97% of them, and selectivity is the one substantial gap.

Every category in (a) was settled by a person reading the paper: an automatic rule proposed each
label and a chemist overruled it fourteen times. That is why the classification is a fixed table
in artifacts/data/gao/ and not a computation.
"""
import numpy as np
import seaborn as sns
from matplotlib.ticker import NullLocator

from _style import CATEGORICAL, DIM, INK, RAMP, canvas, save
from curated import gao_overlap
from curated.gao_overlap import TOLERANCE

# Why a record sits in one dataset and not the other, largest first, coloured by whose count it
# raises: the blue ramp for Gao's reasons, red for the one that is our error, blue for ours.
REASONS = [("chart", "read off a chart", RAMP[1]),
           ("si", "in SI we lack", RAMP[2]),
           ("rule", "design table", RAMP[3]),
           ("missed", "we missed it", CATEGORICAL["red"])]


def main() -> None:
    result = gao_overlap.compute()
    counts = gao_overlap.records().category.value_counts()

    figure, panel = canvas(1, 3, height=2.55)

    # --- a: why the two sets differ in size ---------------------------------------------------
    axis = panel[0]
    shared, ours_only = int(counts["both"]), int(counts["ours"])
    rows = [(label, -int(counts[key]), colour) for key, label, colour in REASONS]
    rows.append(("ours alone", ours_only, CATEGORICAL["blue"]))
    for position, (label, value, colour) in enumerate(rows):
        y = len(rows) - 1 - position
        axis.barh(y, value, height=0.62, color=colour)
        inside = abs(value) > 60
        axis.annotate(f"{abs(value)}", (value, y),
                      xytext=((5 if value < 0 else -5) if inside
                              else (-4 if value < 0 else 4), 0),
                      textcoords="offset points",
                      ha=("left" if value < 0 else "right") if inside
                         else ("right" if value < 0 else "left"),
                      va="center", fontsize=6, color="white" if inside else DIM)
    axis.axvline(0, color=INK, lw=0.8)
    axis.set_yticks(range(len(rows)), [label for label, *_ in reversed(rows)], fontsize=6)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(-215, 150)
    ticks = [-200, -100, 0, 100]
    axis.set_xticks(ticks, [str(abs(v)) for v in ticks])
    axis.set_xlabel(f"records, {shared} shared")

    # --- b: on the records both hold, do they agree -------------------------------------------
    axis = panel[1]
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
    axis.set_xlim(0, 142)
    axis.set_xticks([0, 50, 100])
    axis.set_xlabel("shared records agreeing, per field")

    # --- c: what a disagreement actually looks like -------------------------------------------
    # Panel (b) says how often the two agree. It cannot say what a disagreement is, and that is
    # the interesting half: of the 842 numeric values both datasets report, 797 are identical to
    # the digit, and the 45 that differ are almost all masses, apart by factors rather than by
    # percent. Temperature and reaction time never disagree at all.
    #
    # One dot per differing value rather than a fourth bar chart, on a log axis because the
    # differences run from a rounded percentage point to a factor of seven and a linear axis
    # would stack forty of them against the left spine. The 20% line is the tolerance the
    # heuristic grader allows, so a reader can see which disagreements the graders would even
    # call disagreements.
    axis = panel[2]
    gaps = result["disagreements"]
    off = gaps[~gaps.identical & gaps.ratio.notna() & (gaps.ratio > 1)]
    fields = list(off.groupby("field").ratio.median().sort_values().index)
    np.random.seed(0)
    sns.stripplot(data=off, x="ratio", y="field", order=fields, ax=axis, size=3.4,
                  hue="field", hue_order=fields, legend=False, jitter=0.22, alpha=0.9,
                  palette={f: (CATEGORICAL["red"] if f.endswith("_amount_g")
                               else CATEGORICAL["blue"]) for f in fields})
    axis.set_xscale("log")
    axis.axvline(1 + TOLERANCE, color=INK, lw=0.7, ls=(0, (3, 2)), zorder=1)
    axis.annotate(f"{TOLERANCE:.0%} tolerance", (1 + TOLERANCE, -0.55), xytext=(-3, 0),
                  textcoords="offset points", fontsize=5.2, color=DIM, va="center",
                  ha="right")
    axis.set_xlim(1.003, 16)
    # A log axis puts its own labelled minor ticks between the decades, and at this range they
    # landed on top of the four that carry the meaning.
    axis.xaxis.set_minor_locator(NullLocator())
    # Three ticks, not four: 1.01 and 1.1 are a millimetre apart at this width and printed on
    # top of each other.
    axis.set_xticks([1.01, 2, 10], ["$\\times$1.01", "$\\times$2", "$\\times$10"])
    axis.set_yticks(range(len(fields)),
                    [f.replace("_percent", " %").replace("_amount_g", " (g)").replace("_", " ")
                     for f in fields], fontsize=5.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_ylim(-0.85, len(fields) - 0.3)
    axis.set_ylabel("")
    axis.set_xlabel(f"factor apart, where they differ\n"
                    f"{int(gaps.identical.sum())} of {len(gaps)} values identical")

    save(figure, "fig_gao_records")


if __name__ == "__main__":
    main()
