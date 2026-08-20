"""What happens to the extraction's score as records are added to the answer key.

Adding records the extraction itself produced lifts its own score without the extraction
changing. That is the circularity argument for not growing the curated set from disagreements.
The bootstrap says whether the shift on the labelled records is distinguishable from zero.
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from _setup import (ACCEPT, CATALYST, CURATED, LABELLED, TOLERANCE, experiments, golden, judged,
                    scored, show)
from core.evaluation import evaluate
from core.paths import data_path
from core.schema import Experiment

RESAMPLES = 10000
UNMATCHED = "no curated counterpart"


def reference_with(base: dict, extraction: dict, additions: list) -> dict:
    """The answer key, plus a chosen set of extracted records promoted into it."""
    reference = {}
    for doi, paper in base.items():
        rows = [entry["experiment_data"] for entry in paper["extracted_experiments"]]
        rows += [extraction[doi][index] for added_doi, index in additions if added_doi == doi]
        reference[doi] = [Experiment.model_validate(row) for row in rows]
    return reference


def verdicts_with(reference: dict) -> pd.DataFrame:
    """The metric's correct/incorrect call on each record, under a given answer key."""
    _, labels = evaluate(reference, experiments(LABELLED), ACCEPT, CATALYST, TOLERANCE)

    frame = pd.DataFrame(labels)
    frame = frame[frame.extracted_index.notna()].copy()
    frame["index"] = frame.extracted_index.astype(int)
    frame["m"] = frame.verdict.map({"TP": "correct"}).fillna("incorrect")
    return frame[["doi", "index", "m"]]


def main() -> None:
    both = scored(run=LABELLED).merge(judged(), on=["doi", "index"])
    unpaired = both.query("situation == @UNMATCHED")
    paired = both.query("situation != @UNMATCHED")

    show("agreement between the two graders", {
        "records": len(both),
        "agree": (both.judge == both.metric).sum(),
        "with a curated counterpart": len(paired),
        "  of those, agree": (paired.judge == paired.metric).sum(),
        "without a counterpart": len(unpaired),
        "  of those, judge accepts": (unpaired.judge == "correct").sum(),
    }, fmt="{:.0f}")

    base = {paper["doi"]: paper for paper in json.loads(data_path(CURATED).read_text())}
    extraction = {doi: [record.model_dump(by_alias=True) for record in rows]
                  for doi, rows in experiments(LABELLED).items()}

    rescues = [(row.doi, row.index) for row in unpaired.itertuples() if row.judge == "correct"]
    everything = [(row.doi, row.index) for row in unpaired.itertuples()]
    policies = [("as curated", []),
                ("+ judge-vouched", rescues),
                ("+ every unmatched", everything)]

    rows = []
    for name, additions in policies:
        reference = reference_with(base, extraction, additions)
        result, _ = evaluate(reference, experiments(LABELLED), ACCEPT, CATALYST, TOLERANCE)
        rows.append({
            "answer key": name,
            "experiments": sum(len(v) for v in reference.values()),
            "added": len(additions),
            "precision": result["precision"],
            "recall": result["recall"],
            "f1": result["f1"],
        })
    show("extraction score as the answer key grows", pd.DataFrame(rows).set_index("answer key"))

    human = golden()[["doi", "index", "human"]]
    before = human.merge(verdicts_with(reference_with(base, extraction, [])), on=["doi", "index"])
    generator = np.random.default_rng(0)

    rows = []
    for name, additions in policies[1:]:
        after = before.merge(verdicts_with(reference_with(base, extraction, additions)),
                             on=["doi", "index"], suffixes=("_before", "_after"))
        changed = after[after.m_before != after.m_after]

        # bootstrap the kappa shift; a resample with only one class in any column has no kappa
        shifts = []
        for _ in range(RESAMPLES):
            sample = after.iloc[generator.integers(0, len(after), len(after))]
            if min(sample.human.nunique(), sample.m_before.nunique(),
                   sample.m_after.nunique()) < 2:
                continue
            shifts.append(cohen_kappa_score(sample.m_after, sample.human)
                          - cohen_kappa_score(sample.m_before, sample.human))
        low, high = np.percentile(shifts, [2.5, 97.5])

        rows.append({
            "policy": name,
            "labels changed": len(changed),
            "toward chemists": (changed.m_after == changed.human).sum(),
            "kappa before": cohen_kappa_score(after.m_before, after.human),
            "kappa after": cohen_kappa_score(after.m_after, after.human),
            "95% low": low,
            "95% high": high,
        })
    show("effect on the labelled records", pd.DataFrame(rows).set_index("policy"))


if __name__ == "__main__":
    main()
