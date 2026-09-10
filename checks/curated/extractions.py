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


REPEATS = 3          # arms with fewer runs than this are not a position on the plane


def configurations() -> pd.DataFrame:
    """Every benchmark configuration as a point of score against money.

    The extractor choice is usually argued one variable at a time -- this model beats that one,
    one worked example beats none -- and the two interact through cost, because an example is
    input tokens on every paper. Put every arm on one plane and the argument becomes a Pareto
    one: which configurations are not beaten on both counts at once.

    Cost comes from the spend ledger, which records what each run actually billed, so a free
    endpoint reads as free rather than as a token count nobody paid for.
    """
    import cost as cost_check
    # the package form, not a bare name: checks/curated is on sys.path when
    # checks/run.py runs this file, and is not when a figure imports it
    from curated import shots as shots_check

    ledger = cost_check.compute()
    ledger = ledger.assign(name=ledger.run.str.split("/").str[-1]).set_index("name")

    def billed(name):
        return float(ledger.loc[name, "cost_usd"]) if name in ledger.index else float("nan")

    # Both sweeps, because the two dimensions of this choice live in different folders: the
    # model comparison in extract_*, the worked-example sweep in shots_*. A Pareto argument over
    # one of them alone is the argument this figure already made twice.
    both = pd.concat([
        runs()[["model", "n_shots", "run", "f1"]],
        shots_check.compute().assign(model="luna")[["model", "n_shots", "run", "f1"]],
    ]).drop_duplicates(subset=["run"])
    both = both.assign(cost=[billed(name) for name in both.run]).dropna(subset=["cost"])

    grouped = (both.groupby(["model", "n_shots"])
               .agg(f1=("f1", "mean"), sd=("f1", "std"), cost=("cost", "mean"),
                    repeats=("f1", "size"))
               .reset_index())
    # Arms the sweep only ran once are dropped rather than plotted beside arms with three: at
    # this spread a single run is not a position on the plane, and one of them would have sat on
    # the frontier on the strength of a run nobody repeated.
    grouped = grouped[grouped.repeats >= REPEATS].reset_index(drop=True)

    # A configuration is on the frontier when nothing costs less *and* scores at least as much.
    grouped["on frontier"] = [
        not ((grouped.cost <= row.cost) & (grouped.f1 >= row.f1)
             & ((grouped.cost < row.cost) | (grouped.f1 > row.f1))).any()
        for row in grouped.itertuples()]
    return grouped.sort_values("cost").reset_index(drop=True)


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
    # a spread per measure, not only for f1: the panel draws error bars on all three, and three
    # runs of one model at identical settings span more than the gap between two models
    for measure in ("precision", "recall", "f1"):
        table[f"{measure} sd"] = grouped[measure].std().fillna(0.0)
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
