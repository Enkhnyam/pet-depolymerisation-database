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
from _style import CATEGORICAL, DIM, INK, RAMP, canvas, save
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

    # --- c: paper by paper, who holds more ----------------------------------------------------
    # The totals in (a) say the two sets differ by 142 records and why; they cannot say whether
    # that is spread across the corpus or concentrated. It is concentrated, and it runs both
    # ways: five of the nineteen papers give us more records than the hand curation has, and one
    # gives us none at all.
    axis = panel[2]
    counts_by_paper = result["per paper"]
    gao_side = counts_by_paper["hand-curated"]
    our_side = counts_by_paper["this work"]
    top = max(gao_side.max(), our_side.max()) * 1.12

    axis.plot([0, top], [0, top], color="white", lw=1.6, zorder=1)
    axis.plot([0, top], [0, top], color=INK, lw=0.7, zorder=2)
    ahead = our_side > gao_side
    for mask, colour, label in ((~ahead, CATEGORICAL["red"], "Gao holds more"),
                                (ahead, CATEGORICAL["blue"], "we hold more")):
        axis.scatter(gao_side[mask], our_side[mask], s=13, color=colour, alpha=0.85,
                     linewidths=0.4, edgecolors="white", zorder=3, label=label)
    # No labels on the outliers: a truncated DOI is unreadable at this size and both of these
    # truncate to the same sixteen characters. The caption names them.
    axis.set_xlim(0, top)
    axis.set_ylim(0, top)
    axis.set_xlabel("records Gao holds, per paper")
    axis.set_ylabel("records we hold")
    axis.legend(loc="upper left", frameon=False, fontsize=5.4, handletextpad=0.15,
                borderpad=0.0, labelspacing=0.25, markerscale=1.1)

    save(figure, "fig_gao_records")


if __name__ == "__main__":
    main()
