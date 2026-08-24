"""Figure 4 -- the settings that were chosen, and what each is worth.

The three thresholds get a panel each rather than sharing one: they are measured on different
scales and mean different things, and drawing them on a common axis implied a comparison that
does not exist.
"""
import json

import pandas as pd

from _style import CYCLE, DIM, GRADER, canvas, caption, note, save
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
way}: all three chosen values (marked) sit \emph{below} their optimum on this data
(\textbf{a}--\textbf{c}). Moving the acceptance cutoff from 0.30 to 0.35 would add
__ACCEPT_GAP__ to $F_1$, the catalyst gate from 0.60 to 0.40 would add __CATALYST_GAP__, and the
numeric tolerance from 0.20 to 0.50 would add __TOLERANCE_GAP__. We report the gaps and leave the
thresholds where they are, because moving them now --- to maximise a score on the same 24 papers
the score is computed from --- is precisely the tuning we would be claiming not to have done.
A threshold set before the sweep and left there is worth more than three points of $F_1$.

The prompt settings are where the money is. \textbf{Having one worked example beats having none}
($+0.043$, $p=0.005$), but beyond one nothing separates the settings (\textbf{d}, one-way ANOVA
$p=0.55$). \textbf{The database is built with __SHOTS__} (marked), which is what that sweep
licences: the four examples an earlier run used cost roughly 40\,k tokens of context on every
paper and bought nothing measurable, so dropping to one halved the prompt at no cost in $F_1$.
Requiring each record to cite its source chunks looks like the opposite case (\textbf{e}):
$+__DELTA__$ in $F_1$ at $p=__P__$, short of significance across three runs an arm and reported
as such, but consistent in direction. Source tracking was adopted so numbers could be traced back
to sentences; on this evidence it may also be making the extraction better, which is a reason to
keep it even if provenance did not matter.

Model choice is a straight trade (\textbf{f}), drawn as a staircase because that is what a
frontier of three discrete options is: each step is the extra $F_1$ the next model buys and the
horizontal run before it is what that step costs. None of the three is dominated, so
\textbf{the choice is a budget decision, not a quality one}. Luna was chosen because the mass run
had to be affordable at a thousand papers rather than twenty-four; gpt-oss is free and is plotted
at \$0.01 so it can appear on a logarithmic axis at all."""


def main() -> None:
    figure, panel = canvas(2, 3, width=8.8, height=5.0)

    sweeps = thresholds_check.compute()
    for position, (name, frame) in enumerate(sweeps.items()):
        axis = panel[position]
        axis.plot(frame.index, frame["f1"], marker="o", ms=3.5, lw=1.3,
                  color=CYCLE[position % len(CYCLE)])
        axis.axvline(CHOSEN[name], color="#A33A2E", lw=1, ls="--", zorder=0)
        axis.set_xlabel(f"{name} threshold")
        axis.set_ylabel("F1" if position == 0 else "")

    raw = shots_check.compute()
    if raw is not None:
        shots = raw.groupby("n_shots").f1.agg(["mean", "std"])
        panel[3].errorbar(shots.index, shots["mean"], yerr=shots["std"], marker="o",
                          ms=3.5, lw=1.3, capsize=2.5, color=GRADER["metric"])
        used = shots_used()
        panel[3].axvline(used, color="#A33A2E", lw=1, ls="--", zorder=0)
        panel[3].annotate(f"{used} used", (used, panel[3].get_ylim()[0]),
                          textcoords="offset points", xytext=(4, 6), fontsize=6, color="#A33A2E")
    panel[3].set_xlabel("worked examples")
    panel[3].set_ylabel("F1")

    arms = source_check.compute()
    panel[4].bar(range(len(arms)), arms["mean"], yerr=arms["std"], capsize=4, width=0.5,
                 color=[GRADER["metric"], "#C9D6D3"])
    panel[4].set_xticks(range(len(arms)), ["citing\nsources", "not\nciting"])
    panel[4].set_ylabel("")
    panel[4].set_ylim(0.60, 0.75)

    # the frontier: nothing above and to the left of a point on it
    scores = extractions_check.compute()
    ledger = cost_check.compute().set_index("run")
    trade = []
    for model in scores.index:
        match = [r for r in ledger.index if f"extract_{model}/" in r]
        if match:
            trade.append({"model": model, "cost": max(ledger.loc[match[0], "cost_usd"], 0.01),
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
    panel[5].plot(steps_x, steps_y, color="#C9D6D3", lw=1.6, zorder=1, solid_joinstyle="miter")

    for offset, row in enumerate(trade.itertuples()):
        panel[5].scatter([row.cost], [row.f1], s=46, zorder=3,
                         color=CYCLE[offset % len(CYCLE)])
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

    gaps = {name: frame["f1"].max() - frame["f1"].loc[CHOSEN[name]]
            for name, frame in sweeps.items()}
    delta = arms["mean"].get("citing sources", 0) - arms["mean"].get("not citing", 0)
    print("\n" + caption(
        CAPTION,
        accept_gap=f"{gaps['accept']:.3f}", catalyst_gap=f"{gaps['catalyst']:.3f}",
        tolerance_gap=f"{gaps['tolerance']:.3f}",
        delta=f"{delta:.3f}", p=f"{arms.attrs.get('p', float('nan')):.3f}",
        shots={0: "no examples", 1: "one worked example"}.get(
            shots_used(), f"{shots_used()} worked examples")))


if __name__ == "__main__":
    main()
