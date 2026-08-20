"""What happens to the extraction's score as records are added to the answer key.

Adding records the extraction itself produced lifts its own score without the extraction
changing -- the circularity argument for not growing the curated set from disagreements.
The bootstrap says whether the shift on the labelled records is distinguishable from zero.
"""
import numpy as np
from sklearn.metrics import cohen_kappa_score
from _setup import *

labels = scored(run=LABELLED)
both = labels.merge(judged(), on=["doi", "index"])
unpaired = both.query("situation == 'no curated counterpart'")
paired = both.query("situation != 'no curated counterpart'")

show("agreement between the two graders", {
    "records": len(both),
    "agree": (both.judge == both.metric).sum(),
    "with a curated counterpart": len(paired),
    "  of those, agree": (paired.judge == paired.metric).sum(),
    "without a counterpart": len(unpaired),
    "  of those, judge accepts": (unpaired.judge == "correct").sum()}, fmt="{:.0f}")

base = {p["doi"]: p for p in json.loads(data_path(CURATED).read_text())}
extraction = {d: [r.model_dump(by_alias=True) for r in rs]
              for d, rs in experiments(LABELLED).items()}

def reference_with(additions):
    out = {}
    for doi, paper in base.items():
        rows = [e["experiment_data"] for e in paper["extracted_experiments"]]
        rows += [extraction[doi][i] for d, i in additions if d == doi]
        out[doi] = [Experiment.model_validate(r) for r in rows]
    return out

def verdicts_with(additions):
    _, rows = evaluate(reference_with(additions), experiments(LABELLED),
                       ACCEPT, CATALYST, TOLERANCE)
    frame = pd.DataFrame(rows)
    frame = frame[frame.extracted_index.notna()].copy()
    frame["index"] = frame.extracted_index.astype(int)
    frame["m"] = frame.verdict.map({"TP": "correct"}).fillna("incorrect")
    return frame[["doi", "index", "m"]]

rescues = [(r.doi, r.index) for r in unpaired.itertuples() if r.judge == "correct"]
everything = [(r.doi, r.index) for r in unpaired.itertuples()]
policies = [("as curated", []), ("+ judge-vouched", rescues), ("+ every unmatched", everything)]

rows = []
for name, additions in policies:
    reference = reference_with(additions)
    result, _ = evaluate(reference, experiments(LABELLED), ACCEPT, CATALYST, TOLERANCE)
    rows.append({"answer key": name, "experiments": sum(len(v) for v in reference.values()),
                 "added": len(additions), "precision": result["precision"],
                 "recall": result["recall"], "f1": result["f1"]})
show("extraction score as the answer key grows", pd.DataFrame(rows).set_index("answer key"))

human = golden()[["doi", "index", "human"]]
before = human.merge(verdicts_with([]), on=["doi", "index"])
generator = np.random.default_rng(0)

rows = []
for name, additions in policies[1:]:
    after = before.merge(verdicts_with(additions), on=["doi", "index"], suffixes=("_before", "_after"))
    changed = after[after.m_before != after.m_after]
    shifts = []
    for _ in range(10000):
        sample = after.iloc[generator.integers(0, len(after), len(after))]
        if min(sample.human.nunique(), sample.m_before.nunique(), sample.m_after.nunique()) < 2:
            continue
        shifts.append(cohen_kappa_score(sample.m_after, sample.human)
                      - cohen_kappa_score(sample.m_before, sample.human))
    low, high = np.percentile(shifts, [2.5, 97.5])
    rows.append({"policy": name, "labels changed": len(changed),
                 "toward chemists": (changed.m_after == changed.human).sum(),
                 "kappa before": cohen_kappa_score(after.m_before, after.human),
                 "kappa after": cohen_kappa_score(after.m_after, after.human),
                 "95% low": low, "95% high": high})
show("effect on the labelled records", pd.DataFrame(rows).set_index("policy"))
