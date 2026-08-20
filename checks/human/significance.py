"""Is the judge significantly better than the metric?

Only records where exactly one grader matched the chemists carry information; where both agree,
the record cannot separate them. With as few informative records as we have, no outcome could
reach significance however it fell -- so the finding is that the set is too small to settle the
question, not that the two graders are equally good.
"""
import pandas as pd
from scipy.stats import binomtest

from _setup import golden, show

OBSERVED_SPLIT = 0.75   # the rate at which informative records favour the judge


def main() -> None:
    labelled = golden()
    halves = {"all": labelled, "test (held out)": labelled.query("split == 'test'")}

    rows = {}
    for name, part in halves.items():
        judge_only = ((part.judge == part.human) & (part.metric != part.human)).sum()
        metric_only = ((part.metric == part.human) & (part.judge != part.human)).sum()
        rows[name] = {
            "records": len(part),
            "only judge right": judge_only,
            "only metric right": metric_only,
            "p": binomtest(judge_only, judge_only + metric_only).pvalue,
        }
    show("McNemar", pd.DataFrame(rows).T, fmt="{:.3f}")

    informative = int(rows["all"]["only judge right"] + rows["all"]["only metric right"])
    best = binomtest(informative, informative).pvalue
    print(f"\ninformative records {informative} of {len(labelled)}; "
          f"smallest p reachable {best:.3f}")

    needed = pd.DataFrame([
        {"informative records": count,
         "p at the observed 3:1 split": binomtest(round(count * OBSERVED_SPLIT), count).pvalue}
        for count in [4, 8, 12, 16, 20]
    ])
    show("what would be needed", needed.set_index("informative records"))


if __name__ == "__main__":
    main()
