"""Figure 3 -- how far we can vouch for the database.

The methods argument, and the one a purely extractive pipeline cannot make: a judge read every
record. Grader is the colour here, not route.

Numbers come from the checks that print them; nothing is recomputed.
"""
import pandas as pd

from _style import DIM, GRADER, VERDICT, bars, canvas, heatmap, note, save
from curated import extractions as extractions_check
from curated import matrix as matrix_check
from curated import thresholds as thresholds_check
from database import verdicts as verdicts_check

AGREEMENT = (0.6, 1.0)


def main() -> None:
    matrix = matrix_check.compute()
    scores = extractions_check.compute()
    sweeps = thresholds_check.compute()
    judged = verdicts_check.compute()

    figure, panel = canvas(2, 4, width=9.2, height=4.6)

    image = heatmap(panel[0], matrix.pivot(index="judge", columns="extraction", values="agreement"),
                    vmin=AGREEMENT[0], vmax=AGREEMENT[1], xlabel="extraction", ylabel="judge",
                    title="every record")
    heatmap(panel[1], matrix.pivot(index="judge", columns="extraction",
                                   values="agreement, evaluable"),
            vmin=AGREEMENT[0], vmax=AGREEMENT[1], xlabel="extraction",
            title="records the metric could evaluate")
    figure.colorbar(image, ax=panel[1], fraction=0.04, pad=0.03, label="agreement")

    width = 0.26
    for offset, (column, colour) in enumerate(
            [("precision", "#0E7C6B"), ("recall", "#C4527A"), ("f1", "#9A6510")]):
        panel[2].bar([i + (offset - 1) * width for i in range(len(scores))], scores[column],
                     width=width, color=colour, label=column)
    panel[2].set_xticks(range(len(scores)), scores.index)
    panel[2].set_ylabel("score")
    panel[2].set_ylim(0, 1)
    panel[2].legend(fontsize=5.8, ncol=3, handlelength=1, columnspacing=0.8)
    panel[2].set_title(f"{panel[2].get_title(loc='left')}   on the 24 curated papers",
                       loc="left", fontsize=7.5)

    # the three knobs have different ranges, so the shared x-axis shows shape, not comparability
    for (name, frame), colour in zip(sweeps.items(), ("#0E7C6B", "#C4527A", "#9A6510")):
        panel[3].plot(frame.index, frame.f1, marker="o", ms=2.5, lw=1.1, color=colour, label=name)
    panel[3].set_xlabel("threshold value")
    panel[3].set_ylabel("F1")
    panel[3].legend(fontsize=5.8, handlelength=1.2)
    panel[3].set_title(f"{panel[3].get_title(loc='left')}   a plateau, not a peak",
                       loc="left", fontsize=7.5)

    counts = judged["counts"]
    verdict = pd.Series({"accepted": counts["accepted"],
                         "corrected": counts["rejected, with a correction"],
                         "dropped": counts["rejected outright"]})
    panel[4].bar(range(len(verdict)), verdict.values, width=0.7,
                 color=[VERDICT[name] for name in verdict.index])
    panel[4].set_xticks(range(len(verdict)), verdict.index)
    panel[4].set_ylabel("records")
    panel[4].set_title(f"{panel[4].get_title(loc='left')}   "
                       f"{judged['pass rate']:.1%} accepted", loc="left", fontsize=7.5)

    bars(panel[5], judged["fields"].head(9), colour="#9A6510", horizontal=True,
         xlabel="records the judge would change", title="masses dominate")

    agreement = matrix.set_index(["judge", "extraction"])
    shipped = agreement.loc[("oss", "luna")]
    panel[6].scatter(agreement["agreement"], agreement["agreement, evaluable"],
                     s=26, color=DIM, alpha=0.7, linewidths=0)
    panel[6].scatter([shipped["agreement"]], [shipped["agreement, evaluable"]],
                     s=44, color="#C4527A", linewidths=0, label="oss judging luna")
    panel[6].set_xlabel("agreement, every record")
    panel[6].set_ylabel("agreement, evaluable")
    panel[6].legend(fontsize=5.8, markerscale=0.8)
    note(panel[6], "the reference running out, not disagreement", colour=DIM, y=0.06)

    panel[7].axis("off")
    note(panel[7], "reserved for the shots ablation", colour=DIM, y=0.5)

    save(figure, "fig3_quality")


if __name__ == "__main__":
    main()
