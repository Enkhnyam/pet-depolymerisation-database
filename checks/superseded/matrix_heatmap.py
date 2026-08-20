"""The judge x extraction matrix: how far each judge agrees with the metric grader, and at what cost.

One row per cell. Agreement and kappa are between the two graders on the same records -- no human
labels are involved, which is the point: this is the number available on a corpus with no curated
table, and therefore the number the mass extraction has to lean on.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from _setup import (RUNS_DIR, data_path, accept_threshold, catalyst_threshold,
                    numeric_tolerance, as_experiments)
from core.evaluation import evaluate
from core.schema import load_curated

REFERENCE = "curated_table_final.json"


def extraction_runs():
    """Repeat r1 of each model. The judges were run against r1, so scoring r2 or r3 here would
    compare a judge's verdicts with a metric computed over a different set of records."""
    found = {}
    for path in sorted(glob.glob(str(RUNS_DIR / "extract_*/*_r1/run_meta.json"))):
        run_dir = Path(path).parent
        found[run_dir.parent.name.replace("extract_", "")] = run_dir.relative_to(RUNS_DIR)
    return found


def repeats_of(model):
    return sorted(Path(p).parent.relative_to(RUNS_DIR)
                  for p in glob.glob(str(RUNS_DIR / f"extract_{model}/*/run_meta.json")))


def judge_runs():
    found = {}
    for path in glob.glob(str(RUNS_DIR / "judge_*_on_*/*/judge_meta.json")):
        run_dir = Path(path).parent
        judge, target = run_dir.parent.name.replace("judge_", "").split("_on_")
        found[(judge, target)] = run_dir.relative_to(RUNS_DIR)
    return found


def metric_verdicts(bundle):
    reference = load_curated(data_path(REFERENCE))
    result, labels = evaluate(reference, as_experiments(str(bundle)),
                              accept_threshold, catalyst_threshold, numeric_tolerance)
    frame = pd.DataFrame(labels)
    frame = frame[frame.extracted_index.notna()].copy()
    frame["index"] = frame.extracted_index.astype(int)
    frame["metric"] = frame.verdict.map({"TP": "correct"}).fillna("incorrect")
    return result, frame[["doi", "index", "metric"]]


def judge_verdicts(bundle):
    rows = []
    for path in glob.glob(str(RUNS_DIR / bundle / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        for verdict in paper["verdicts"]:
            if verdict.get("parsed_ok"):
                rows.append({"doi": paper["doi"], "index": verdict["extracted_index"],
                             "judge": verdict["verdict"],
                             "fixes": len(verdict.get("fixes") or []),
                             "drop": bool(verdict.get("drop_record"))})
    return pd.DataFrame(rows)


def spend(bundle, key):
    meta = json.loads((RUNS_DIR / bundle / key).read_text())
    return meta.get("cost_usd", 0.0) or 0.0, meta.get("prompt_tokens", 0) or 0


extractions = extraction_runs()
judges = judge_runs()

if not extractions:
    print("No extraction runs yet. Run scripts/matrix_extractions.sh first.")
    raise SystemExit(0)

print("EXTRACTIONS, scored against the curated table")
ext_rows = []
scored_cache = {}
for name, bundle in sorted(extractions.items()):
    result, verdicts = metric_verdicts(bundle)
    scored_cache[name] = verdicts
    cost, tokens = spend(bundle, "run_meta.json")
    ext_rows.append({"extraction": name, "records": result["tp"] + result["fp"],
                     "precision": result["precision"], "recall": result["recall"],
                     "f1": result["f1"], "cost_usd": cost, "in_tokens": tokens})
print(pd.DataFrame(ext_rows).to_string(index=False, float_format="{:.3f}".format))

if not judges:
    print("\nNo judge runs yet. Run scripts/matrix_judges.sh once the extractions finish.")
    raise SystemExit(0)

print("\nMATRIX: each judge against the metric grader, on each extraction")
cells = []
for (judge, target), bundle in sorted(judges.items()):
    if target not in scored_cache:
        continue
    both = scored_cache[target].merge(judge_verdicts(bundle), on=["doi", "index"])
    if both.empty:
        continue
    agree = (both.judge == both.metric).mean()
    kappa = (cohen_kappa_score(both.judge, both.metric)
             if both.judge.nunique() > 1 and both.metric.nunique() > 1 else float("nan"))
    cost, tokens = spend(bundle, "judge_meta.json")
    cells.append({"judge": judge, "extraction": target, "records": len(both),
                  "agreement": agree, "kappa": kappa,
                  "judge_says_correct": (both.judge == "correct").mean(),
                  "fixes": int(both.fixes.sum()), "drops": int(both["drop"].sum()),
                  "cost_usd": cost})

matrix = pd.DataFrame(cells)
print(matrix.to_string(index=False, float_format="{:.3f}".format))

for measure in ("agreement", "kappa", "cost_usd"):
    grid = matrix.pivot(index="judge", columns="extraction", values=measure)
    print(f"\n{measure} — judges down, extractions across")
    print(grid.to_string(float_format="{:.3f}".format))

print("\nWhat the projection uses: for a corpus with no curated table, only the judge's verdicts")
print("exist. The agreement measured here is what licenses reading a judge's pass rate as an")
print("estimate of F1. A cell where the two graders agree strongly is a cell whose judge can")
print("stand in for the metric; a cell where they do not is one whose projection would be guesswork.")
