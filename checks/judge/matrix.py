"""The judge x extraction matrix -- the paper's headline table.

Agreement is between the two graders on the same records; no human labels are involved, which
is the point: this is the only number available on a corpus with no curated table.

Reported two ways. Over every record the metric marks the surplus wrong without looking at it,
because it can only pair as many records as the answer key holds. Over records it could
genuinely evaluate, the two graders are compared on equal terms.
"""
from _setup import *

def found(pattern, meta, key):
    out = {}
    for path in glob.glob(str(RUNS_DIR / pattern / "*" / meta)):
        run_dir = Path(path).parent
        out[key(run_dir.parent.name)] = run_dir
    return out

extractions = found("extract_*", "run_meta.json", lambda n: n.replace("extract_", ""))
judges = found("judge_*_on_*", "judge_meta.json",
               lambda n: tuple(n.replace("judge_", "").split("_on_")))

rows = []
for (judge_name, target), judge_dir in sorted(judges.items()):
    if target not in extractions:
        continue
    metric = scored(run=extractions[target])[["doi", "index", "metric", "situation"]]
    both = metric.merge(judged(run=judge_dir), on=["doi", "index"])
    evaluable = both.query("situation != 'no curated counterpart'")
    rows.append({"judge": judge_name, "extraction": target, "records": len(both),
                 "agreement": (both.metric == both.judge).mean(),
                 "evaluable": len(evaluable),
                 "agreement, evaluable": (evaluable.metric == evaluable.judge).mean()})

frame = pd.DataFrame(rows)
show("per cell", frame.set_index(["judge", "extraction"]))
show("agreement over every record",
     frame.pivot(index="judge", columns="extraction", values="agreement"))
show("agreement over records the metric could evaluate",
     frame.pivot(index="judge", columns="extraction", values="agreement, evaluable"))
