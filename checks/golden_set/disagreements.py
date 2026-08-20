from _setup import *

labelled = golden()
labels = scored()
detailed = labelled.merge(labels, on=["doi", "extracted_index"], suffixes=("", "_metric"))

def describe(row):
    if row.verdict == "MISMATCH":
        return "matched, but the catalyst names differ"
    if row.verdict == "FP":
        return "no matching curated experiment"
    return "metric accepted the record"

detailed["situation"] = detailed.apply(describe, axis=1)

print("the chemists rejected", (labelled.human == "incorrect").sum(), "of", len(labelled), "records")
print()

for grader, name in [("judge_v4", "judge"), ("metric", "metric")]:
    table = pd.crosstab(labelled[grader], labelled.human,
                        rownames=[name], colnames=["chemists"])
    wrong = (labelled[grader] != labelled.human).sum()
    print(f"{name} against the chemists ({wrong} disagreements):")
    print(table.to_string())
    print()

disputed = labelled[labelled.metric != labelled.judge_v4]
sided_with = pd.crosstab(disputed.judge_v4, disputed.human,
                         rownames=["judge"], colnames=["chemists"])
judge_right = (disputed.judge_v4 == disputed.human).sum()

print(f"the two graders disagree on {len(disputed)} records; the chemists sided with the judge on "
      f"{judge_right} of them:")
print(sided_with.to_string())
print()

for grader, name in [("judge_v4", "judge"), ("metric", "metric")]:
    mistakes = detailed[detailed[grader] != detailed.human]
    print(f"the kind of record {name} gets wrong:")
    print(mistakes.situation.value_counts().to_string())
    print()
