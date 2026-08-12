import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ARTIFACTS, ROOT, RUNS_DIR, data_path
from core.schema import Experiment, load_curated
from core.evaluation import evaluate

extraction_run = "extract_oss/extract_oss_n4_r1"
judge_run = "judge_oss_on_oss/judge_oss_on_oss"

curated_table = "curated_table_final.json"
golden_set_file = ARTIFACTS / "gold/final/golden_set_judge_sol_v3.json"

accept_threshold = 0.3
catalyst_threshold = 0.6
numeric_tolerance = 0.2

outcomes = ["yield_percent", "selectivity_percent", "conversion_percent"]
fields = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

def curated(filename=curated_table):
    papers = json.loads(data_path(filename).read_text())
    rows = []
    for paper in papers:
        for entry in paper["extracted_experiments"]:
            rows.append({"doi": paper["doi"], **entry["experiment_data"]})
    return pd.DataFrame(rows)

def extracted(bundle=extraction_run):
    rows = []
    for path in glob.glob(str(RUNS_DIR / bundle / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        for position, record in enumerate(paper["records"]):
            rows.append({"doi": paper["doi"], "index": position, **record})
    return pd.DataFrame(rows)

def as_experiments(bundle):
    by_paper = {}
    for path in glob.glob(str(RUNS_DIR / bundle / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        by_paper[paper["doi"]] = [Experiment.model_validate(r) for r in paper["records"]]
    return by_paper

def scored(bundle=extraction_run, curation=curated_table, catalyst=catalyst_threshold):
    reference = load_curated(data_path(curation))
    _, labels = evaluate(reference, as_experiments(bundle), accept_threshold, catalyst, numeric_tolerance)
    return pd.DataFrame(labels)

def totals(bundle=extraction_run, curation=curated_table, accept=accept_threshold,
           catalyst=catalyst_threshold, tolerance=numeric_tolerance):
    reference = load_curated(data_path(curation))
    result, _ = evaluate(reference, as_experiments(bundle), accept, catalyst, tolerance)
    return result

def judged(bundle=judge_run):
    rows = []
    for path in glob.glob(str(RUNS_DIR / bundle / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        for verdict in paper["verdicts"]:
            if verdict["parsed_ok"]:
                rows.append({"doi": paper["doi"],
                             "index": verdict["extracted_index"],
                             "judge": verdict["verdict"],
                             "bad_fields": verdict["bad_fields"]})
    return pd.DataFrame(rows)

def curated_additions():
    return json.loads(data_path("curated_additions.json").read_text())

def golden():
    labelled = pd.DataFrame(json.loads(golden_set_file.read_text()))
    verdicts = scored()[["doi", "extracted_index", "verdict"]]
    verdicts["metric"] = verdicts.verdict.map({"TP": "correct"}).fillna("incorrect")
    return labelled.drop(columns=["metric"]).merge(
        verdicts[["doi", "extracted_index", "metric"]], on=["doi", "extracted_index"])


def runs():
    configured = {p.stem for p in (ROOT / "ablation_configs").glob("*.yaml")}
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / "*/*/run_meta.json"))):
        run_dir = Path(path).parent
        if run_dir.parent.name not in configured:
            continue
        meta = json.loads(Path(path).read_text())
        meta["run"] = str(run_dir.relative_to(RUNS_DIR))
        rows.append(meta)
    return pd.DataFrame(rows)

def scores_by_run(folder):
    # Scores are recomputed from the saved extractions against the current curated table, not read
    # from the eval.json each run wrote, so every reported number tracks the table as it stands now.
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / folder / "*/config.json"))):
        run_dir = Path(path).parent
        config = json.loads(Path(path).read_text())
        scores = totals(bundle=f"{folder}/{run_dir.name}")
        rows.append({"run": run_dir.name,
                     "n_shots": config["harness_params"]["n_shots"],
                     "f1": scores["f1"],
                     "precision": scores["precision"],
                     "recall": scores["recall"]})
    return pd.DataFrame(rows)
