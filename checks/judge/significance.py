"""Is the judge significantly better than the metric?

Only records where exactly one grader matched the chemists carry information. With as few as
we have, no outcome could reach significance however it fell -- so the finding is that the set
is too small to settle the question, not that the graders are equally good.
"""
from scipy.stats import binomtest
from _setup import *

labelled = golden()
rows = {}
for name, part in [("all", labelled), ("test (held out)", labelled.query("split == 'test'"))]:
    judge_only = ((part.judge == part.human) & (part.metric != part.human)).sum()
    metric_only = ((part.metric == part.human) & (part.judge != part.human)).sum()
    rows[name] = {"records": len(part), "only judge right": judge_only,
                  "only metric right": metric_only,
                  "p": binomtest(judge_only, judge_only + metric_only).pvalue}
show("McNemar", pd.DataFrame(rows).T, fmt="{:.3f}")

informative = int(rows["all"]["only judge right"] + rows["all"]["only metric right"])
best = binomtest(informative, informative).pvalue
print(f"\ninformative records {informative} of {len(labelled)}; "
      f"smallest p reachable {best:.3f}")

needed = pd.DataFrame([{"informative records": n, "p at the observed 3:1 split":
                        binomtest(round(n * .75), n).pvalue} for n in [4, 8, 12, 16, 20]])
show("what would be needed", needed.set_index("informative records"))
