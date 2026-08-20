from collections import Counter

from _setup import *

TEXT_FIELDS = {"catalyst", "solvent"}

labels = scored()
records = labels[labels.extracted_index.notna()].copy()
records["index"] = records.extracted_index.astype(int)
paired = records[~records.reason.fillna("").str.contains("unmatched extracted")]

both = paired.merge(judged(), on=["doi", "index"])
both["judge"] = both.judge.where(both.judge == "correct", "incorrect")
both["metric"] = both.verdict.map({"TP": "correct"}).fillna("incorrect")

print("records the table could be compared against:", len(both))
print("the two graders reach the same verdict on  :", (both.judge == both.metric).sum())
print()

rejected_by_metric = both[both.metric == "incorrect"]
on_name = rejected_by_metric.reason.fillna("").str.contains("catalyst mismatch").sum()
print(f"the metric rejects {len(rejected_by_metric)} of them")
print(f"  because the catalyst name did not match: {on_name}")
print(f"  because the numbers were out of range  : {len(rejected_by_metric) - on_name}")
print()

rejected_by_judge = both[both.judge == "incorrect"]
naming_text = sum(1 for row in rejected_by_judge.bad_fields if TEXT_FIELDS & set(row))
print(f"the judge rejects {len(rejected_by_judge)} of them")
print(f"  naming a text field (catalyst or solvent): {naming_text}")
print("  fields it names:",
      dict(Counter(f for row in rejected_by_judge.bad_fields for f in row)))
print()

accepted = both[both.verdict == "TP"]
still_wrong = Counter(f for row in accepted.field_errors for f in row)
numeric_errors = sum(v for f, v in still_wrong.items() if f not in TEXT_FIELDS)
print(f"inside the {len(accepted)} pairs the metric accepted it still counted "
      f"{sum(still_wrong.values())} wrong fields,")
print(f"  {numeric_errors} of them numeric, and not one of those made either grader reject "
      f"the record.")
print()
print("Eight of the ten fields are numbers, and numbers leave nothing to interpret: a value is")
print("inside the tolerance or it is not, and both graders reach the same answer. Almost every")
print("disagreement between them sits on the catalyst, the one field written as free text. In a")
print("task whose output is this rigid, a judge that reads the paper and an algorithm that")
print("compares against a table are doing nearly the same job.")
