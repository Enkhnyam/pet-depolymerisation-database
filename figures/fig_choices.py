"""SI -- the settings this work chose, and what each one is worth.

Six panels answering the same question six times: was this tuned until the number looked good?

(a)-(c) The metric grader's three thresholds, swept. The answer a reader wants is visible without
reading a word: every chosen value sits *below* its own optimum. Moving the acceptance cutoff off
0.30 would add F1, so would loosening the catalyst gate, so would widening the numeric tolerance
-- and none of them were moved, because the optimum is measured on the same 24 papers the score
is computed from and chasing it there is tuning on the test set. The gaps are reported instead.

(d) Worked examples. One beats none; nothing between two and five beats one. The chosen setting is
also the cheapest, which is the kind of coincidence worth stating rather than leaning on.

(e) Source tracking, adopted for provenance and apparently also worth F1. Three repeats an arm
cannot carry the claim to significance and the panel shows the repeats rather than an interval,
so a reader can see how much of the gap is spread.

(f) Does paying more buy anything? Not a plane of score against cost, which is what this was and
what made it unreadable: cost is the variable the panel is about and the one the arms are least
separated on -- seven of the eight between nothing and $0.22, the eighth at $1.23. Rows sorted by
price instead, one arm each, score the only axis. Prices rise down the column and scores do not
follow; the step line is the best score anything at that price or less reached, so a dot left of
it is an arm beaten on both counts.
"""
import numpy as np
import seaborn as sns
from matplotlib.lines import Line2D

from _style import CATEGORICAL, DIM, EMPHASIS, INK, RAMP, RULE, canvas, save
from curated import extractions, shots, source_tracking, thresholds

# The value each threshold actually ships at, read from the check rather than repeated here.
import _setup

# The extractors as (f) names them. Short forms: the caption spells each one out in full, and a
# row label three words wide would take the axis with it.
MODELS = {"oss": "gpt-oss", "luna": "luna", "terra": "terra"}

SWEEPS = [("accept", _setup.ACCEPT, "acceptance cutoff $\\tau$"),
          ("catalyst", _setup.CATALYST, "catalyst similarity gate"),
          ("tolerance", _setup.TOLERANCE, "numeric tolerance")]


def main() -> None:
    sweeps = thresholds.compute()
    figure, panel = canvas(2, 3, height=4.0)

    # --- a-c: each threshold swept, with the shipped value marked -----------------------------
    for index, (name, shipped, label) in enumerate(SWEEPS):
        axis = panel[index]
        frame = sweeps[name]
        axis.plot(frame.index, frame.f1, color=RAMP[2], lw=1.0, marker="o", ms=2.6,
                  markerfacecolor="white", markeredgewidth=0.8)
        best = frame.f1.idxmax()
        axis.plot([best], [frame.f1.max()], marker="o", ms=4.2, color=CATEGORICAL["yellow"],
                  markeredgecolor="white", markeredgewidth=0.6, zorder=5)
        axis.plot([shipped], [frame.f1.loc[shipped]], marker="D", ms=4.2, color=EMPHASIS,
                  markeredgecolor="white", markeredgewidth=0.6, zorder=6)
        gap = frame.f1.max() - frame.f1.loc[shipped]
        # The numbers go on the axis label, not into the plot. Any in-plot position that has
        # room on one sweep sits on the curve in the next -- these three curves rise, fall and
        # rise again -- and an annotation touching the line it describes is the one thing a
        # panel this small cannot afford.
        axis.set_xlabel(f"{label}\nshipped {shipped:g} · peak {best:g} · "
                        f"{gap:+.3f} $F_1$")
        axis.set_ylabel("$F_1$ on the benchmark" if index == 0 else "")
        span = frame.f1.max() - frame.f1.min()
        axis.set_ylim(frame.f1.min() - span * 0.35, frame.f1.max() + span * 0.22)

    # --- d: worked examples, every repeat shown -----------------------------------------------
    # A mean with an error bar over three points hides that the arms overlap. The repeats are
    # the honest mark at this sample size, and the line joins the arm means.
    axis = panel[3]
    arms = shots.compute()
    # stripplot's jitter draws from numpy's global RNG, so the panel came out different on every
    # run and FIGURES_CHECK reported the figure stale forever. Seeded here: a figure that cannot
    # be reproduced byte for byte cannot be checked against the data that made it.
    np.random.seed(0)
    sns.stripplot(data=arms, x="n_shots", y="f1", ax=axis, size=2.8, color=RAMP[2],
                  alpha=0.8, jitter=0.12, legend=False)
    means = arms.groupby("n_shots").f1.mean()
    axis.plot(range(len(means)), means.values, color=INK, lw=0.8, zorder=4)
    shipped = int(_setup.DATABASE_SHOTS) if hasattr(_setup, "DATABASE_SHOTS") else 1
    axis.plot([list(means.index).index(shipped)], [means.loc[shipped]], marker="D", ms=4.2,
              color=EMPHASIS, markeredgecolor="white", markeredgewidth=0.6, zorder=6)
    axis.set_xlabel(f"worked examples in the prompt\nshipped {shipped} · "
                    f"every repeat plotted")
    axis.set_ylabel("$F_1$ on the benchmark")

    # --- e: source tracking on and off --------------------------------------------------------
    axis = axis = panel[4]
    src = source_tracking.compute()
    names = list(src.index)
    for position, name in enumerate(names):
        row = src.loc[name]
        colour = CATEGORICAL["blue"] if name == "citing sources" else DIM
        axis.errorbar(position, row["mean"], yerr=row["std"], fmt="none", ecolor=INK,
                      elinewidth=0.7, capsize=2.6, zorder=3)
        axis.plot([position], [row["mean"]], marker="o", ms=5.0, color=colour,
                  markeredgecolor="white", markeredgewidth=0.7, zorder=4)
        axis.annotate(f"{row['mean']:.3f}\n$\\pm${row['std']:.3f}",
                      (position, row["mean"]), xytext=(8, 0),
                      textcoords="offset points", va="center", fontsize=5.4, color=DIM)
    axis.set_xticks(range(len(names)), [n.replace(" ", "\n") for n in names], fontsize=5.6)
    axis.tick_params(axis="x", length=0)
    axis.set_xlim(-0.5, len(names) + 0.2)
    axis.set_ylim(0.64, 0.86)
    axis.set_xlabel("")
    axis.set_ylabel("$F_1$, mean of three repeats")

    # --- f: does paying more buy anything? ---------------------------------------------------
    # Third form of this panel. It was a scatter of score against cost, which failed because cost
    # is the variable the panel is about and the one the arms are least separated on -- seven of
    # eight between nothing and $0.22, the eighth at $1.23 -- so any axis wide enough for terra
    # collapsed the rest into a labelled cloud. Sorting by price instead fixed that.
    #
    # What it then acquired was clutter. A staircase of the best score at each price ran through
    # the dots, and because it is a step function drawn over a scatter it read as a data series
    # connecting them -- the one thing it is not. A shaded band for the shipped arm's spread took
    # a third of the width, and the error bars already said what it said.
    #
    # Both are gone and neither claim is lost. Domination is a property of an arm, so it is drawn
    # on the arm: an arm that nothing cheaper beats is filled, an arm beaten on both price and
    # score at once is hollow. That is the same partition the staircase drew, read off one
    # marker instead of off a line and a position. The shipped arm keeps a single dashed rule so
    # a reader can drop a vertical from it; the error bars carry the spread.
    axis = panel[5]
    configs = extractions.configurations().sort_values("cost").reset_index(drop=True)
    shipped_row = configs[(configs.model == "luna")
                          & (configs.n_shots == int(_setup.DATABASE_SHOTS)
                             if hasattr(_setup, "DATABASE_SHOTS") else configs.n_shots == 1)]
    shipped_row = shipped_row.iloc[0]
    rows = len(configs)

    # One rule at what ships, to drop a vertical from. Behind everything.
    axis.axvline(shipped_row.f1, color=RULE, lw=0.9, ls=(0, (3, 2)), zorder=0)

    for index, row in configs.iterrows():
        top = rows - 1 - index
        ships = row.model == shipped_row.model and row.n_shots == shipped_row.n_shots
        frontier = bool(row["on frontier"])
        axis.errorbar(row.f1, top, xerr=row.sd, fmt="none",
                      ecolor=DIM if frontier else RULE, elinewidth=0.6, capsize=1.6, zorder=2)
        # filled = nothing cheaper beats it; hollow = beaten on price and score at once
        axis.plot([row.f1], [top], marker="D" if ships else "o", ms=4.6 if ships else 3.8,
                  color=(EMPHASIS if ships else RAMP[2]) if frontier else "white",
                  markeredgecolor=EMPHASIS if ships else (RAMP[2] if frontier else DIM),
                  markeredgewidth=0.6 if frontier else 0.9, zorder=3)
        # The price, in a column of its own past the axis, right-aligned so eight of them can be
        # compared digit by digit rather than by the length of anything.
        axis.annotate("free" if row.cost <= 0 else f"\\${row.cost:.2f}", (1.15, top),
                      xycoords=("axes fraction", "data"), ha="right", va="center",
                      fontsize=5.4, color=EMPHASIS if ships else DIM)

    axis.annotate("per run", (1.15, rows - 0.35), xycoords=("axes fraction", "data"),
                  ha="right", va="bottom", fontsize=5.2, color=DIM)
    axis.set_yticks(range(rows),
                    [f"{MODELS[row.model]} \u00b7 {row.n_shots}"
                     for row in configs.itertuples()][::-1],
                    fontsize=5.6)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_ylim(-0.5, rows - 0.15)
    axis.set_xlim(0.712, 0.832)
    axis.set_xticks([0.72, 0.76, 0.80])
    # That the rows run cheapest to dearest is not stated: the price column ascends, which says
    # it once and without a word. One line, because the marker now carries what three explained.
    axis.set_xlabel("$F_1$ on the benchmark, bars \u00b11 s.d.\n"
                    "hollow: beaten on price and score")

    # What the two marks in (a)-(d) mean. Without this a reader has a yellow dot and a dark
    # diamond on four panels and no way to tell which is the setting and which is the optimum.
    figure.legend(handles=[
        Line2D([], [], marker="D", ms=4.2, color=EMPHASIS, ls="none",
               markeredgecolor="white", markeredgewidth=0.6,
               label="the value the database ships"),
        Line2D([], [], marker="o", ms=4.2, color=CATEGORICAL["yellow"], ls="none",
               markeredgecolor="white", markeredgewidth=0.6,
               label="the best value on this sweep"),
    ], loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.015),
        handletextpad=0.3, columnspacing=1.8)
    save(figure, "fig_choices", legend_room=True)


if __name__ == "__main__":
    main()
