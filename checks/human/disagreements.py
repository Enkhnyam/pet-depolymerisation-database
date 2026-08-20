"""Where the two graders disagree, which one did the chemists side with -- and what kind of
record each grader gets wrong.

The last table is the argument that the two graders are not redundant: they fail on different
kinds of record.
"""
import pandas as pd

from _setup import golden, show

GRADERS = ["judge", "metric"]


def main() -> None:
    labelled = golden()
    rejected = (labelled.human == "incorrect").sum()
    print(f"\nthe chemists rejected {rejected} of {len(labelled)} records")

    for grader in GRADERS:
        wrong = (labelled[grader] != labelled.human).sum()
        table = pd.crosstab(labelled[grader], labelled.human,
                            rownames=[grader], colnames=["chemists"])
        show(f"{grader} against the chemists ({wrong} disagreements)", table, fmt="{:.0f}")

    disputed = labelled[labelled.metric != labelled.judge]
    judge_right = (disputed.judge == disputed.human).sum()
    show(f"the graders disagree on {len(disputed)}; chemists sided with the judge on {judge_right}",
         pd.crosstab(disputed.judge, disputed.human,
                     rownames=["judge"], colnames=["chemists"]), fmt="{:.0f}")

    for grader in GRADERS:
        mistakes = labelled[labelled[grader] != labelled.human]
        show(f"kind of record {grader} gets wrong", mistakes.situation.value_counts(), fmt="{:.0f}")


if __name__ == "__main__":
    main()
