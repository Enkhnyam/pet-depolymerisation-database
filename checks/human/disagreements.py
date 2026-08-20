"""Where the two graders disagree, which one did the chemists side with -- and on what.

The last block is the concrete case: pairs the metric rejected purely because the catalyst names
differ. Where both graders say correct, the names are the same substance spelled differently and
the metric was wrong. Where both say incorrect, the extracted name is a placeholder that
identifies no substance, so rejecting it was right for the wrong reason.
"""
import pandas as pd

from _setup import CURATED, LABELLED, LABELS, golden, scored, show, sources

GRADERS = ["judge", "metric"]


def main() -> None:
    sources(labels=LABELS, labelled_run=LABELLED, answer_key=CURATED)
    labelled = golden()
    print(f"\nthe chemists rejected {(labelled.human == 'incorrect').sum()} "
          f"of {len(labelled)} records")

    for grader in GRADERS:
        wrong = (labelled[grader] != labelled.human).sum()
        show(f"{grader} against the chemists ({wrong} disagreements)",
             pd.crosstab(labelled[grader], labelled.human,
                         rownames=[grader], colnames=["chemists"]), fmt="{:.0f}")

    disputed = labelled[labelled.metric != labelled.judge]
    show(f"the graders disagree on {len(disputed)}; chemists sided with the judge on "
         f"{(disputed.judge == disputed.human).sum()}",
         pd.crosstab(disputed.judge, disputed.human,
                     rownames=["judge"], colnames=["chemists"]), fmt="{:.0f}")

    for grader in GRADERS:
        show(f"kind of record {grader} gets wrong",
             labelled[labelled[grader] != labelled.human].situation.value_counts(), fmt="{:.0f}")

    rejected = scored(run=LABELLED).query("verdict == 'MISMATCH' and catalyst_match == False")
    names = pd.DataFrame({
        "doi": rejected.doi, "index": rejected["index"],
        "curated": [row["catalyst"]["curated"] for row in rejected.fields],
        "extracted": [row["catalyst"]["extracted"] for row in rejected.fields]})
    merged = names.merge(labelled[["doi", "index", "judge", "human"]], on=["doi", "index"])
    show(f"the {len(merged)} rejected on the catalyst name alone",
         merged[["judge", "human", "curated", "extracted"]].reset_index(drop=True))


if __name__ == "__main__":
    main()
