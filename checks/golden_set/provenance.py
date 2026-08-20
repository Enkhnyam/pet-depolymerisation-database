from _setup import *

labels = scored()
with_judge = labels.merge(judged(),
                          left_on=["doi", "extracted_index"], right_on=["doi", "index"])

def describe(row):
    if row.verdict == "MISMATCH":
        return "matched, then rejected"
    if row.verdict == "FP":
        return "no matching curated experiment"
    return "metric accepted the record"

with_judge["situation"] = with_judge.apply(describe, axis=1)
everything = pd.crosstab(with_judge.situation, with_judge.judge)

labelled = golden().merge(labels, on=["doi", "extracted_index"], suffixes=("", "_metric"))
labelled["situation"] = labelled.apply(describe, axis=1)
chosen = pd.crosstab(labelled.situation, labelled.judge_v4)

print("all", len(with_judge), "extracted records, by what the metric did and what the judge said:")
print(everything.to_string())
print()
print("the", len(labelled), "records the chemists labelled:")
print(chosen.to_string())
print()
print("Every record where the metric and the judge disagreed on the catalyst name was kept, since")
print("those decide which grader is right. Records with no curated match were sampled rather than")
print("taken whole, because there are too many of them. Records both graders accepted form a")
print("control group: if a grader is only agreeing by luck, it shows up there.")
