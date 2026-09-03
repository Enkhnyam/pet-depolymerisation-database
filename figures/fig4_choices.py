"""Figure 4 -- the settings that were chosen, and what each is worth.

The three thresholds get a panel each rather than sharing one: they are measured on different
scales and mean different things, and drawing them on a common axis implied a comparison that
does not exist.
"""
import json

import pandas as pd

from _style import DIM, GUIDE, INK, NEUTRAL, WARN, canvas, caption, note, save
from _setup import DATABASE          # after _style: importing it is what puts checks/ on the path
from curated import extractions as extractions_check
from curated import shots as shots_check
from curated import source_tracking as source_check
from curated import thresholds as thresholds_check
import cost as cost_check

CHOSEN = {"accept": 0.30, "catalyst": 0.60, "tolerance": 0.20}


def shots_used() -> int:
    """How many worked examples the database run actually used.

    Read from the run's own config rather than written here: this was hardcoded to 4, and stayed
    at 4 marking the wrong point on panel (d) after the database was rebuilt with one.
    """
    config = json.loads((DATABASE / "config.json").read_text())
    return int(config["harness_params"]["n_shots"])

CAPTION = r"""\textbf{Four settings, and what each one is worth.}
The metric grader has three thresholds, and the first question about any of them is whether they
were tuned until the number looked good. \textbf{They were not, and the sweeps show it the hard
way}: all three chosen values (marked) sit \emph{below} their optimum on the shipped extraction
(\textbf{a}--\textbf{c}). Moving the acceptance cutoff from 0.30 to __ACCEPT_BEST__ would add
__ACCEPT_GAP__ to $F_1$, the catalyst gate from 0.60 to __CATALYST_BEST__ would add
__CATALYST_GAP__, and the numeric tolerance from 0.20 to __TOLERANCE_BEST__ would add
__TOLERANCE_GAP__. We report the gaps and leave the thresholds where they are: moving them to maximise a score on
the same 24 papers the score is computed from would be tuning on the test set.

More worked examples do not help (\textbf{d}). One example rather than none is worth
$__SHOTDELTA__$ in $F_1$ at $p = __SHOTP__$, short of significance at three runs an arm. A one-way
ANOVA over the arms with at least one example gives $p = __ANOVAP__$, and __BESTSHOTS__ example has
the highest mean, but no arm between two and five differs from it by more than noise once the
several comparisons involved are taken into account. The database is built with __SHOTS__
(marked), which is also the cheapest setting: four examples add roughly 40\,k tokens of context to
every paper.
Requiring each record to cite its source chunks looks like the opposite case (\textbf{e}):
$+__DELTA__$ in $F_1$ at $p=__P__$, short of significance across three runs an arm and reported
as such, but consistent in direction. Source tracking was adopted so numbers could be traced back
to sentences; on this evidence it may also be making the extraction better, which is a reason to
keep it even if provenance did not matter.

Cost and quality do not trade off across all three models (\textbf{f}). Scored at the setting the
database ships and averaged over repeats, __FRONTIER_BEST__ is the most accurate model and also
the cheaper one, so only __FRONTIER_DOMINATED__ A choice does remain at the cheap
end: gpt-oss is free and scores __FRONTIER_LOW_F1__ against __FRONTIER_BEST__'s
__FRONTIER_BEST_F1__, so __FRONTIER_GAP__ of $F_1$ costs __FRONTIER_RATIO__ times as much.
gpt-oss is plotted at \$0.01 so it appears on a logarithmic axis."""


def main() -> None:
    figure, panel = canvas(2, 3, height=4.03)

    sweeps = thresholds_check.compute()
    for position, (name, frame) in enumerate(sweeps.items()):
        axis = panel[position]
        # one colour across the three sweeps: they are the same quantity measured against three
        # different knobs, and giving each its own hue implied three different things were plotted
        axis.plot(frame.index, frame["f1"], marker="o", ms=3.5, lw=1.3, color=NEUTRAL)
        axis.axvline(CHOSEN[name], color=WARN, lw=1, ls="--", zorder=0)
        axis.set_xlabel(f"{name} threshold")
        axis.set_ylabel("F1" if position == 0 else "")

    raw = shots_check.compute()
    contrast = shots_check.contrast(raw) if raw is not None else {
        "delta": float("nan"), "p": float("nan"), "anova_p": float("nan"), "best": 0}
    if raw is not None:
        shots = shots_check.summary(raw)
        panel[3].errorbar(shots.index, shots["mean"], yerr=shots["std"], marker="o",
                          ms=3.5, lw=1.3, capsize=2.5, color=NEUTRAL)
        used = shots_used()
        panel[3].axvline(used, color=WARN, lw=1, ls="--", zorder=0)
        panel[3].annotate(f"{used} used", (used, panel[3].get_ylim()[0]),
                          textcoords="offset points", xytext=(4, 6), fontsize=6, color=WARN)
    panel[3].set_xlabel("worked examples")
    panel[3].set_ylabel("F1")

    arms = source_check.compute()
    # ecolor: matplotlib defaults error bars to pure black, the only true black on the page
    panel[4].bar(range(len(arms)), arms["mean"], yerr=arms["std"], capsize=4, width=0.5,
                 ecolor=INK, error_kw={"lw": 1.0},
                 color=[NEUTRAL, GUIDE])
    panel[4].set_xticks(range(len(arms)), ["citing\nsources", "not\nciting"])
    panel[4].set_ylabel("")
    # fit the whiskers, not the bars: a fixed top clipped the citing arm's error bar off the
    # panel entirely, so the arm with the larger uncertainty looked like the certain one
    span = (arms["mean"] + arms["std"]).max() - (arms["mean"] - arms["std"]).min()
    panel[4].set_ylim((arms["mean"] - arms["std"]).min() - span * 0.25,
                      (arms["mean"] + arms["std"]).max() + span * 0.15)

    # The frontier: nothing above and to the left of a point on it.
    #
    # Cost is averaged over the same runs the score is averaged over. Taking the first run that
    # matched the model name was fine while each model had exactly one; with repeats it picked an
    # arbitrary one, and could pair a score from the one-example arm with the price of the
    # four-example arm -- which is roughly two and a half times the prompt.
    scores = extractions_check.compute()
    every = extractions_check.runs()
    ledger = cost_check.compute().set_index("run")
    trade = []
    for model in scores.index:
        arm = every[(every.model == model) & (every.n_shots == scores.loc[model, "n_shots"])]
        costs = [ledger.loc[key, "cost_usd"] for name in arm.run
                 for key in ledger.index if key.endswith("/" + name)]
        if costs:
            trade.append({"model": model, "cost": max(sum(costs) / len(costs), 0.01),
                          "f1": scores.loc[model, "f1"]})
    trade = pd.DataFrame(trade).sort_values("cost")

    frontier, best = [], -1.0
    for row in trade.itertuples():
        if row.f1 > best:
            frontier.append(row)
            best = row.f1
    # A staircase, not a straight line between points: the segment joining two models is not a
    # set of achievable intermediate options, and drawing it as a slope invited reading one off.
    # Each riser is the F1 the next model buys; each tread is what you pay to get there.
    steps_x, steps_y = [], []
    for row in frontier:
        if steps_x:
            steps_x.append(row.cost)
            steps_y.append(steps_y[-1])
        steps_x.append(row.cost)
        steps_y.append(row.f1)
    panel[5].plot(steps_x, steps_y, color=GUIDE, lw=1.6, zorder=1, solid_joinstyle="miter")

    for row in trade.itertuples():
        # NEUTRAL like every other panel on this canvas: each point is already labelled with its
        # model, so three hues would be decoration, and decoration here is the only colour on the
        # page that means nothing
        panel[5].scatter([row.cost], [row.f1], s=46, zorder=3, color=NEUTRAL)
        # labels below-right, where the staircase never runs, so none sits on a line
        panel[5].annotate(f"{row.model}\n${row.cost:.2f}", (row.cost, row.f1),
                          textcoords="offset points", xytext=(7, -9), fontsize=6,
                          ha="left", va="top", color=DIM, linespacing=1.25)
    panel[5].set_xscale("log")
    panel[5].set_xlabel("cost of 24 papers (USD, log)")
    panel[5].set_ylabel("F1")
    # margins on a log axis are in decades, so the generous value used for the linear panels
    # opened five decades of empty space around three points
    panel[5].margins(x=0.18, y=0.34)

    save(figure, "fig4_choices")

    leader = trade.loc[trade.f1.idxmax()]
    gaps = {name: frame["f1"].max() - frame["f1"].loc[CHOSEN[name]]
            for name, frame in sweeps.items()}
    # where the optimum actually sits, rather than where it sat the last time this was written by
    # hand: repointing the checks at the shipped extraction moved the acceptance optimum from
    # 0.35 to 0.50, and a caption naming the old destination would have been quietly wrong
    best = {name: frame["f1"].idxmax() for name, frame in sweeps.items()}
    delta = arms["mean"].get("citing sources", 0) - arms["mean"].get("not citing", 0)
    print("\n" + caption(
        CAPTION,
        accept_gap=f"{gaps['accept']:.3f}", catalyst_gap=f"{gaps['catalyst']:.3f}",
        tolerance_gap=f"{gaps['tolerance']:.3f}",
        accept_best=f"{best['accept']:g}", catalyst_best=f"{best['catalyst']:g}",
        tolerance_best=f"{best['tolerance']:g}",
        frontier_best=leader["model"],
        frontier_low_f1=f"{trade.f1.min():.3f}",
        frontier_best_f1=f"{leader['f1']:.3f}",
        frontier_gap=f"{leader['f1'] - trade.f1.min():.3f}",
        frontier_ratio=f"{leader['cost'] / max(trade.cost.min(), 0.01):.0f}",
        frontier_dominated=(
            "; ".join(f"{row.model}, which costs \\${row.cost:.2f} against "
                      f"\\${leader['cost']:.2f} and scores lower,"
                      for row in trade.itertuples() if row.model != leader["model"]
                      and row.f1 < leader["f1"] and row.cost > leader["cost"]) or
            "no model is strictly dominated") + " is dominated.",
        delta=f"{delta:.3f}", p=f"{arms.attrs.get('p', float('nan')):.3f}",
        shotdelta=f"{contrast['delta']:+.3f}", shotp=f"{contrast['p']:.3f}",
        anovap=f"{contrast['anova_p']:.2f}",
        bestshots={0: "none", 1: "one"}.get(contrast["best"], str(contrast["best"])),
        shots={0: "no examples", 1: "one worked example"}.get(
            shots_used(), f"{shots_used()} worked examples")))


if __name__ == "__main__":
    main()
