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
from matplotlib.ticker import NullLocator

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

    # --- f: what more money actually buys ----------------------------------------------------
    # Three versions of this panel argued one variable at a time -- this model against that one,
    # one worked example against none -- and the two interact, because an example is input
    # tokens on every paper. Every arm on one plane turns it into the question a reader has:
    # which configurations are not beaten on both counts at once.
    #
    # The shaded quadrant is what a Pareto argument is. Anything inside it costs more than the
    # shipped setting and scores less, so terra sitting there at eight times the price is the
    # panel's own conclusion rather than a sentence in the caption.
    axis = panel[5]
    configs = extractions.configurations()
    shipped_row = configs[(configs.model == "luna")
                          & (configs.n_shots == int(_setup.DATABASE_SHOTS)
                             if hasattr(_setup, "DATABASE_SHOTS") else configs.n_shots == 1)]
    shipped_row = shipped_row.iloc[0]

    # oss bills nothing at all, and a logarithmic axis has no room for zero. It sits at the
    # left-hand tick, which is labelled "free" rather than given a price it never had.
    FREE = 0.045
    place = lambda c: FREE if c <= 0 else c

    axis.fill_between([place(shipped_row.cost), 3], -1, shipped_row.f1,
                      color=RULE, alpha=0.55, zorder=0, linewidth=0)
    axis.annotate("dearer and worse", (2.6, 0.653), ha="right", fontsize=5.2, color=DIM)

    frontier = configs[configs["on frontier"]].sort_values("cost")
    axis.step([place(c) for c in frontier.cost], frontier.f1, where="post", color=RAMP[2],
              lw=1.0, zorder=2)

    for row in configs.itertuples():
        x = place(row.cost)
        edge = row._7                       # on frontier
        axis.errorbar(x, row.f1, yerr=row.sd, fmt="none", ecolor=DIM, elinewidth=0.5,
                      capsize=1.4, zorder=3)
        axis.plot([x], [row.f1], marker="o", ms=3.6, zorder=4,
                  color=RAMP[2] if edge else "white",
                  markeredgecolor=RAMP[2] if edge else DIM, markeredgewidth=0.9)
    axis.plot([place(shipped_row.cost)], [shipped_row.f1], marker="D", ms=5.0, color=EMPHASIS,
              markeredgecolor="white", markeredgewidth=0.7, zorder=6)

    for label, row, offset in (("gpt-oss", configs[configs.model == "oss"].iloc[0], (6, -8)),
                               ("terra", configs[configs.model == "terra"].iloc[0], (-6, -9)),
                               ("luna, 1 example", shipped_row, (4, 9))):
        axis.annotate(label, (place(row.cost), row.f1), xytext=offset,
                      textcoords="offset points", fontsize=5.6, color=DIM,
                      ha="right" if offset[0] < 0 else "left")

    axis.set_xscale("log")
    axis.set_xlim(0.030, 3.4)
    # A log axis labels its own minor ticks, and at this width they printed over the four that
    # carry the meaning.
    axis.xaxis.set_minor_locator(NullLocator())
    axis.set_xticks([FREE, 0.1, 0.3, 1.0], ["free", "\\$0.10", "\\$0.30", "\\$1"])
    axis.set_ylim(0.64, 0.86)
    axis.set_ylabel("")
    axis.set_xlabel("cost of one run\nfilled: on the frontier · hollow: beaten")

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
