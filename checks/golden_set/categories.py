import numpy as np
from sklearn.metrics import cohen_kappa_score

from _setup import *

labels = scored()
records = labels[labels.extracted_index.notna()].copy()
records["index"] = records.extracted_index.astype(int)
records["metric"] = records.verdict.map({"TP": "correct"}).fillna("incorrect")
records["situation"] = records.reason.fillna("matched").map(
    lambda r: "no matching curated experiment" if "unmatched extracted" in str(r)
    else "matched, but the catalyst names differ" if "catalyst mismatch" in str(r)
    else "matched a curated experiment")

both = records.merge(judged(), on=["doi", "index"])
both["judge"] = both.judge.where(both.judge == "correct", "incorrect")

groups = both.groupby(["situation", "metric", "judge"]).size().rename("records").reset_index()
print("every extracted record, by its situation and the two verdicts:")
print(groups.to_string(index=False))
print(f"\ntotal {groups.records.sum()} records, the two graders agreeing on "
      f"{(both.judge == both.metric).sum()} of them "
      f"({(both.judge == both.metric).mean():.0%})")

paired = both[both.situation != "no matching curated experiment"]
unpaired = both[both.situation == "no matching curated experiment"]
print(f"\nwith a curated counterpart   {len(paired):3d}   graders agree "
      f"{(paired.judge == paired.metric).sum():3d} ({(paired.judge == paired.metric).mean():.1%})")
print(f"without a curated counterpart {len(unpaired):3d}   the metric rejects all of them; "
      f"the judge accepts {(unpaired.judge == 'correct').sum()}")

base = {p["doi"]: p for p in json.loads(data_path(curated_table).read_text())}
extraction = {}
for path in glob.glob(str(RUNS_DIR / extraction_run / "extractions/*.json")):
    paper = json.loads(Path(path).read_text())
    extraction[paper["doi"]] = paper["records"]

def score_with(additions):
    reference = {}
    for doi, paper in base.items():
        rows = [entry["experiment_data"] for entry in paper["extracted_experiments"]]
        rows += [extraction[doi][i] for d, i in additions if d == doi]
        reference[doi] = [Experiment.model_validate(r) for r in rows]
    size = sum(len(v) for v in reference.values())
    result, _ = evaluate(reference, as_experiments(extraction_run),
                         accept_threshold, catalyst_threshold, numeric_tolerance)
    return size, result

rescues = [(r.doi, r.index) for r in unpaired[unpaired.judge == "correct"].itertuples()]
everything = [(r.doi, r.index) for r in records.itertuples()
              if r.situation == "no matching curated experiment"]

print("\nwhat happens to the extraction score as records are added to the curated table:")
rows = []
for name, additions in [("as curated", []),
                        ("+ records the judge vouches for", rescues),
                        ("+ every unmatched record", everything)]:
    size, result = score_with(additions)
    rows.append({"curated table": name, "experiments": size, "added": len(additions),
                 "precision": result["precision"], "recall": result["recall"], "f1": result["f1"]})
print(pd.DataFrame(rows).to_string(index=False, float_format="{:.3f}".format))

labelled = golden()[["doi", "extracted_index", "human"]]

def metric_verdicts(additions):
    reference = {}
    for doi, paper in base.items():
        rows = [entry["experiment_data"] for entry in paper["extracted_experiments"]]
        rows += [extraction[doi][i] for d, i in additions if d == doi]
        reference[doi] = [Experiment.model_validate(r) for r in rows]
    _, rows = evaluate(reference, as_experiments(extraction_run),
                       accept_threshold, catalyst_threshold, numeric_tolerance)
    out = pd.DataFrame(rows)
    out = out[out.extracted_index.notna()].copy()
    out["m"] = out.verdict.map({"TP": "correct"}).fillna("incorrect")
    return out[["doi", "extracted_index", "m"]]

before = labelled.merge(metric_verdicts([]), on=["doi", "extracted_index"])
generator = np.random.default_rng(0)

print("\neffect on the labelled records, where the graders are actually compared:")
for name, additions in [("+ records the judge vouches for", rescues),
                        ("+ every unmatched record", everything)]:
    after = before.merge(metric_verdicts(additions), on=["doi", "extracted_index"],
                         suffixes=("_before", "_after"))
    changed = after[after.m_before != after.m_after]
    agreeing = (changed.m_after == changed.human).sum()

    shifts = []
    for _ in range(10000):
        sample = after.iloc[generator.integers(0, len(after), len(after))]
        if min(sample.human.nunique(), sample.m_before.nunique(), sample.m_after.nunique()) < 2:
            continue
        shifts.append(cohen_kappa_score(sample.m_after, sample.human)
                      - cohen_kappa_score(sample.m_before, sample.human))
    low, high = np.percentile(shifts, [2.5, 97.5])

    print(f"  {name}")
    print(f"    {len(changed)} of {len(after)} labelled records change verdict "
          f"({agreeing} toward the chemists, {len(changed) - agreeing} away)")
    print(f"    metric kappa {cohen_kappa_score(after.m_before, after.human):.2f} -> "
          f"{cohen_kappa_score(after.m_after, after.human):.2f}   "
          f"change {np.mean(shifts):+.3f}, 95% interval [{low:+.3f}, {high:+.3f}]")

print("\nAdding records the extraction already produced lifts the extraction score without the")
print("extraction changing. The judge-vouched additions move the labelled comparison by one record,")
print("which is not distinguishable from zero; those records were excluded from the labelled set, so")
print("it cannot measure them. Adding every unmatched record puts experiments the chemists rejected")
print("into the answer key, and that degradation is distinguishable from chance.")
