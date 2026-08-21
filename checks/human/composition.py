"""What is in the human-labelled set, how it was drawn, and why it no longer does its job.

The set was drawn on disagreements, which is the right design: a record the two graders disagree
about becomes an informative pair the moment a human decides it. Twenty-eight of the 48 were
disagreements when they were chosen.

Then the judge rubric was rewritten, and the judge changed its mind on twenty records -- nineteen
of them toward the metric. The disagreements the set was built on largely stopped being
disagreements, and only four survive. The labels are still valid; the sampling design is not,
because the thing it sampled on moved afterwards.

The lesson for a new round: fix the judge first, then draw the sample, and do not touch the judge
again. Iterating the grader after fixing the sample spends the sample.

Records where the two graders disagreed on the catalyst were kept whole, since those decide
which grader is right. Records with no curated counterpart were sampled rather than taken whole,
there being too many. Records both graders accepted form a control group, where a grader
agreeing only by luck would show up.

The dev/test split was fixed before the final rubric was written, so the test half is a clean
estimate of anything tuned while looking at the other half.
"""
import hashlib
import json

import pandas as pd

from _setup import CURATED, LABELLED, LABELS, golden, scored, show, sources


def main() -> None:
    sources(labels=LABELS, labelled_run=LABELLED, answer_key=CURATED)
    labelled = golden()

    show("set", {
        "records": len(labelled),
        "papers": labelled.doi.nunique(),
        "labels revised after criteria settled": labelled.correction.notna().sum(),
    }, fmt="{:.0f}")

    checksum = hashlib.sha256(LABELS.read_bytes()).hexdigest()
    print(f"\nsource run  {LABELLED.name}\nsha256      {checksum}")

    show("labels by split", pd.crosstab(labelled.split, labelled.human), fmt="{:.0f}")
    show("how the set was drawn", pd.crosstab(labelled.situation, labelled.human), fmt="{:.0f}")

    # the file keeps the verdicts as they stood when the set was chosen, which is what makes the
    # comparison below possible at all
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


if __name__ == "__main__":
    main()
