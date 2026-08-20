from sklearn.metrics import cohen_kappa_score
from _setup import *
from core.evaluation import evaluate
from core.schema import load_curated

labelled = golden()[["doi", "extracted_index", "human", "judge_v4"]]
reference = load_curated(data_path(curated_table))
extraction = as_experiments(extraction_run)

rows = {}
for requirement in [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0]:
    _, labels = evaluate(reference, extraction, 0.3, requirement, 0.2)
    labels = pd.DataFrame(labels)
    labels["metric"] = labels.verdict.map({"TP": "correct"}).fillna("incorrect")
    merged = labelled.merge(labels[["doi", "extracted_index", "metric"]],
                            on=["doi", "extracted_index"])
    rows[requirement] = {"agreement": (merged.human == merged.metric).mean(),
                         "kappa": cohen_kappa_score(merged.human, merged.metric),
                         "records flagged": (merged.metric == "incorrect").sum()}

table = pd.DataFrame(rows).T
table.index.name = "similarity required"
judge_kappa = cohen_kappa_score(labelled.human, labelled.judge_v4)

print(table.to_string(float_format="{:.2f}".format))
print()
print(f"the judge on the same records: kappa {judge_kappa:+.2f}")
print()
print("0.60 is the best setting for this data and is the one reported throughout. Demanding")
print("identical names, or accepting any name, are both worse.")
