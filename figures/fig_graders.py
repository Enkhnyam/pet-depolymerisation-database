"""How good the extraction is, and which grader the chemists back.

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

  (c) On the records where the two graders do disagree, which of them the chemists sided with.
      This is the comparison the section exists for, and it is the one place the two graders can
      be separated: where they agree, the record says nothing about which is better.
"""
from _style import (BAR, CYCLE, DIM, GRADER, RAMP, bracket, canvas, grouped_bars, headroom,
                    pie, save, sci)
from curated import extractions as extractions_check
from curated import matrix as matrix_check
from human import adjudicated as adjudicated_check

# Each measure abbreviated to what fits on a bar label, glossed in the caption.
SHORT = {"precision": "P", "recall": "R", "f1": "$F_1$"}

# The shipped pair: luna extracts, gpt-oss judges. Named here because (b) is about that one
# cell of the matrix and not about the matrix.
SHIPPED = ("oss", "luna")


def main() -> None:
    scores = extractions_check.compute()
    cell = matrix_check.compute().query(
        "judge == @SHIPPED[0] and extraction == @SHIPPED[1]").iloc[0]
    audit = adjudicated_check.compute(adjudicated_check.REAL)
    mcnemar = audit["mcnemar"]

    figure, panel = canvas(1, 3, height=2.36)

    # --- a: the heuristic grader on each extractor, with the spread over repeats -------------
    measures = ["precision", "recall", "f1"]
    models = scores[measures].T
    spread = scores[[f"{m} sd" for m in measures]].T
    spread.index = measures
    grouped_bars(panel[0], models, errors=spread, names=SHORT,
                 palette=dict(zip(models.columns, CYCLE)),
                 ylabel="heuristic grader vs the curated answer key")
    panel[0].set_ylim(0, 1.05)
    panel[0].annotate(f"mean of {int(scores['runs'].min())} runs, bars are 1 s.d.",
                      (0.97, 0.97), xycoords="axes fraction", ha="right", va="top",
                      fontsize=5.2, color=DIM)

    # --- b: judge against heuristic, on the pair the database ships --------------------------
    split = {"same verdict": int(cell["agree"]),
             "different verdict": int(cell["disagree"]),
             "no counterpart": int(cell["no counterpart"])}
    pie(panel[1], __import__("pandas").Series(split),
        colours=[GRADER["metric"], GRADER["judge"], RAMP[3]], gap=0.42)
    panel[1].set_xlabel(f"{int(cell['records'])} records judged by "
                        f"{SHIPPED[0]} on the {SHIPPED[1]} extraction")

    # --- c: on the disagreements, who the chemists backed ------------------------------------
    backed = [("the heuristic", mcnemar["favouring the metric"], GRADER["metric"]),
              ("the judge", mcnemar["favouring the judge"], GRADER["judge"])]
    tallest = max(value for _, value, _ in backed)
    panel[2].bar(range(2), [value for _, value, _ in backed], width=BAR,
                 color=[colour for *_, colour in backed])
    panel[2].set_xticks(range(2), [name for name, *_ in backed])
    panel[2].tick_params(axis="x", length=0)
    panel[2].set_xlabel("the chemists sided with")
    panel[2].set_ylabel(f"number of disagreements "
                        f"(of {mcnemar['informative pairs']})")
    headroom(panel[2], tallest * 1.3)
    panel[2].set_xlim(-0.6, 1.6)
    for position, (_, value, _) in enumerate(backed):
        panel[2].annotate(f"{value}", (position, value), textcoords="offset points",
                          xytext=(0, 3), ha="center", fontsize=6.5, color=DIM)
    bracket(panel[2], 0, 1, tallest * 1.18, f"McNemar $p = {sci(mcnemar['p'])}$")

    save(figure, "fig_graders")


if __name__ == "__main__":
    main()
