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
import matplotlib.pyplot as plt
import pandas as pd

from _style import CATEGORICAL, DIM, INK, RAMP, RAMP_RED, canvas, kde2d, save
from curated import gao_overlap

# Six pairs, the first being the main text's.
PAIRS = [("temperature_c", "yield_percent", "temperature (°C)", "yield (%)",
          ((140, 210), (0, 100))),
         ("temperature_c", "conversion_percent", "temperature (°C)", "conversion (%)",
          ((140, 210), (0, 100))),
         ("conversion_percent", "yield_percent", "conversion (%)", "yield (%)",
          ((0, 100), (0, 100))),
         ("temperature_c", "selectivity_percent", "temperature (°C)", "selectivity (%)",
          ((140, 210), (0, 100))),
         ("PET_amount_g", "yield_percent", "PET (g, $\\log_{10}$)", "yield (%)",
          ((-2.2, 1.6), (0, 100))),
         ("catalyst_amount_g", "yield_percent", "catalyst (g, $\\log_{10}$)", "yield (%)",
          ((-3.2, 0.8), (0, 100)))]

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

    figure, panel = canvas(3, 3, height=6.4)

    for index, (x, y, xlabel, ylabel, view) in enumerate(PAIRS):
        space = gao_overlap.condition_space(frame, x, y)
        long = pd.concat([space["this work"].assign(dataset="this work"),
                          space["hand-curated"].assign(dataset="Gao et al.")])
        kde2d(panel[index], long, x, y, hue="dataset", order=["this work", "Gao et al."],
              # Every panel labels its own y: the pairs vary across a row, so the leftmost
              # label would have claimed panel b's conversion axis was a yield axis.
              clip=view, xlabel=xlabel, ylabel=ylabel, label=False)
        panel[index].set_xlim(*view[0])
        panel[index].set_ylim(*view[1])
        # Above the frame, not inside it: at the bottom right the fill reaches the corner and
        # the count was printed underneath a density.
        panel[index].annotate(f"n={len(space['this work'])} / {len(space['hand-curated'])}",
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

    # --- i: the key, in the cell the grid leaves over -----------------------------------------
    axis = panel[8]
    axis.set_axis_off()
    axis.text(0.02, 0.93, "each panel above: two filled densities,", transform=axis.transAxes,
              fontsize=6, color=DIM)
    axis.text(0.02, 0.85, "light at the edge, dark at the core", transform=axis.transAxes,
              fontsize=6, color=DIM)
    for row, (name, ramp) in enumerate((("this work", RAMP), ("Gao et al.", RAMP_RED))):
        for step, colour in enumerate(ramp[:4][::-1]):
            axis.add_patch(plt.Rectangle((0.04 + step * 0.08, 0.60 - row * 0.17), 0.08, 0.09,
                                         transform=axis.transAxes, facecolor=colour,
                                         edgecolor="none", clip_on=False))
        axis.text(0.40, 0.645 - row * 0.17, name, transform=axis.transAxes, fontsize=6.5,
                  color=ramp[1], fontweight="bold", va="center")
    axis.text(0.02, 0.24, "n = this work / Gao, the records\neach side reports for that pair",
              transform=axis.transAxes, fontsize=6, color=DIM)

    save(figure, "fig_gao")


if __name__ == "__main__":
    main()
