"""Figure 4 -- the settings we chose, and what each one is worth.

Every panel is a decision that could have gone another way, with the evidence for it and, where
there is none, an honest flat line.
"""
import pandas as pd

from _style import CYCLE, GRADER, canvas, caption, grouped_bars, note, save
from curated import extractions as extractions_check
from curated import shots as shots_check
from curated import source_tracking as source_check
from curated import thresholds as thresholds_check
import cost as cost_check

CAPTION = r"""\textbf{Four settings, and what each is worth.}
(a) The metric grader's three thresholds, swept one at a time. All three sit on plateaus rather
than peaks, which is the evidence that they were not tuned until the number looked good; the
catalyst gate is the only one with a real optimum, and it is broad.
(b) Worked examples in the prompt. \textbf{Having one beats having none} ($+0.043$, $p=0.005$);
beyond one nothing separates the settings (one-way ANOVA $p=0.55$). The database was built with
four, which on this evidence buys nothing and costs roughly 40\,k tokens per paper.
(c) Requiring each record to cite its source chunks. \textbf{$+__DELTA__$ in $F_1$, $p=__P__$} ---
short of significance at three runs each, and reported as such, but the direction is consistent.
Source tracking was adopted for provenance; it appears to pay for itself twice.
(d) What each extraction model costs against what it scores. \textbf{Terra is the best extractor
and roughly ten times the price}; luna sits at the knee, which is why the database was built with
it. The judge is not on this axis because the one we ship runs on an unmetered endpoint --- its
cost is wall time, not money."""


def main() -> None:
    figure, panel = canvas(2, 2, width=7.2, height=5.4)

    sweeps = thresholds_check.compute()
    for offset, (name, frame) in enumerate(sweeps.items()):
        panel[0].plot(frame.index, frame["f1"], marker="o", ms=3, lw=1.2,
                      label=name, color=CYCLE[offset % len(CYCLE)])
    panel[0].set_xlabel("threshold value")
    panel[0].set_ylabel("F1")
    panel[0].legend(frameon=False, fontsize=6)

    raw = shots_check.compute()
    if raw is not None:
        shots = raw.groupby("n_shots").f1.agg(["mean", "std"])
        panel[1].errorbar(shots.index, shots["mean"], yerr=shots["std"], marker="o",
                          ms=3.5, lw=1.2, capsize=2.5, color=GRADER["metric"])
    panel[1].set_xlabel("worked examples in the prompt")
    panel[1].set_ylabel("F1")

    arms = source_check.compute()
    panel[2].bar(range(len(arms)), arms["mean"], yerr=arms["std"], capsize=4, width=0.55,
                 color=[GRADER["metric"], "#C9D6D3"])
    panel[2].set_xticks(range(len(arms)), list(arms.index))
    panel[2].set_ylabel("F1")
    panel[2].set_ylim(0.60, 0.75)

    scores = extractions_check.compute()
    ledger = cost_check.compute().set_index("run")
    for offset, model in enumerate(scores.index):
        match = [r for r in ledger.index if f"extract_{model}/" in r]
        if not match:
            continue
        spend = ledger.loc[match[0], "cost_usd"]
        panel[3].scatter(max(spend, 0.01), scores.loc[model, "f1"], s=40,
                         color=CYCLE[offset % len(CYCLE)], label=model)
        panel[3].annotate(model, (max(spend, 0.01), scores.loc[model, "f1"]),
                          textcoords="offset points", xytext=(6, -2), fontsize=6)
    panel[3].set_xscale("log")
    panel[3].margins(x=0.28, y=0.18)          # room for the labels beside each point
    panel[3].set_xlabel("cost of 24 papers (USD, log)")
    panel[3].set_ylabel("F1")
    note(panel[3], "free endpoint plotted at $0.01", x=0.97, y=0.06, ha="right")

    save(figure, "fig4_choices")
    delta = arms["mean"].get("citing sources", 0) - arms["mean"].get("not citing", 0)
    print("\n" + caption(CAPTION, delta=f"{delta:.3f}", p=f"{arms.attrs.get('p', float('nan')):.3f}"))


if __name__ == "__main__":
    main()
