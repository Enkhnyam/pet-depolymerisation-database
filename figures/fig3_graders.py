"""Figure 3 -- how good the extraction is, and how well the judge can tell.

The database rests on one assumption: that a judge's verdicts can stand in for a measurement
nobody can afford to make. These panels test that assumption where a measurement does exist, and
show what it would take to settle the part that is still open.
"""
import pandas as pd

from _style import CYCLE, GRADER, bars, canvas, caption, grouped_bars, note, save
from curated import extractions as extractions_check
from curated import judged_runs as judged_check
from human import labelled as labelled_check
from human import worklist as worklist_check

CAPTION = r"""\textbf{How good the extraction is, and how well the judge can tell.}
(a) The three extraction models against the curated answer key. Terra scores highest but costs
roughly ten times what luna does per paper, which is why the database was built with luna.
(b) Each judge's pass rate against the $F_1$ actually measured for the same run. \textbf{The
assumption the database rests on is that these track each other}, and across the three
extractions they do --- but with three points per judge this is direction, not a slope anyone
should quote.
(c) The same judges' precision: of the records a judge accepted, the share the curated table also
accepts. \textbf{The judge we ship is the most lenient and the least precise} --- it accepts
95\% of luna's records at 0.67 precision, where luna as judge accepts 81\% at 0.73. A lenient
judge inflates a pass rate, which is the main risk in reading __ACCEPTED__\% as a quality figure.
(d) Both graders against the two chemists on the 48 adjudicated records. The judge is ahead on
every column; the set is too small to establish that, which (e) explains.
(e) Why: the set was drawn on grader disagreements, but the judge rubric was rewritten afterwards
and the judge changed its verdict on 20 of the 48, \textbf{19 of them toward the metric}. Only
four disagreements survive, and four cannot reach significance however they fall.
(f) What a second round has to draw from: __TOTAL__ disagreements under the shipped pair, of which
only __STRONG__ are about chemistry rather than about the answer key having no row. Thirty pairs
are needed, so a conclusive round must either use the weaker cases or curate more papers."""


def main() -> None:
    scores = extractions_check.compute()          # already indexed by model
    judge_runs = judged_check.compute()
    disputed = worklist_check.compute()

    figure, panel = canvas(2, 3, width=8.6, height=5.0)

    grouped_bars(panel[0], scores[["precision", "recall", "f1"]], ylabel="score")

    for offset, (name, group) in enumerate(judge_runs.groupby("judge")):
        panel[1].scatter(group["measured f1"], group["judge pass rate"], s=26,
                         label=name, alpha=0.85, color=CYCLE[offset % len(CYCLE)])
    panel[1].set_xlabel("measured F1")
    panel[1].set_ylabel("judge pass rate")
    panel[1].legend(frameon=False, fontsize=6, loc="upper left")

    pivot = judge_runs.pivot(index="judge", columns="extraction", values="precision")
    grouped_bars(panel[2], pivot, ylabel="precision of what it accepted")

    labelled = labelled_check.scorecard()
    grouped_bars(panel[3], labelled[["agreement", "precision", "recall"]], ylabel="score")

    drift = labelled_check.drift()
    bars(panel[4], pd.Series({"at selection": drift["disagreements when the set was drawn"],
                              "now": drift["disagreements now"]}),
         colour=[GRADER["judge"], GRADER["metric"]], ylabel="disagreements in the 48")

    pool = pd.Series({"chemistry": int(disputed.informative.sum()),
                      "no answer-key row": int((~disputed.informative).sum())})
    bars(panel[5], pool, colour=[GRADER["metric"], "#C9D6D3"], ylabel="records")
    panel[5].axhline(30, color="#A33A2E", lw=1, ls="--")
    note(panel[5], "30 needed", x=0.97, y=0.62, ha="right")

    save(figure, "fig3_graders")
    print("\n" + caption(CAPTION, accepted="72",
                         total=len(disputed), strong=int(disputed.informative.sum())))


if __name__ == "__main__":
    main()
