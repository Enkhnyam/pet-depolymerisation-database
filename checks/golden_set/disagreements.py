"""Where the two graders disagree, which one did the chemists side with -- and what kind of
record each grader gets wrong. The last table is the argument they are not redundant."""
from _setup import *

labelled = golden()
print(f"\nthe chemists rejected {(labelled.human == 'incorrect').sum()} of {len(labelled)} records")

for grader in ["judge", "metric"]:
    show(f"{grader} against the chemists "
         f"({(labelled[grader] != labelled.human).sum()} disagreements)",
         pd.crosstab(labelled[grader], labelled.human,
                     rownames=[grader], colnames=["chemists"]), fmt="{:.0f}")

disputed = labelled[labelled.metric != labelled.judge]
show(f"the graders disagree on {len(disputed)}; chemists sided with the judge on "
     f"{(disputed.judge == disputed.human).sum()}",
     pd.crosstab(disputed.judge, disputed.human, rownames=["judge"], colnames=["chemists"]),
     fmt="{:.0f}")

for grader in ["judge", "metric"]:
    show(f"kind of record {grader} gets wrong",
         labelled[labelled[grader] != labelled.human].situation.value_counts(), fmt="{:.0f}")
