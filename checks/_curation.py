import glob
import json
from pathlib import Path

from _setup import (RUNS_DIR, data_path, extraction_run, judge_run, scored, judged,
                    golden, curated_table, curated_additions)

as_curated = "curated_data_json_by_doi.json"

DATA_FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
               "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
               "conversion_percent", "pressure_atm"]
OUTCOME_FIELDS = ["yield_percent", "selectivity_percent", "conversion_percent"]

def extracted_records():
    records = {}
    for path in glob.glob(str(RUNS_DIR / extraction_run / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        for position, record in enumerate(paper["records"]):
            records[(paper["doi"], position)] = record
    return records

def cleaned_papers():
    papers = json.loads(data_path(as_curated).read_text())
    records = extracted_records()
    for paper in papers:
        for entry in curated_additions():
            if paper["doi"] == entry["doi"]:
                paper["extracted_experiments"].append(
                    {"experiment_data": records[(entry["doi"], entry["extracted_index"])]})
    for paper in papers:
        already_seen = set()
        keep = []
        for entry in paper["extracted_experiments"]:
            experiment = entry["experiment_data"]
            fingerprint = tuple(str(experiment.get(field)) for field in DATA_FIELDS)
            if fingerprint in already_seen:
                continue
            if all(experiment.get(field) is None for field in OUTCOME_FIELDS):
                continue
            already_seen.add(fingerprint)
            keep.append(entry)
        paper["extracted_experiments"] = keep
    return papers

def missing_experiments():
    from core.evaluation import evaluate
    from core.schema import Experiment
    from _setup import as_experiments, extraction_run
    import pandas as pd

    reference = {paper["doi"]: [Experiment.model_validate(entry["experiment_data"])
                                for entry in paper["extracted_experiments"]]
                 for paper in cleaned_papers()}
    from _setup import accept_threshold, catalyst_threshold, numeric_tolerance
    _, rows = evaluate(reference, as_experiments(extraction_run),
                       accept_threshold, catalyst_threshold, numeric_tolerance)
    labels = pd.DataFrame(rows)
    verdicts = judged(judge_run)
    unmatched = labels[labels.verdict == "FP"]
    with_judge = unmatched.merge(verdicts, left_on=["doi", "extracted_index"],
                                 right_on=["doi", "index"])
    judge_says_real = with_judge[with_judge.judge == "correct"]

    labels = golden()[["doi", "extracted_index", "human"]]
    merged = judge_says_real.merge(labels, on=["doi", "extracted_index"], how="left")

    return merged

def write_version(filename, papers):
    total = sum(len(p["extracted_experiments"]) for p in papers)
    data_path(filename).write_text(json.dumps(papers, indent=2))
    return total
