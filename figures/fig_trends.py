"""Whether the extracted chemistry behaves, tested on every relationship that predicts a sign.

The selection rule is stated before the data is looked at, which is the only thing that makes a
panel like this evidence rather than a search. checks/database/withinpaper.py holds four pairs of
fields whose sign chemistry predicts -- hotter gives more, more catalyst gives more, hotter
finishes sooner, longer gives more -- and all four are drawn. Showing the strongest of them alone,
which is what the manuscript did with one panel, is selection on the outcome.

The finding is that pooling destroys all four and looking within a paper recovers three. Published
experiments span PET feedstock forms, catalyst activities and scales, so a correlation computed
across the corpus is a correlation across study designs: every pooled coefficient sits within
0.06 of zero. Compared with itself, a paper shows the predicted sign.

The fourth relationship does not hold, and it is on the figure for that reason. "Longer gives
more" reaches a median rho of +0.06 across 82 papers, with 57% running the predicted way, at
p = 0.06. A pipeline that manufactured agreeable correlations would not have produced a null,
so the null is part of the evidence that the other three are real.
"""
import pandas as pd
import seaborn as sns

from _style import CATEGORICAL, DIM, INK, RAMP, RULE, canvas, save, sci
from database import withinpaper as wp


def main() -> None:
    result = wp.compute()
    table, per_paper = result["table"], result["per paper"]
    order = list(table.index)

    long = pd.concat([pd.DataFrame({"relationship": name, "rho": values.values})
                      for name, values in per_paper.items()])

    figure, panel = canvas(1, 2, height=2.55)

    # --- a: every paper's own correlation, against the pooled one -----------------------------
    # One dot per paper, the box for the middle of them, and a diamond for the pooled figure the
    # same computation returns. The contrast is the panel: the diamonds cluster on zero and the
    # boxes do not.
    axis = panel[0]
    sns.stripplot(data=long, x="rho", y="relationship", order=order, ax=axis, size=2.0,
                  color=RAMP[2], alpha=0.55, jitter=0.3, legend=False)
    sns.boxplot(data=long, x="rho", y="relationship", order=order, ax=axis, width=0.44,
                showfliers=False, whis=(10, 90),
                boxprops=dict(facecolor="none", edgecolor=INK, linewidth=0.6),
                whiskerprops=dict(color=INK, linewidth=0.6),
                capprops=dict(color=INK, linewidth=0.6),
                medianprops=dict(color=CATEGORICAL["blue"], linewidth=1.4))
    for position, name in enumerate(order):
        axis.plot([table.loc[name, "pooled"]], [position], marker="D", ms=3.6,
                  color=CATEGORICAL["yellow"], markeredgecolor="white", markeredgewidth=0.5,
                  zorder=6, clip_on=False)
    axis.axvline(0, color=RULE, lw=0.8, zorder=0)
    axis.set_yticks(range(len(order)), [name.replace(" gives", "\ngives") for name in order],
                    fontsize=6)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(-1.05, 1.05)
    axis.set_xlabel("Spearman $\\rho$ — dot per paper, bar the median, diamond pooled")
    axis.set_ylabel("")

    # --- b: how many papers run the way chemistry says ----------------------------------------
    # The same four relationships as a share, because a median rho does not say how consistent
    # the papers were and a reader asks that immediately. 50% is the line a coin would reach and
    # is drawn, so "57%" is visibly close to it.
    axis = panel[1]
    share = table["as predicted"] * 100
    # Rows top-down in the same order as (a). seaborn puts a categorical y's first level at the
    # top and barh puts index 0 at the bottom, so drawing both from the same list silently
    # mirrors one against the other -- and with no y labels on this panel there is nothing to
    # give it away.
    for position, name in enumerate(order):
        y = len(order) - 1 - position
        value = table.loc[name, "p"]
        stat = f"$p = {sci(value)}$" if value < 0.01 else f"$p = {value:.2f}$"
        axis.barh(y, share[name], height=0.6,
                  color=CATEGORICAL["blue"] if value < 0.05 else DIM)
        axis.annotate(f"{share[name]:.0f}% of {int(table.loc[name, 'papers'])} papers, {stat}",
                      (share[name], y), xytext=(4, 0), textcoords="offset points",
                      va="center", fontsize=5.4, color=DIM)
    axis.axvline(50, color=INK, lw=0.7, ls=(0, (3, 2)), zorder=3)
    axis.annotate("a coin reaches here", (50, -0.42), xytext=(4, 0),
                  textcoords="offset points", fontsize=5.4, color=DIM, va="center")
    axis.set_yticks(range(len(order)), ["" for _ in order])
    axis.set_ylim(-0.6, len(order) - 0.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 155)
    axis.set_xticks([0, 25, 50, 75, 100])
    axis.set_xlabel("papers whose correlation runs the predicted way (%)")

    save(figure, "fig_trends")


if __name__ == "__main__":
    main()
