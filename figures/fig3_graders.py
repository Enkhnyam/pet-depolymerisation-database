"""Figure 3 -- how good the extraction is, and which grader the chemists back.

Three panels, one idiom. An earlier version answered each question in whatever form suited it
alone -- bars, then a scatter, then a dumbbell -- and the reader had to learn three charts to
follow one argument. All three are grouped bars now: same geometry, same measure colours, so the
comparison a reader makes in the first panel is the comparison they make in the third.
"""
from _style import BAR, NEUTRAL, canvas, caption, grouped_bars, note, save, sci
from curated import extractions as extractions_check
from human import adjudicated as adjudicated_check

CAPTION = r"""\textbf{Extraction quality, and the two graders against the chemists.}
__BEST_MODEL__ scores highest of the three extractors on the curated papers (\textbf{a}, $F_1 =
__BEST_F1__ \pm __BEST_SD__$) against __SECOND_MODEL__ at __SECOND_F1__, a gap of the same size as
the spread between repeats of one model, so the ordering is not resolved by these data. All three are scored at
__BENCH_SHOTS__ worked example, the setting the database ships, __BENCH_RUNS__; the score is the
mean over them. The adjudication in \textbf{b} and \textbf{c} was run earlier, against a
four-example benchmark extraction of the same model, so panel \textbf{a} and the adjudication
describe the same two models at different prompt settings. Repeats matter here: runs of one model at identical settings, differing only in
the model's nondeterminism, span $0.05$ in $F_1$, which is wider than the gap between two of these
three models.

Panels \textbf{b} and \textbf{c} report the adjudication of __RECORDS__ records by two chemists.
Both graders flag more records than the chemists reject (\textbf{b}): of the metric's
__METRIC_FLAGS__ flags, __METRIC_RIGHT__ were records a chemist also called wrong, a precision of
__METRIC_PRECISION__, against __JUDGE_PRECISION__ for the judge on __JUDGE_FLAGS__ flags. Recall
runs the other way, since the metric flags freely enough to catch everything the chemists
rejected, so $F_1$ separates the two less than precision does. Agreement beyond chance is low for
both ($\kappa = __METRIC_KAPPA__$ and $__JUDGE_KAPPA__$): neither grader substitutes for a chemist.

The comparison between them is nonetheless clear (\textbf{c}). Of the __PAIRS__ records where
exactly one grader matched the chemists, __FAVOUR_JUDGE__ favour the judge and __FAVOUR_METRIC__
the metric ($p = __MCNEMAR_P__$, McNemar). Those pairs all come from the disagreement stratum,
which was censused rather than sampled, so the comparison carries no sampling error. The recall
figures beside it do: their intervals are wide because the accepted stratum was sampled,
__SAMPLED__ records of it reviewed."""


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
    print("\n" + caption(
        CAPTION,
        records=records, sampled=reviewed,
        bench_shots=int(scores["n_shots"].iloc[0]),
        bench_runs=("over {} repeats each".format(int(scores["runs"].min()))
                    if scores["runs"].nunique() == 1 and scores["runs"].min() > 1
                    else "over {} to {} repeats per model".format(
                        int(scores["runs"].min()), int(scores["runs"].max()))),
        best_model=ranked.index[0], best_f1=f"{ranked.f1.iloc[0]:.3f}",
        best_sd=f"{ranked['f1 sd'].iloc[0]:.3f}",
        second_model=ranked.index[1], second_f1=f"{ranked.f1.iloc[1]:.3f}",
        metric_flags=int(table.loc["metric", "flagged"]),
        metric_right=int(table.loc["metric", "of those wrong"]),
        metric_precision=f"{table.loc['metric', 'precision']:.2f}",
        metric_kappa=f"{table.loc['metric', 'kappa']:.2f}",
        judge_flags=int(table.loc["judge", "flagged"]),
        judge_precision=f"{table.loc['judge', 'precision']:.2f}",
        judge_kappa=f"{table.loc['judge', 'kappa']:.2f}",
        pairs=mcnemar["informative pairs"],
        favour_judge=mcnemar["favouring the judge"],
        favour_metric=mcnemar["favouring the metric"],
        mcnemar_p=sci(mcnemar["p"])))


if __name__ == "__main__":
    main()
