"""Every benchmark extraction scored against the curated answer key.

This is the table the model choice was made from. Scoring one arbitrary run says nothing; the
comparison is the point -- and for a while this table was making exactly that mistake, reporting
one run per model as though it were the model's score.

It is not. Four runs of luna at identical settings -- same prompt, same seed, same papers, the
model's own nondeterminism the only thing free to vary -- score 0.749, 0.757, 0.799 and 0.799.
A spread of 0.05 is wider than most of the differences this paper discusses, including the gap
between two of the models here. So every run is scored separately and arms are reported as a mean
over repeats with the spread beside it; a single run is a draw, not a measurement.

Runs are grouped by (model, n_shots), which is what a repeat holds fixed.
"""
import glob
import json
from pathlib import Path

import pandas as pd

from _setup import CURATED, RUNS_DIR, curated, records, show, sources, totals


def runs() -> pd.DataFrame:
    """One row per benchmark run, with the arm it belongs to."""
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / "extract_*/*/run_meta.json"))):
        run_dir = Path(path).parent
        config = json.loads((run_dir / "config.json").read_text())
        result = totals(run=run_dir)
        rows.append({
            "model": run_dir.parent.name.replace("extract_", ""),
            "n_shots": int(config["harness_params"]["n_shots"]),
            "run": run_dir.name,
            "records": len(records(run_dir)),
            "precision": result["precision"],
            "recall": result["recall"],
            "f1": result["f1"],
            "correct": result["tp"],
            "false alarms": result["fp"],
            "missed": result["fn"],
        })

    return pd.DataFrame(rows)


def arms(shots: int | None = None) -> pd.DataFrame:
    """Mean and spread per model, over the repeats of one arm.

    `shots` picks the arm. With none given it picks the arm every model has, preferring the one
    with the most repeats -- never each model's own best arm independently, which would compare
    one model at one example against another at four and call it a model difference. While a
    sweep is still running, that rule holds the table on the arm all three models have finished.
    """
    frame = runs()
    if shots is not None:
        frame = frame[frame.n_shots == shots]
    else:
        covered = frame.groupby("n_shots").model.nunique()
        shared = covered[covered == frame.model.nunique()].index
        if len(shared):
            repeats = frame[frame.n_shots.isin(shared)].groupby("n_shots").size()
            frame = frame[frame.n_shots == repeats.idxmax()]
    grouped = frame.groupby("model")
    table = grouped[["precision", "recall", "f1"]].mean()
    table["f1 sd"] = grouped.f1.std().fillna(0.0)
    table["runs"] = grouped.size()
    table["n_shots"] = grouped.n_shots.first()
    return table


def compute() -> pd.DataFrame:
    """Backwards-compatible view: one row per model, averaged over its arm."""
    return arms()


def main() -> None:
    sources(answer_key=CURATED, extractions=RUNS_DIR / "extract_*")
    table = curated()
    print(f"\nscored against {len(table)} curated experiments from {table.doi.nunique()} papers")
    show("every benchmark run", runs().set_index(["model", "n_shots", "run"]))
    show("per arm, averaged over repeats", arms())


if __name__ == "__main__":
    main()
