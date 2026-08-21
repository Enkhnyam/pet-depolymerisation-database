"""The 48 records two chemists adjudicated: what is in the set, and what it says.

The set was drawn on disagreements, which is the efficient design. The judge rubric was then
rewritten and the judge changed its mind on twenty of the 48, nineteen of them toward the metric,
so only four disagreements survive. The labels are still valid; the sampling design is not,
because the quantity it sampled on moved afterwards.

Both graders are scored against the chemists here. Which of them is better is a separate question
that this set cannot answer -- see human/significance.py.
"""
import hashlib
import json

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from _setup import CURATED, LABELLED, LABELS, golden, scored, show, sources

GRADERS = ["judge", "metric"]


def scorecard() -> pd.DataFrame:
    """Each grader against the chemists: agreement, and the flagging task."""
    labelled = golden()
    rows = {}
    for grader in GRADERS:
        precision, recall, f1, _ = precision_recall_fscore_support(
            labelled.human, labelled[grader], average="binary", pos_label="incorrect")
        rows[grader] = {"agreement": (labelled.human == labelled[grader]).mean(),
                        "precision": precision, "recall": recall, "f1": f1,
                        "flagged": int((labelled[grader] == "incorrect").sum())}
    return pd.DataFrame(rows).T


def drift() -> dict:
    """How many disagreements the set held when it was drawn, and how many survive."""
    stored = pd.DataFrame(json.loads(LABELS.read_text())).rename(
        columns={"extracted_index": "index"})
    merged = stored.merge(scored(run=LABELLED)[["doi", "index", "metric"]],
                          on=["doi", "index"], suffixes=("_stored", "_now"))
    moved = merged[merged.judge != merged.judge_v4]
    return {"disagreements when the set was drawn": int((stored.metric != stored.judge).sum()),
            "disagreements now": int((merged.metric_now != merged.judge_v4).sum()),
            "records where the judge changed its mind": len(moved),
            "of those, moved toward the metric": int((moved.judge_v4 == moved.metric_now).sum())}


def main() -> None:
    sources(labels=LABELS, labelled_run=LABELLED, answer_key=CURATED)
    labelled = golden()

    show("the set", {
        "records": len(labelled),
        "papers": labelled.doi.nunique(),
        "rejected by the chemists": int((labelled.human == "incorrect").sum()),
        "labels revised after criteria settled": int(labelled.correction.notna().sum()),
    }, fmt="{:.0f}")
    print(f"\nsource run  {LABELLED.name}"
          f"\nsha256      {hashlib.sha256(LABELS.read_bytes()).hexdigest()}")
    show("labels by split", pd.crosstab(labelled.split, labelled.human), fmt="{:.0f}")
    show("how the set was drawn", pd.crosstab(labelled.situation, labelled.human), fmt="{:.0f}")

    # why the design no longer holds: the file keeps the verdicts as they stood at selection
    stored = pd.DataFrame(json.loads(LABELS.read_text())).rename(
        columns={"extracted_index": "index"})
    merged = stored.merge(scored(run=LABELLED)[["doi", "index", "metric"]],
                          on=["doi", "index"], suffixes=("_stored", "_now"))
    moved = merged[merged.judge != merged.judge_v4]
    show("the sample was drawn on disagreements, and then they went away", {
        "disagreements when the set was drawn": int((stored.metric != stored.judge).sum()),
        "disagreements now": int((merged.metric_now != merged.judge_v4).sum()),
        "records where the judge changed its mind": len(moved),
        "  of those, moved toward the metric": int((moved.judge_v4 == moved.metric_now).sum()),
    }, fmt="{:.0f}")
    show("what the rubric rewrite did", {
        "agreement with the metric, old rubric": (merged.metric_now == merged.judge).mean(),
        "agreement with the metric, current": (merged.metric_now == merged.judge_v4).mean(),
        "agreement with the chemists, old rubric": (merged.judge == merged.human).mean(),
        "agreement with the chemists, current": (merged.judge_v4 == merged.human).mean(),
    }, fmt="{:.2f}")

    rows = {}
    for grader in GRADERS:
        precision, recall, f1, _ = precision_recall_fscore_support(
            labelled.human, labelled[grader], average="binary", pos_label="incorrect")
        rows[grader] = {"agreement": (labelled.human == labelled[grader]).mean(),
                        "precision": precision, "recall": recall, "f1": f1,
                        "flagged": int((labelled[grader] == "incorrect").sum())}
    show("each grader against the chemists", pd.DataFrame(rows).T, fmt="{:.2f}")

    halves = {"all": labelled, "dev": labelled.query("split == 'dev'"),
              "test (held out)": labelled.query("split == 'test'")}
    show("agreement by split", pd.DataFrame({
        name: {g: (part.human == part[g]).mean() for g in GRADERS}
        for name, part in halves.items()}), fmt="{:.0%}")

    for grader in GRADERS:
        show(f"kind of record {grader} gets wrong",
             labelled[labelled[grader] != labelled.human].situation.value_counts(), fmt="{:.0f}")


if __name__ == "__main__":
    main()
