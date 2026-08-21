"""Figure 4 -- the settings that were chosen, and what each is worth.

The three thresholds get a panel each rather than sharing one: they are measured on different
scales and mean different things, and drawing them on a common axis implied a comparison that
does not exist.
"""
import pandas as pd

from _style import CYCLE, GRADER, canvas, caption, note, save
from curated import extractions as extractions_check
from curated import shots as shots_check
from curated import source_tracking as source_check
from curated import thresholds as thresholds_check
import cost as cost_check

CHOSEN = {"accept": 0.30, "catalyst": 0.60, "tolerance": 0.20}

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
$p=0.55$). \textbf{The database was built with four}, which on this evidence buys nothing and
costs roughly 40\,k tokens on every paper --- the clearest saving available to a future run.
Requiring each record to cite its source chunks looks like the opposite case (\textbf{e}):
$+__DELTA__$ in $F_1$ at $p=__P__$, short of significance across three runs an arm and reported
as such, but consistent in direction. Source tracking was adopted so numbers could be traced back
to sentences; on this evidence it may also be making the extraction better, which is a reason to
keep it even if provenance did not matter.

Model choice is a straight trade (\textbf{f}). Terra extracts best and costs roughly ten times
what luna does; gpt-oss is free and weakest. All three sit on the frontier, so none is dominated
--- \textbf{the choice is a budget decision, not a quality one}, and luna was chosen because the
mass run had to be affordable at four hundred papers rather than twenty-four."""


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
        panel[3].axvline(4, color="#A33A2E", lw=1, ls="--", zorder=0)
        note(panel[3], "used", x=0.72, y=0.08)
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
    panel[5].plot([r.cost for r in frontier], [r.f1 for r in frontier],
                  color="#C9D6D3", lw=1.6, zorder=1)
    for offset, row in enumerate(trade.itertuples()):
        panel[5].scatter([row.cost], [row.f1], s=44, zorder=2,
                         color=CYCLE[offset % len(CYCLE)])
        panel[5].annotate(row.model, (row.cost, row.f1), textcoords="offset points",
                          xytext=(0, 8), fontsize=6, ha="center")
    panel[5].set_xscale("log")
    panel[5].set_xlabel("cost of 24 papers (USD)")
    panel[5].set_ylabel("F1")
    panel[5].margins(x=0.3, y=0.28)
    note(panel[5], "free endpoint at $0.01", x=0.97, y=0.06, ha="right")

    save(figure, "fig4_choices")

    gaps = {name: frame["f1"].max() - frame["f1"].loc[CHOSEN[name]]
            for name, frame in sweeps.items()}
    delta = arms["mean"].get("citing sources", 0) - arms["mean"].get("not citing", 0)
    print("\n" + caption(
        CAPTION,
        accept_gap=f"{gaps['accept']:.3f}", catalyst_gap=f"{gaps['catalyst']:.3f}",
        tolerance_gap=f"{gaps['tolerance']:.3f}",
        delta=f"{delta:.3f}", p=f"{arms.attrs.get('p', float('nan')):.3f}"))


if __name__ == "__main__":
    main()
