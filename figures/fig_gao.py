"""SI -- the comparison against Gao et al., on every field pair rather than the one in the paper.

The main text shows temperature against yield, which is one slice of a comparison that can be
taken in ten. This is the rest of it: the same two datasets, the same 19 papers, the same
declared ramps, over six pairs of fields. Panel (a) reproduces the main text's so the section can
be read on its own, and (b)-(f) are the pairs it does not show.

The last two panels answer the two questions a density cannot. (g) why the sets differ in size at
all, and (h) whether they agree where both hold a record -- which is the section's real claim and
was one sentence of prose.

(g) is not two pie charts. A pie cannot show that the sets overlap -- two circles side by side say
nothing about their intersection -- and the reasons are signed: four raise Gao's count, one raises
ours. A diverging bar reads left for "only Gao" and right for "only this work" against a single
axis of records.

Fields the check logs before estimating are labelled as logged, because the density is estimated
on the scale it is drawn on: estimating on grams and plotting the log of the result would
describe a different distribution from the one on the page.
"""
import pandas as pd

from _style import CATEGORICAL, DIM, INK, RAMP, SLOTS, canvas, kde2d, save
from curated import gao_overlap

# Six pairs in two rows, and each row shares its y field. That is what makes the panels wide
# enough to read: with three different y fields in a row, every panel carries its own tick
# labels and its own axis label, and the plot boxes end up tall narrow slots with the density
# filling them from edge to edge. One y per row means one set of tick labels per row.
ROWS = [("yield_percent", "yield (%)",
         [("temperature_c", "temperature (°C)", (132, 218)),
          ("conversion_percent", "conversion (%)", (0, 100)),
          ("PET_amount_g", "PET (g, $\\log_{10}$)", (-2.8, 2.2))]),
        ("selectivity_percent", "selectivity (%)",
         [("temperature_c", "temperature (°C)", (132, 218)),
          ("reaction_time_min", "reaction time (min, $\\log_{10}$)", (0.4, 3.6)),
          ("catalyst_amount_g", "catalyst (g, $\\log_{10}$)", (-3.8, 1.4))])]

# Why a record sits in one dataset and not the other, largest first, coloured by whose count it
# raises: the blue ramp for Gao's reasons, red for the one that is our error, blue for ours.
REASONS = [("chart", "Gao read it off a plotted curve", RAMP[1]),
           ("si", "in Supporting Information we do not hold", RAMP[2]),
           ("rule", "a design table our scope rules skip", RAMP[3]),
           ("missed", "our extraction missed it", CATEGORICAL["red"])]


def main() -> None:
    result = gao_overlap.compute()
    frame = gao_overlap.records()
    counts = frame.category.value_counts()

    # 5.6 in, not 6.4. At 6.4 the plot boxes came out 1.23 x 1.49 in -- portrait
    # slots for landscape data, which is half of why the panels read as too small
    # for what is in them. This puts them at roughly square.
    figure, panel = canvas(3, 3, height=5.6)

    for row, (y, ylabel, columns) in enumerate(ROWS):
        for column, (x, xlabel, xview) in enumerate(columns):
            index = row * 3 + column
            axis = panel[index]
            space = gao_overlap.condition_space(frame, x, y)
            long = pd.concat([space["this work"].assign(dataset="this work"),
                              space["hand-curated"].assign(dataset="Gao et al.")])
            kde2d(axis, long, x, y, hue="dataset", order=["this work", "Gao et al."],
                  clip=(xview, (0, 100)), xlabel=xlabel,
                  ylabel=ylabel if column == 0 else "", label=False)

            # A tenth of the range as margin, not a twentieth. Yield and selectivity are
            # populated across their whole range, so the density is nonzero at both bounds and
            # a thin margin left it drawn hard against the frame -- which is what "the graphs
            # overflow" was: not paths outside the axes, but no white anywhere around them.
            pad_x = (xview[1] - xview[0]) * 0.05
            axis.set_xlim(xview[0] - pad_x, xview[1] + pad_x)
            axis.set_ylim(-10, 110)
            if column:
                axis.tick_params(axis="y", labelleft=False)
            axis.annotate(f"n={len(space['this work'])} / {len(space['hand-curated'])}",
                          (1.0, 1.02), xycoords="axes fraction", ha="right", va="bottom",
                          fontsize=5.4, color=DIM)

    # --- g: why the two sets differ in size ---------------------------------------------------
    axis = panel[6]
    shared, ours_only = int(counts["both"]), int(counts["ours"])
    rows = [(label, -int(counts[key]), colour) for key, label, colour in REASONS]
    rows.append(("we hold it and Gao does not", ours_only, CATEGORICAL["blue"]))
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
    axis.set_yticks(range(len(rows)), [label for label, *_ in reversed(rows)], fontsize=5.2)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(-215, 150)
    ticks = [-200, -100, 0, 100]
    axis.set_xticks(ticks, [str(abs(v)) for v in ticks])
    axis.set_xlabel(f"records, {shared} shared")

    # --- h: on the records both hold, do they agree -------------------------------------------
    axis = panel[7]
    agree = result["agreement"].sort_values("share")
    for position, (field, row) in enumerate(agree.iterrows()):
        axis.barh(position, row["share"] * 100, height=0.62,
                  color=CATEGORICAL["blue"] if row["share"] >= 0.9 else CATEGORICAL["red"])
        axis.annotate(f"{row['share']:.0%} of {int(row['both report it'])}",
                      (row["share"] * 100, position), xytext=(3, 0),
                      textcoords="offset points", va="center", fontsize=5.2, color=DIM)
    axis.set_yticks(range(len(agree)),
                    [str(name).replace("_", " ") for name in agree.index], fontsize=5.2)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 142)
    axis.set_xticks([0, 50, 100])
    axis.set_xlabel("shared records agreeing, per field")

    # --- i: how much of a record each side fills in ------------------------------------------
    # The third question the section never asked. (g) says why the two sets differ in size and
    # (h) says whether they agree where they meet; neither says whether an extraction reports
    # as much per record as a person does. Hand curation fills every condition field on every
    # record; this extraction fills 84 to 97% of them, and selectivity is the one real gap.
    axis = panel[8]
    full = result["completeness"] * 100
    order = full.mean(axis=1).sort_values().index
    positions = range(len(order))
    axis.barh([p + 0.19 for p in positions], full.loc[order, "hand-curated"], height=0.36,
              color=CATEGORICAL["red"], label="hand-curated")
    axis.barh([p - 0.19 for p in positions], full.loc[order, "this work"], height=0.36,
              color=CATEGORICAL["blue"], label="this work")
    for position, field in enumerate(order):
        gap = full.loc[field, "hand-curated"] - full.loc[field, "this work"]
        if gap >= 5:
            axis.annotate(f"$-${gap:.0f}", (full.loc[field, "hand-curated"], position),
                          xytext=(3, 0), textcoords="offset points", va="center",
                          fontsize=5.2, color=DIM)
    axis.set_yticks(list(positions),
                    [str(name).replace("_", " ") for name in order], fontsize=5.2)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 122)
    axis.set_xticks([0, 50, 100])
    axis.set_xlabel("field reported (%)")
    # Above the bars, not among them: the panel is sorted ascending, so the free space is at
    # the bottom right, which is exactly where the short bars and their gap labels are.
    axis.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False,
                fontsize=5.4, handlelength=0.9, handletextpad=0.35, borderpad=0.0,
                columnspacing=1.0)

    save(figure, "fig_gao")


if __name__ == "__main__":
    main()
