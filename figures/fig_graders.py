"""How good the extraction is, and which grader manual evaluation backs.

Three panels, no legend on any of them: the x ticks carry the measures, which are the same words
in both scored panels, and colour carries the thing being compared -- three extraction models in
(a), the two graders in (b) and (c).

What each panel answers, and why it is the panel it is:

  (a) The heuristic grader's score for each candidate extractor, against the hand-curated
      answer key. Error bars are the spread over three repeats at the setting the database
      ships, and they are the point rather than decoration: luna leads terra by 0.024 in F1
      while its own three runs span 0.018 and oss's span 0.034. The ordering of the top two is
      not resolved by three runs and the panel now says so instead of asserting a ranking.

  (b) How often the judge and the heuristic reach the same verdict, on the pair the database is
      built with. Three slices rather than two, because the flat 0.81 hides what the
      disagreement is made of: on 39 of 285 records the heuristic has no counterpart in the
      answer key and therefore no opinion, and counting those as disagreements blames it for
      records it could not grade.

  (c) On the records where the two graders do disagree, which of them manual evaluation
      sided with. "Human evaluation" rather than "the chemists" on the panel itself, which
      is the wording the manuscript's own caption already used.
      This is the comparison the section exists for, and it is the one place the two graders can
      be separated: where they agree, the record says nothing about which is better.
"""
from matplotlib.patches import Patch

from _style import (BAR, CATEGORICAL, CYCLE, DIM, GRADER, INK, RAMP, canvas, grouped_bars,
                    headroom, pie, save, shares)
from curated import extractions as extractions_check
from curated import matrix as matrix_check
from human import adjudicated as adjudicated_check
from human import corrections as corrections_check

# Each measure abbreviated to what fits on a bar label, glossed in the caption.
SHORT = {"precision": "P", "recall": "R", "f1": "$F_1$"}

# The shipped pair: luna extracts, gpt-oss judges. Named here because (b) is about that one
# cell of the matrix and not about the matrix.
SHIPPED = ("oss", "luna")

# (d)'s three outcomes. Dark blue where the judge earned its keep, the pale ramp step where it
# changed nothing, red where its value was refused. The pale step rather than the tick ink: grey
# against red separates at dE 7.8 under deuteranopia, below the palette's own floor of 8, and
# these two segments touch. The pale fill is too light to carry 5.6 pt text, so that one name is
# set in ink and its position does the binding.
VERDICT = {corrections_check.CAUGHT: CATEGORICAL["blue"],
           corrections_check.BOTH: RAMP[3],
           corrections_check.REJECTED: CATEGORICAL["red"]}
# A count sits on its own fill, so its colour follows the fill and nothing else: white on the two
# dark ones, ink on the pale one. A count with no room inside goes above the bar in the tick ink,
# like every other out-of-bar number in these figures.
ON = {corrections_check.CAUGHT: "white", corrections_check.BOTH: INK,
      corrections_check.REJECTED: "white"}
THICKEST, THINNEST = 0.66, 0.14      # bar thickness is the sample size, floored so 6 cards show

# Each verdict abbreviated to what fits on one legend line, the way (a) abbreviates its measures.
# The check's own names are sentences -- "Extraction and judge both correct" -- which is right for
# the table it prints and three times too wide for a key under a quarter-width panel. Stacked on
# three lines they were the most cluttered thing in the figure; the caption glosses them in full.
SHORT_VERDICT = {corrections_check.CAUGHT: "correction right",
                 corrections_check.BOTH: "both right",
                 corrections_check.REJECTED: "correction rejected"}


def main() -> None:
    scores = extractions_check.compute()
    cell = matrix_check.compute().query(
        "judge == @SHIPPED[0] and extraction == @SHIPPED[1]").iloc[0]
    audit = adjudicated_check.compute(adjudicated_check.REAL)
    mcnemar = audit["mcnemar"]

    corrections = corrections_check.compute()

    # Two rows rather than one. (d) carries four named rows and three named outcomes, none
    # of which fit in a quarter of the text width, and (a)'s nine slanted labels were
    # already crowded at a third of it.
    figure, panel = canvas(2, 2, height=4.3)

    # --- a: the heuristic grader on each extractor, with the spread over repeats -------------
    measures = ["precision", "recall", "f1"]
    models = scores[measures].T
    spread = scores[[f"{m} sd" for m in measures]].T
    spread.index = measures
    grouped_bars(panel[0], models, errors=spread, names=SHORT,
                 palette=dict(zip(models.columns, CYCLE)),
                 ylabel="score vs answer key")
    panel[0].set_ylim(0, 1.05)

    # --- b: judge against heuristic, on the pair the database ships --------------------------
    # Named in full rather than same/differ/n-a. The third slice is the one that needed the
    # room: "n/a" says nothing, and what it means -- the heuristic had no answer-key counterpart
    # to grade against, so it holds no opinion rather than a wrong one -- is the reason the
    # slice is drawn at all.
    split = {"agree": int(cell["agree"]), "disagree": int(cell["disagree"]),
             "not gradeable": int(cell["no counterpart"])}
    # One decimal, because no integer rounding of 230/16/39 sums to a hundred: 80.70, 5.61 and
    # 13.68 all round up and the legend read 101%. The route pie in fig_database stays on
    # integers, where the manuscript quotes them.
    pie(panel[1], __import__("pandas").Series(split),
        colours=[GRADER["metric"], GRADER["judge"], RAMP[3]], decimals=1, key="below", ncol=3)

    # --- c: on the disagreements, who human evaluation backed ------------------------------------
    backed = [("the heuristic", mcnemar["favouring the metric"], GRADER["metric"]),
              ("the judge", mcnemar["favouring the judge"], GRADER["judge"])]
    tallest = max(value for _, value, _ in backed)
    panel[2].bar(range(2), [value for _, value, _ in backed], width=BAR,
                 color=[colour for *_, colour in backed])
    panel[2].set_xticks(range(2), [name for name, *_ in backed])
    panel[2].tick_params(axis="x", length=0)
    panel[2].set_xlabel("human evaluation sided with")
    panel[2].set_ylabel(f"number of disagreements "
                        f"(of {mcnemar['informative pairs']})")
    headroom(panel[2], tallest * 1.3)
    panel[2].set_xlim(-0.6, 1.6)
    for position, (_, value, _) in enumerate(backed):
        panel[2].annotate(f"{value}", (position, value), textcoords="offset points",
                          xytext=(0, 3), ha="center", fontsize=6.5, color=DIM)

    # --- d: and what the judge's corrections are worth, by what each one asks for -------------
    # (a)-(c) ask whether the judge's verdict can be trusted. This asks what its proposals are
    # worth once a chemist rules on them, which is the question that decides whether they can be
    # applied -- and the answer is not one number. Every bar spans the full width so the rates
    # compare across kinds; thickness is how many of that kind were ruled on, so the six number
    # replacements are a strip nobody can read a rate off rather than a row with equal say.
    #
    # The colour key is a legend under the axes rather than three names written among the bars.
    # Those names were set in three different colours in three different places and read as
    # scattered text; this is the same swatch-name-count-share list (b) already uses, in the same
    # place, so the two keyed panels of this figure are keyed the same way.
    axis = panel[3]
    meta = corrections.attrs
    rows = len(corrections)
    deepest = corrections["cases"].max()

    for position, (kind, row) in enumerate(corrections.iterrows()):
        y = rows - 1 - position
        height = max(THICKEST * row["cases"] / deepest, THINNEST)
        left = 0.0
        for outcome in corrections_check.OUTCOMES:
            share = 100 * row[outcome] / row["cases"]
            if not share:
                continue
            axis.barh(y, share, left=left, height=height, color=VERDICT[outcome],
                      edgecolor="white", linewidth=0.6, zorder=2)
            middle, count = left + share / 2, int(row[outcome])
            # The narrowest segment here is one rename in twenty-two, which is the panel's whole
            # point and must never be the number that would not fit.
            if share >= 13 and height >= 0.30:
                axis.text(middle, y, f"{count}", ha="center", va="center", fontsize=6,
                          color=ON[outcome], zorder=5)
            else:
                axis.annotate(f"{count}", (middle, y + height / 2), xytext=(0, 1.5),
                              textcoords="offset points", ha="center", va="bottom",
                              fontsize=5.4, color=DIM, zorder=5)
            left += share
        # How deep that kind was sampled, in a column past the bars. Every bar ends at 100%, so
        # the column aligns itself and reads as a table rather than as four loose notes.
        axis.annotate(f"{int(row['cases'])}", (104, y), xycoords=("data", "data"), ha="left",
                      va="center", fontsize=5.6, color=DIM)

    axis.set_yticks(range(rows), [corrections_check.KINDS[k] for k in corrections.index][::-1],
                    fontsize=6)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 100)
    axis.set_xticks([0, 50, 100], ["0", "50", "100%"])
    axis.set_ylim(-0.75, rows - 0.15)
    # The count column needs naming once; without it the four figures past the bars are loose.
    axis.annotate("ruled on", (104, rows - 1 + 0.46), xycoords=("data", "data"), ha="left",
                  va="bottom", fontsize=5.4, color=DIM)
    axis.set_xlabel("% of the corrections of that kind")

    totals = [int(corrections[outcome].sum()) for outcome in corrections_check.OUTCOMES]
    axis.legend([Patch(facecolor=VERDICT[o], edgecolor="white", linewidth=0.6)
                 for o in corrections_check.OUTCOMES],
                [f"{SHORT_VERDICT[o]}  {n:,} ({share:.0f}%)"
                 for o, n, share in zip(corrections_check.OUTCOMES, totals, shares(totals))],
                loc="upper center", bbox_to_anchor=(0.5, -0.26), frameon=False,
                fontsize=5.4, labelcolor=INK, handlelength=0.85, handleheight=0.85, handletextpad=0.5,
                labelspacing=0.42, borderpad=0.0, borderaxespad=0.0, ncol=3, columnspacing=1.0)

    save(figure, "fig_graders")


if __name__ == "__main__":
    main()
