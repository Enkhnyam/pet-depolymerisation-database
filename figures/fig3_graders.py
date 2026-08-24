"""Figure 3 -- how good the extraction is, and whether the judge can tell.

Three panels, because three questions is what the evidence supports. Grouped bars were the wrong
form for two of them: a bar chart of precision hides the trade-off that makes the number
interesting, and a bar chart of one grader beside another hides which way each moved.
"""
import pandas as pd

from _style import CYCLE, DIM, GRADER, canvas, caption, grouped_bars, save
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

    # Each panel keys a different thing, so one shared legend cannot serve the canvas. Instead
    # every key sits in space its own panel leaves empty: here the y-axis is opened to 1.0, well
    # above the tallest bar, so the key has a band to itself instead of standing on luna's bars.
    grouped_bars(panel[0], scores[["precision", "recall", "f1"]], ylabel="score")
    panel[0].set_ylim(0, 1.02)
    panel[0].legend(frameon=False, fontsize=6, loc="upper center", ncol=3,
                    columnspacing=1.0, handletextpad=0.4, borderpad=0.1)

    # leniency against correctness: a judge is only useful in the upper right, and a bar chart of
    # either number alone hides that they trade off
    # Nine points, and colour alone left the reader unable to say which extraction each graded.
    # Colour is the judge; the letter printed beside each point is the extraction it graded, so
    # both variables are readable without a second legend competing with the first.
    for offset, (name, group) in enumerate(judge_runs.groupby("judge")):
        panel[1].scatter(group["judge pass rate"], group["precision"], s=34,
                         color=CYCLE[offset % len(CYCLE)], label=f"judge: {name}", alpha=0.9,
                         zorder=3)
        for _, row in group.iterrows():
            panel[1].annotate(str(row["extraction"])[0],
                              (row["judge pass rate"], row["precision"]),
                              textcoords="offset points", xytext=(5, -1), fontsize=5.5,
                              color=DIM, va="center")
    shipped = judge_runs.query("judge == 'oss' and extraction == 'luna'").iloc[0]
    panel[1].scatter([shipped["judge pass rate"]], [shipped["precision"]], s=120,
                     facecolors="none", edgecolors="#A33A2E", linewidths=1.3, zorder=4)
    panel[1].annotate("the pair the\ndatabase uses",
                      (shipped["judge pass rate"], shipped["precision"]),
                      textcoords="offset points", xytext=(-11, 2), fontsize=5.5,
                      color="#A33A2E", ha="right", va="center", linespacing=1.3)
    panel[1].margins(x=0.20, y=0.22)
    panel[1].set_xlabel("share of records the judge accepts")
    panel[1].set_ylabel("precision of what it accepted")
    panel[1].legend(frameon=False, fontsize=6, loc="lower left", borderpad=0.1)

    # A horizontal dumbbell, one row per measure. Vertically the three measures were squeezed
    # into a shared 0.55--1.0 axis and the connecting segments read as though they joined
    # different measures to each other; laid out in rows, each segment is unmistakably the gap
    # between the two graders on one measure, and its length is that gap.
    measures = ["agreement", "precision", "recall"]
    for position, measure in enumerate(measures[::-1]):
        judge, metric = labelled.loc["judge", measure], labelled.loc["metric", measure]
        panel[2].plot([metric, judge], [position, position], color="#C9D6D3", lw=2.4, zorder=1,
                      solid_capstyle="round")
        # judge is a ring, not a disc: the two graders tie exactly on recall, and two filled
        # markers at one coordinate render as a single dot of whichever was drawn last. A ring
        # around a disc reads unambiguously as both being here.
        panel[2].scatter([metric], [position], s=42, color=GRADER["metric"], zorder=2,
                         label="metric" if position == 0 else None)
        panel[2].scatter([judge], [position], s=96, facecolors="none",
                         edgecolors=GRADER["judge"], linewidths=1.5, zorder=3,
                         label="judge" if position == 0 else None)
        difference = judge - metric
        panel[2].annotate("level" if abs(difference) <= 0.005 else f"{difference:+.02f}",
                          (max(metric, judge), position), textcoords="offset points",
                          xytext=(10, 0), fontsize=5.5, color=DIM, va="center")
    panel[2].set_yticks(range(len(measures)), measures[::-1], fontsize=6)
    panel[2].set_ylim(-0.6, len(measures) - 0.4)
    panel[2].set_xlim(0.55, 1.06)
    panel[2].set_xlabel("agreement with the chemists")
    panel[2].legend(frameon=False, fontsize=6, loc="lower left", borderpad=0.1)

    save(figure, "fig3_graders")

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
