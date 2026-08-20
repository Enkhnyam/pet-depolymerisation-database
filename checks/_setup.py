"""Shared loaders for the checks. One place decides what is being measured.

Every check does `from _setup import *` and takes no arguments, so changing a constant here
changes all of them at once and no two checks can disagree about what they are scoring.

Nothing is cached: scored() re-runs the matcher against the curated table as it stands now,
so fixing a yield in the answer key moves every number the next time the suite runs.
"""
import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ARTIFACTS, ROOT, RUNS_DIR, data_path
from core.schema import Experiment, load_curated
from core.evaluation import evaluate

# --- what we are measuring ------------------------------------------------------------------
CURATED = "curated_table_final.json"                          # the 253-experiment answer key
EXTRACTION = RUNS_DIR / "extract_oss/extract_oss_n4_r1"       # scored by the metric checks
JUDGE = RUNS_DIR / "judge_oss_on_oss/judge_oss_on_oss"        # verdicts read by the judge checks
DATABASE = RUNS_DIR / "mass_luna"                             # the 447-paper corpus run
DATABASE_JUDGE = RUNS_DIR / "mass_oss/mass_oss"

# The 48 human labels were made on this run and identify records by position, so they mean
# nothing against any other. Scoring them against a different extraction silently relabels a
# quarter of the set -- record 12 of one run is a different experiment from record 12 of another.
LABELLED = ARTIFACTS / "gold/source_run"
LABELS = ARTIFACTS / "gold/golden_set.json"

ACCEPT, CATALYST, TOLERANCE = 0.30, 0.60, 0.20

OUTCOMES = ["yield_percent", "selectivity_percent", "conversion_percent"]
FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", *OUTCOMES, "pressure_atm"]


# --- loaders --------------------------------------------------------------------------------
def curated(table=CURATED):
    """The answer key, one row per curated experiment."""
    rows = [{"doi": paper["doi"], **entry["experiment_data"]}
            for paper in json.loads(data_path(table).read_text())
            for entry in paper["extracted_experiments"]]
    return pd.DataFrame(rows)


def records(run=EXTRACTION):
    """What a run's model wrote down, one row per record."""
    rows = []
    for path in glob.glob(str(run / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        rows += [{"doi": paper["doi"], "index": i, **r} for i, r in enumerate(paper["records"])]
    return pd.DataFrame(rows)


def experiments(run=EXTRACTION):
    """A run's records as Experiment objects keyed by doi -- what evaluate() expects."""
    out = {}
    for path in glob.glob(str(run / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        out[paper["doi"]] = [Experiment.model_validate(r) for r in paper["records"]]
    return out


def scored(run=EXTRACTION, table=CURATED, accept=ACCEPT, catalyst=CATALYST, tolerance=TOLERANCE):
    """The metric's verdict on every record, plus a plain-language `situation`."""
    reference = load_curated(data_path(table))
    _, labels = evaluate(reference, experiments(run), accept, catalyst, tolerance)
    frame = pd.DataFrame(labels)
    frame = frame[frame.extracted_index.notna()].copy()
    frame["index"] = frame.extracted_index.astype(int)
    frame["metric"] = frame.verdict.map({"TP": "correct"}).fillna("incorrect")
    frame["situation"] = frame.verdict.map({"TP": "accepted",
                                            "MISMATCH": "matched, names differ",
                                            "FP": "no curated counterpart"})
    return frame


def totals(run=EXTRACTION, table=CURATED, accept=ACCEPT, catalyst=CATALYST, tolerance=TOLERANCE):
    """Precision, recall and F1 for a whole run."""
    reference = load_curated(data_path(table))
    result, _ = evaluate(reference, experiments(run), accept, catalyst, tolerance)
    return result


def judged(run=JUDGE):
    """The judge's verdict on every record it could parse."""
    rows = []
    for path in glob.glob(str(run / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        rows += [{"doi": paper["doi"], "index": v["extracted_index"],
                  "judge": "correct" if v["verdict"] == "correct" else "incorrect",
                  "bad_fields": v["bad_fields"]}
                 for v in paper["verdicts"] if v["parsed_ok"]]
    return pd.DataFrame(rows)


def golden():
    """The 48 human-labelled records with both graders' verdicts on the same rows.

    Scored against LABELLED, never EXTRACTION -- see the note on LABELLED above.
    """
    labelled = pd.DataFrame(json.loads(LABELS.read_text()))
    # `judge` in the file is an older rubric; judge_v4 is the one reported everywhere.
    labelled = labelled.drop(columns=["judge"]).rename(columns={"judge_v4": "judge",
                                                               "extracted_index": "index"})
    verdicts = scored(run=LABELLED)[["doi", "index", "metric", "situation"]]
    return labelled.drop(columns=["metric", "judge_critique", "judge_bad_fields"],
                         errors="ignore").merge(verdicts, on=["doi", "index"])


def runs():
    """The cost and token ledger for every run that still has a config."""
    configured = {p.stem for p in (ROOT / "configs").glob("*/*.yaml")}
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / "*/run_meta.json"))
                       + glob.glob(str(RUNS_DIR / "*/*/run_meta.json"))):
        run_dir = Path(path).parent
        if run_dir.name in configured or run_dir.parent.name in configured:
            rows.append({**json.loads(Path(path).read_text()),
                         "run": str(run_dir.relative_to(RUNS_DIR))})
    return pd.DataFrame(rows)


def show(title, data, fmt="{:.3f}"):
    """Print one titled block. The only output helper the checks use."""
    if isinstance(data, dict):
        data = pd.Series(data)
    print(f"\n{title}\n{data.to_string(float_format=fmt.format)}")
