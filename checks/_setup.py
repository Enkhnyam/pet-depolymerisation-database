"""Shared loaders for the check scripts.

One module decides what is being measured, so no two checks can disagree about it. Every check
imports the names it uses explicitly -- there is no star import, so you can always tell where a
name came from.

Nothing is cached: scored() re-runs the matcher against the curated table as it stands now, so
correcting a yield in the answer key moves every number the next time the suite runs.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from core.paths import ARTIFACTS, ROOT, RUNS_DIR, data_path
from core.schema import Experiment, load_curated
from core.evaluation import evaluate


# --- what is being measured -----------------------------------------------------------------
CURATED = "curated_table_final.json"                       # the 295-experiment answer key

# The shipped pair: luna extracts, gpt-oss judges. These were left pointing at extract_oss and
# judge_oss_on_oss long after luna became the extractor the database is built with, which meant
# the metric checks -- and the threshold sweeps in Figure 4 -- described a model that was never
# shipped. EXTRACTION and JUDGE must stay a matched pair: JUDGE is a judge run *on* EXTRACTION.
EXTRACTION = RUNS_DIR / "extract_luna/extract_luna_n4_r1"  # scored by the metric checks
JUDGE = RUNS_DIR / "judge_oss_on_luna/judge_oss_on_luna"   # read by the judge checks
DATABASE = RUNS_DIR / "mass_luna_1shot"                    # the 1,026-paper corpus run
DATABASE_JUDGE = RUNS_DIR / "mass_oss_1shot/mass_oss_1shot"

# The 48 human labels identify records by position within the run they were drawn from, so they
# mean nothing against any other extraction: record 12 of one run is a different experiment from
# record 12 of another. Scoring them elsewhere silently relabels about a quarter of the set.
LABELLED = ARTIFACTS / "gold/source_run"
LABELS = ARTIFACTS / "gold/golden_set.json"

ACCEPT = 0.30       # a matched pair is accepted below this penalty
CATALYST = 0.60     # catalyst names must be at least this similar to pair at all
TOLERANCE = 0.20    # numbers agree within this fraction

OUTCOMES = ["yield_percent", "selectivity_percent", "conversion_percent"]
FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", *OUTCOMES, "pressure_atm"]


# --- loaders --------------------------------------------------------------------------------
def curated(table: str = CURATED) -> pd.DataFrame:
    """The answer key, one row per curated experiment."""
    papers = json.loads(data_path(table).read_text())

    rows = []
    for paper in papers:
        for entry in paper["extracted_experiments"]:
            rows.append({"doi": paper["doi"], **entry["experiment_data"]})
    return pd.DataFrame(rows)


def records(run: Path = EXTRACTION) -> pd.DataFrame:
    """What a run's model wrote down, one row per record."""
    rows = []
    for path in glob.glob(str(run / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        for position, record in enumerate(paper["records"]):
            rows.append({"doi": paper["doi"], "index": position, **record})
    return pd.DataFrame(rows)


def experiments(run: Path = EXTRACTION) -> dict:
    """A run's records as Experiment objects keyed by doi -- the shape evaluate() expects."""
    by_paper = {}
    for path in glob.glob(str(run / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        by_paper[paper["doi"]] = [Experiment.model_validate(r) for r in paper["records"]]
    return by_paper


def scored(run: Path = EXTRACTION, table: str = CURATED, accept: float = ACCEPT,
           catalyst: float = CATALYST, tolerance: float = TOLERANCE) -> pd.DataFrame:
    """The metric's verdict on every extracted record.

    Adds two columns the checks read constantly: `metric` (correct / incorrect) and `situation`,
    which says *why* -- whether the record was accepted, matched but rejected on the catalyst
    name, or had no curated counterpart to compare against at all.
    """
    reference = load_curated(data_path(table))
    _, labels = evaluate(reference, experiments(run), accept, catalyst, tolerance)

    frame = pd.DataFrame(labels)
    frame = frame[frame.extracted_index.notna()].copy()   # drop curated rows nothing matched
    frame["index"] = frame.extracted_index.astype(int)
    frame["metric"] = frame.verdict.map({"TP": "correct"}).fillna("incorrect")
    # A MISMATCH is a pair the assignment made and then rejected, and it happens two different
    # ways: the catalyst gate refused the pair, or the catalyst agreed and the numbers pushed the
    # average past the accept threshold. Collapsing both into one label blamed the catalyst for
    # fourteen of twenty-five records where the catalyst string was identical.
    gate_failed = frame.fields.apply(
        lambda f: isinstance(f, dict) and f["catalyst"]["penalty"] > 0)
    frame["situation"] = frame.verdict.map({"TP": "accepted", "FP": "no curated counterpart"})
    frame.loc[frame.verdict == "MISMATCH", "situation"] = np.where(
        gate_failed[frame.verdict == "MISMATCH"],
        "the catalyst names differ", "the numbers differ")
    return frame


def totals(run: Path = EXTRACTION, table: str = CURATED, accept: float = ACCEPT,
           catalyst: float = CATALYST, tolerance: float = TOLERANCE) -> dict:
    """Precision, recall and F1 for a whole run."""
    reference = load_curated(data_path(table))
    result, _ = evaluate(reference, experiments(run), accept, catalyst, tolerance)
    return result


def judged(run: Path = JUDGE) -> pd.DataFrame:
    """The judge's verdict on every record it could parse."""
    rows = []
    for path in glob.glob(str(run / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        for verdict in paper["verdicts"]:
            if not verdict["parsed_ok"]:
                continue
            rows.append({
                "doi": paper["doi"],
                "index": verdict["extracted_index"],
                # the rubric allows several wordings; only "correct" counts as a pass
                "judge": "correct" if verdict["verdict"] == "correct" else "incorrect",
                "bad_fields": verdict["bad_fields"],
            })
    return pd.DataFrame(rows)


def golden() -> pd.DataFrame:
    """The 48 human-labelled records, with both graders' verdicts on the same rows.

    Scored against LABELLED, never EXTRACTION -- see the note on LABELLED above.
    """
    labelled = pd.DataFrame(json.loads(LABELS.read_text()))

    # `judge` in the file is an older rubric; judge_v4 is the one reported everywhere else.
    labelled = labelled.drop(columns=["judge", "metric"])
    labelled = labelled.rename(columns={"judge_v4": "judge", "extracted_index": "index"})

    verdicts = scored(run=LABELLED)[["doi", "index", "metric", "situation"]]
    return labelled.merge(verdicts, on=["doi", "index"])


def runs() -> pd.DataFrame:
    """The cost and token ledger for every run that still has a config."""
    configured = {path.stem for path in (ROOT / "configs").glob("*/*.yaml")}

    # mass runs sit one directory shallower than the matrix runs, so both depths are searched
    paths = (glob.glob(str(RUNS_DIR / "*/run_meta.json"))
             + glob.glob(str(RUNS_DIR / "*/*/run_meta.json")))

    rows = []
    for path in sorted(paths):
        run_dir = Path(path).parent
        if run_dir.name not in configured and run_dir.parent.name not in configured:
            continue
        meta = json.loads(Path(path).read_text())
        meta["run"] = str(run_dir.relative_to(RUNS_DIR))
        rows.append(meta)
    return pd.DataFrame(rows)


def sources(**named) -> None:
    """Print the bundles a check reads, so any number can be traced back to the files behind it.

    Run directories are named with the model that produced them and the config that defines them,
    because that is what a reviewer needs to check a claim: which model, under which settings,
    over which papers.
    """
    width = max([len(label) for label in named] + [len("thresholds")])
    print("reads")
    for label, target in named.items():
        if isinstance(target, str) and not str(target).startswith("/"):
            print(f"  {label:{width}s}  artifacts/data/{target}")
            continue

        path = Path(target)
        where = path.relative_to(ROOT) if path.is_absolute() and ROOT in path.parents else path
        detail = []
        for meta_name in ("run_meta.json", "judge_meta.json"):
            meta_file = path / meta_name
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                detail.append(meta.get("model", ""))
                if meta.get("n_papers"):
                    detail.append(f"{meta['n_papers']} papers")
                break
        if (path / "config.json").exists():
            detail.append("config.json")
        note = "   " + " · ".join(d for d in detail if d) if detail else ""
        print(f"  {label:{width}s}  {where}{note}")

    print(f"  {'thresholds':{width}s}  accept {ACCEPT:.2f} · catalyst {CATALYST:.2f} · "
          f"tolerance {TOLERANCE:.2f}")


def show(title: str, data, fmt: str = "{:.3f}") -> None:
    """Print one titled block. The only output helper the checks use."""
    if isinstance(data, dict):
        data = pd.Series(data)
    print(f"\n{title}\n{data.to_string(float_format=fmt.format)}")
