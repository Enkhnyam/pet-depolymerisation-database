"""Figure 3 -- how good the extraction is, and whether the judge can tell.

Three panels, because three questions is what the evidence supports. Grouped bars were the wrong
form for two of them: a bar chart of precision hides the trade-off that makes the number
interesting, and a bar chart of one grader beside another hides which way each moved.
"""
import pandas as pd

from _style import CYCLE, GRADER, canvas, caption, grouped_bars, note, save
from curated import extractions as extractions_check
from curated import judged_runs as judged_check
from human import labelled as labelled_check

CAPTION = r"""\textbf{How good the extraction is, and whether the judge can tell.}
Terra is the strongest extractor on the curated papers and luna the second (\textbf{a}), but
terra costs roughly ten times as much per paper, which is why the database was built with luna ---
a choice Figure~\ref{fig:choices} makes explicit.

Whether a judge's verdicts can stand in for that measurement is the assumption everything else
rests on, and \textbf{b} is the shape of it. A judge is useful only in the upper right: accepting
few enough records to be discriminating, and being right about the ones it accepts. \textbf{The
judge the database uses is the most lenient of the three} --- gpt-oss accepts __OSS_RATE__\% of
luna's records at __OSS_PRECISION__ precision, where luna as judge accepts __LUNA_RATE__\% at
__LUNA_PRECISION__. Leniency inflates a pass rate, so the __ACCEPTED__\% headline figure for the
database should be read as an upper bound rather than an estimate.

Against the two chemists who adjudicated 48 records (\textbf{c}), the judge is ahead of the metric
on agreement and on the precision of what it flags, and the two are level on recall. The gaps are
small and the set is far too small to establish them: only four of the 48 records separate the
graders at all, for reasons Section~\ref{sec:evidence} explains. The panel is here to show the
direction and the size of what a larger round would be testing, not to settle it."""


def main() -> None:
    scores = extractions_check.compute()
    judge_runs = judged_check.compute()
    labelled = labelled_check.scorecard()

    figure, panel = canvas(1, 3, width=9.0, height=3.1)

    grouped_bars(panel[0], scores[["precision", "recall", "f1"]], ylabel="score")

    # leniency against correctness: a judge is only useful in the upper right, and a bar chart of
    # either number alone hides that they trade off
    for offset, (name, group) in enumerate(judge_runs.groupby("judge")):
        panel[1].scatter(group["judge pass rate"], group["precision"], s=34,
                         color=CYCLE[offset % len(CYCLE)], label=name, alpha=0.9)
    shipped = judge_runs.query("judge == 'oss' and extraction == 'luna'").iloc[0]
    panel[1].scatter([shipped["judge pass rate"]], [shipped["precision"]], s=110,
                     facecolors="none", edgecolors="#A33A2E", linewidths=1.4, zorder=4)
    panel[1].annotate("shipped", (shipped["judge pass rate"], shipped["precision"]),
                      textcoords="offset points", xytext=(-10, 8), fontsize=6, color="#A33A2E",
                      ha="right")
    panel[1].margins(x=0.14, y=0.16)
    panel[1].set_xlabel("share of records the judge accepts")
    panel[1].set_ylabel("precision of what it accepted")
    panel[1].legend(frameon=False, fontsize=6, loc="lower left")

    # paired, not grouped: the question is which grader is higher on each measure and by how much
    # a small horizontal offset, because the two graders tie exactly on recall and one marker
    # would otherwise sit invisibly underneath the other
    measures = ["agreement", "precision", "recall"]
    gap = 0.07
    for position, measure in enumerate(measures):
        judge, metric = labelled.loc["judge", measure], labelled.loc["metric", measure]
        panel[2].plot([position - gap, position + gap], [metric, judge],
                      color="#C9D6D3", lw=2, zorder=1)
        panel[2].scatter([position - gap], [metric], s=42, color=GRADER["metric"], zorder=2,
                         label="metric" if position == 0 else None)
        panel[2].scatter([position + gap], [judge], s=42, color=GRADER["judge"], zorder=2,
                         label="judge" if position == 0 else None)
    panel[2].set_xticks(range(len(measures)), measures)
    panel[2].set_ylabel("against the chemists")
    panel[2].set_ylim(0.55, 1.0)
    panel[2].legend(frameon=False, fontsize=6, loc="lower left")

    save(figure, "fig3_graders", legend_room=False)

    luna = judge_runs.query("judge == 'luna' and extraction == 'luna'").iloc[0]
    print("\n" + caption(
        CAPTION,
        oss_rate=f"{100 * shipped['judge pass rate']:.0f}",
        oss_precision=f"{shipped['precision']:.2f}",
        luna_rate=f"{100 * luna['judge pass rate']:.0f}",
        luna_precision=f"{luna['precision']:.2f}",
        accepted="72"))


if __name__ == "__main__":
    main()
