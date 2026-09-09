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

(f) Cost against score. A logarithmic cost axis, which is the one place in this project a log
scale is right: the models differ by two orders of magnitude in price and by hundredths in F1.
The free judge is drawn at $0.01 so it has somewhere to sit.
"""
import numpy as np
import seaborn as sns
from matplotlib.lines import Line2D

from _style import CATEGORICAL, DIM, EMPHASIS, INK, RAMP, RULE, canvas, save
from curated import extractions, shots, source_tracking, thresholds

# The value each threshold actually ships at, read from the check rather than repeated here.
import _setup

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

    # --- f: what each model scores, and what it cost -----------------------------------------
    # This was a scatter on a logarithmic cost axis, with the free judge parked at $0.01 so it
    # had somewhere to sit and a grey rule at the best score that explained itself to nobody.
    # Two quantities about three models do not need a log scale: the score is the bar, the cost
    # is written on the end of it, and the reader can compare both by reading down the column.
    axis = panel[5]
    scores = extractions.compute().sort_values("f1")
    COSTS = {"luna": "\\$0.18", "terra": "\\$1.23", "oss": "free, unmetered"}
    best = scores.f1.idxmax()
    # Dots rather than bars. On a zero-based axis three scores between 0.754 and 0.805 are
    # three bars of the same length, and the 0.051 that separates the cheapest model from the
    # best one disappears. A dot carries no zero baseline to honour, so the axis can show the
    # range the models actually occupy.
    for position, name in enumerate(scores.index):
        row = scores.loc[name]
        axis.errorbar(row["f1"], position, xerr=row["f1 sd"], fmt="none", ecolor=INK,
                      elinewidth=0.7, capsize=2.2, zorder=3)
        axis.plot([row["f1"]], [position], marker="o", ms=5.4,
                  color=EMPHASIS if name == best else RAMP[2], markeredgecolor="white",
                  markeredgewidth=0.7, zorder=4)
        axis.annotate(f"{row['f1']:.3f}  ·  {COSTS[str(name)]}",
                      (row["f1"] + row["f1 sd"], position), xytext=(6, 0),
                      textcoords="offset points", va="center", fontsize=5.6, color=DIM)
    axis.set_yticks(range(len(scores)), [str(n) for n in scores.index], fontsize=6.5)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0.68, 0.90)
    axis.set_xticks([0.70, 0.75, 0.80, 0.85])
    axis.set_ylim(-0.6, len(scores) - 0.4)
    axis.set_xlabel("$F_1$ and the cost of one run\nmean of three repeats, bar the spread")

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
