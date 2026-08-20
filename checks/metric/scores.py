from _setup import *

records = extracted()
result = totals()

summary = pd.Series({
    "experiments in table": len(curated()),
    "records extracted": len(records),
    "precision": result["precision"],
    "recall": result["recall"],
    "f1": result["f1"],
    "correct": result["tp"],
    "false alarms": result["fp"],
    "missed": result["fn"],
})

print("run    ", extraction_run)
print("papers ", records.doi.nunique())
print()
print(summary.to_string(float_format="{:.3f}".format))
