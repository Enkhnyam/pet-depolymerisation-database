from _setup import *

labels = scored()
verdict_counts = labels.verdict.value_counts()

rejected_matches = labels[labels.verdict == "MISMATCH"]
rejected_on_name = (rejected_matches.catalyst_match == False).sum()

with_judge = labels.merge(judged(),
                          left_on=["doi", "extracted_index"], right_on=["doi", "index"])
judge_view = pd.crosstab(with_judge.verdict, with_judge.judge)

print("the metric's verdict on every record:")
print(verdict_counts.to_string())
print()
print("A MISMATCH is a pair the metric matched and then rejected, so it counts as both a false")
print("positive and a false negative. That is why the reported FP and FN exceed these counts.")
print()
print("rejected matches                       ", len(rejected_matches))
print("of those, rejected on the catalyst name", rejected_on_name)
print()
print("what the judge says about each group:")
print(judge_view.to_string())
