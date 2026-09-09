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

# Six pairs, the first being the main text's.
PAIRS = [("temperature_c", "yield_percent", "temperature (°C)", "yield (%)",
          ((132, 218), (0, 100))),
         ("temperature_c", "conversion_percent", "temperature (°C)", "conversion (%)",
          ((132, 218), (0, 100))),
         ("conversion_percent", "yield_percent", "conversion (%)", "yield (%)",
          ((0, 100), (0, 100))),
         ("temperature_c", "selectivity_percent", "temperature (°C)", "selectivity (%)",
          ((132, 218), (0, 100))),
         ("PET_amount_g", "yield_percent", "PET (g, $\\log_{10}$)", "yield (%)",
          ((-2.8, 2.2), (0, 100))),
         ("catalyst_amount_g", "yield_percent", "catalyst (g, $\\log_{10}$)", "yield (%)",
          ((-3.8, 1.4), (0, 100)))]

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
        # A margin outside the estimate, so nothing is drawn against the frame. Where a field
        # has a real bound the density is cut at it, and the cut belongs inside white space
        # where it reads as a bound rather than as a figure running off its own edge.
        pad_x = (view[0][1] - view[0][0]) * 0.03
        pad_y = (view[1][1] - view[1][0]) * 0.04
        panel[index].set_xlim(view[0][0] - pad_x, view[0][1] + pad_x)
        panel[index].set_ylim(view[1][0] - pad_y, view[1][1] + pad_y)
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

    # --- i: the shared records, value against value ------------------------------------------
    # A key was here, and a key is not worth a ninth of a figure. This is the comparison the
    # section is actually about, one point per shared value rather than a share per field: on
    # the three percentage fields, every one of the 239 values both datasets report falls within
    # GaoParitySlack points of the other. A scatter that is a clean diagonal is the strongest
    # form that claim has, and it also shows there is no systematic offset between the two.
    axis = panel[8]
    parity = result["parity"]
    pct = parity[parity.field.str.endswith("_percent")]
    fields = list(dict.fromkeys(pct.field))
    for name, colour in zip(fields, SLOTS):
        part = pct[pct.field == name]
        axis.scatter(part.gao, part.ours, s=5.0, color=colour, alpha=0.75, linewidths=0,
                     label=str(name).replace("_percent", " %").replace("_", " "))
    axis.plot([0, 100], [0, 100], color="white", lw=1.6, zorder=1)
    axis.plot([0, 100], [0, 100], color=INK, lw=0.7, zorder=2)
    axis.set_xlim(-4, 104)
    axis.set_ylim(-4, 104)
    axis.set_xlabel(f"Gao et al. (%), {len(pct)} values")
    axis.set_ylabel("this work (%)")
    axis.legend(loc="lower right", frameon=False, fontsize=5.2, handletextpad=0.15,
                borderpad=0.0, labelspacing=0.25, markerscale=1.3)

    save(figure, "fig_gao")


if __name__ == "__main__":
    main()
