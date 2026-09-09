"""What happens to the extraction's score as records are added to the answer key.

Adding records the extraction itself produced lifts its own score without the extraction
changing. That is the circularity we refused to exploit, and it is measurable twice over: on the
extraction's F1, and on how well the metric still tracks the chemists afterwards. The bootstrap
says whether the second change is distinguishable from zero.
"""
import json

import numpy as np
import pandas as pd

from _setup import (ACCEPT, CATALYST, CURATED, JUDGE, LABELLED, LABELS, TOLERANCE, experiments,
                    golden, judged, scored, show, sources)
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


def compute() -> pd.DataFrame:
    """The growth rows, so the paper's Table 4 and its own paragraph read one number.

    They did not: the text quoted F1 rising 0.727 to 0.835 against a table saying 0.802 to 0.878,
    because both were typed at different times.
    """
    both = scored(run=LABELLED).merge(judged(), on=["doi", "index"])
    unpaired = both.query("situation == @UNMATCHED")
    base = {paper["doi"]: paper for paper in json.loads(data_path(CURATED).read_text())}
    extraction = {doi: [record.model_dump(by_alias=True) for record in rows]
                  for doi, rows in experiments(LABELLED).items()}
    policies = [("as curated", []),
                ("+ judge-vouched",
                 [(r.doi, r.index) for r in unpaired.itertuples() if r.judge == "correct"]),
                ("+ every unmatched", [(r.doi, r.index) for r in unpaired.itertuples()])]
    rows = []
    for name, additions in policies:
        reference = reference_with(base, extraction, additions)
        result, _ = evaluate(reference, experiments(LABELLED), ACCEPT, CATALYST, TOLERANCE)
        rows.append({"answer key": name,
                     "experiments": sum(len(v) for v in reference.values()),
                     "added": len(additions),
                     "precision": result["precision"], "recall": result["recall"],
                     "f1": result["f1"]})
    return pd.DataFrame(rows).set_index("answer key")


def tracking() -> pd.DataFrame:
    """What growing the answer key does to the grader, not just to the score.

    This was computed inside main() and printed. The SI quotes all six of its numbers -- the
    agreement before and after, the change, its bootstrap interval and how many verdicts moved
    -- and with the computation buried in main() the only way to quote them was to type them,
    which is how the manuscript came to carry four numbers no check could move.
    """
    both = scored(run=LABELLED).merge(judged(), on=["doi", "index"])
    unpaired = both.query("situation == @UNMATCHED")
    base = {paper["doi"]: paper for paper in json.loads(data_path(CURATED).read_text())}
    extraction = {doi: [record.model_dump(by_alias=True) for record in rows]
                  for doi, rows in experiments(LABELLED).items()}
    rescues = [(row.doi, row.index) for row in unpaired.itertuples() if row.judge == "correct"]
    everything = [(row.doi, row.index) for row in unpaired.itertuples()]

    human = golden()[["doi", "index", "human"]]
    before = human.merge(verdicts_with(reference_with(base, extraction, [])),
                         on=["doi", "index"])
    generator = np.random.default_rng(0)

    rows = []
    for name, additions in (("+ judge-vouched", rescues), ("+ every unmatched", everything)):
        after = before.merge(verdicts_with(reference_with(base, extraction, additions)),
                             on=["doi", "index"], suffixes=("_before", "_after"))
        changed = after[after.m_before != after.m_after]

        shifts = []
        for _ in range(RESAMPLES):
            sample = after.iloc[generator.integers(0, len(after), len(after))]
            shifts.append((sample.m_after == sample.human).mean()
                          - (sample.m_before == sample.human).mean())
        low, high = np.percentile(shifts, [2.5, 97.5])

        rows.append({"policy": name,
                     "labels changed": len(changed),
                     "toward the chemists": int((changed.m_after == changed.human).sum()),
                     "agreement before": (after.m_before == after.human).mean(),
                     "agreement after": (after.m_after == after.human).mean(),
                     "95% low": low, "95% high": high})
    return pd.DataFrame(rows).set_index("policy")


def main() -> None:
    sources(labels=LABELS, labelled_run=LABELLED, answer_key=CURATED, judge=JUDGE)
    both = scored(run=LABELLED).merge(judged(), on=["doi", "index"])
    unpaired = both.query("situation == @UNMATCHED")

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
        rows.append({"answer key": name,
                     "experiments": sum(len(v) for v in reference.values()),
                     "added": len(additions),
                     "precision": result["precision"],
                     "recall": result["recall"],
                     "f1": result["f1"]})
    show("the extraction's own score as the answer key grows", compute())

    show("how well the metric still tracks the chemists afterwards", tracking())


if __name__ == "__main__":
    main()
