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

from _style import CATEGORICAL, DIM, INK, RAMP, RULE, canvas, save
from curated import gao_overlap

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

    # --- c: are the records only we hold as good as the ones both hold? ----------------------
    # The obvious suspicion about an extraction returning more records than a person did is that
    # the surplus is junk. This is the test, and the shape of the panel is the answer: a short
    # line means the two populations report that field at the same rate. Nine of the ten lines
    # are short, and two of those run the other way -- the extra records carry temperature and
    # reaction time more often than the shared ones do.
    #
    # A dumbbell rather than paired bars. What matters here is the distance between two numbers,
    # and a bar chart makes a reader compare two lengths from a shared baseline to recover it.
    axis = panel[2]
    extra = result["extra records"] * 100
    order = list((extra["ours only"] - extra["shared"]).sort_values().index)
    for position, field in enumerate(order):
        low, high = extra.loc[field, "shared"], extra.loc[field, "ours only"]
        axis.plot([low, high], [position] * 2, color=RULE, lw=1.6, solid_capstyle="round",
                  zorder=1)
        axis.plot([low], [position], marker="o", ms=4.0, color=DIM, zorder=3,
                  markeredgecolor="white", markeredgewidth=0.6)
        axis.plot([high], [position], marker="o", ms=4.0, zorder=3,
                  color=CATEGORICAL["red"] if high < low - 5 else CATEGORICAL["blue"],
                  markeredgecolor="white", markeredgewidth=0.6)
        if abs(high - low) >= 5:
            axis.annotate(f"{high - low:+.0f}", (max(low, high), position), xytext=(5, 0),
                          textcoords="offset points", va="center", fontsize=5.4, color=DIM)
    axis.set_yticks(range(len(order)),
                    [f.replace("_percent", " %").replace("_amount_g", " (g)").replace("_", " ")
                     for f in order], fontsize=5.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(35, 118)
    axis.set_xticks([40, 60, 80, 100], ["40", "60", "80", "100%"])
    axis.set_ylim(-0.8, len(order) - 0.4)
    meta = result["extra records"].attrs
    axis.set_xlabel(f"records reporting the field\n"
                    f"grey: {meta['shared']} shared · blue: {meta['extra']} ours")

    save(figure, "fig_gao_records")


if __name__ == "__main__":
    main()
