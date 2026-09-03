"""Figure 3 -- how good the extraction is, and which grader the chemists back.

Three panels, one idiom. An earlier version answered each question in whatever form suited it
alone -- bars, then a scatter, then a dumbbell -- and the reader had to learn three charts to
follow one argument. All three are grouped bars now: same geometry, same measure colours, so the
comparison a reader makes in the first panel is the comparison they make in the third.
"""
from _style import BAR, NEUTRAL, canvas, grouped_bars, note, save, sci
from curated import extractions as extractions_check
from human import adjudicated as adjudicated_check



def main() -> None:
    scores = extractions_check.compute()
    audit = adjudicated_check.compute(adjudicated_check.REAL)
    table, mcnemar = audit["table"], audit["mcnemar"]

    ranked = scores.sort_values("f1", ascending=False)

    figure, panel = canvas(1, 3, height=2.36)

    grouped_bars(panel[0], scores[["precision", "recall", "f1"]], ylabel="score")
    panel[0].set_ylim(0, 1.02)
    panel[0].legend(frameon=False, fontsize=6, loc="upper center", ncol=3,
                    columnspacing=1.0, handletextpad=0.4, borderpad=0.1)

    # the same geometry and the same measure colours as (a), so the two read as one comparison
    against = table[["precision", "recall", "F1", "kappa"]].rename(columns=str.lower)
    grouped_bars(panel[1], against, ylabel="against the chemists")
    panel[1].set_ylim(0, 1.15)
    panel[1].legend(frameon=False, fontsize=6, loc="upper center", ncol=4,
                    columnspacing=0.8, handletextpad=0.3, borderpad=0.1)

    # NEUTRAL, not the grader colours: on this canvas teal already means precision, and a bar
    # that meant "metric" in one panel and "precision" in the next would make the page unreadable.
    # The axis labels carry which grader is which, so colour has nothing left to say here.
    split = {"judge": mcnemar["favouring the judge"], "metric": mcnemar["favouring the metric"]}
    panel[2].bar(range(2), [split["metric"], split["judge"]], width=BAR, color=NEUTRAL)
    panel[2].set_xticks(range(2), ["metric was right", "judge was right"])
    panel[2].set_ylabel("informative pairs")
    panel[2].set_ylim(0, max(split.values()) * 1.35)
    panel[2].set_xlim(-0.7, 1.7)
    for position, value in enumerate([split["metric"], split["judge"]]):
        panel[2].annotate(f"{value}", (position, value), textcoords="offset points",
                          xytext=(0, 3), ha="center", fontsize=6.5, color=NEUTRAL)
    note(panel[2], f"McNemar p = {mcnemar['p']:.1e}  ({mcnemar['informative pairs']} pairs)",
         x=0.5, y=0.93, ha="center", colour=NEUTRAL)

    save(figure, "fig3_graders")

    records = int(audit["records"].shape[0])
    # the reviewed count, not the drawn one: two censused records moved into this stratum
    reviewed = int((audit["records"].stratum == "both accepted it").sum())


if __name__ == "__main__":
    main()
