"""Can we say which grader is better? No -- and this is what it would take.

McNemar counts only records where exactly one grader matched the chemists; where both agree, the
record says nothing about which is better. Our 48 labelled records yield four such pairs, and with
four pairs the smallest reachable p is above 0.05 however they fall. The comparison was
unanswerable before the data was looked at.

A record the two graders already disagree on becomes an informative pair the moment a human
decides it, because one of them must be the one that matched. So a new round should label
disagreements, not a random sample -- which is what made the existing set so uninformative.
"""
import pandas as pd
from scipy.stats import binom, binomtest

from _setup import RUNS_DIR, golden, judged, scored, show

ALPHA = 0.05
POWER = 0.80
SHIPPED = ("oss", "luna")   # the judge and extraction the database actually uses


def power_at(n: int, rate: float) -> float:
    """Chance of reaching significance with n discordant pairs, if the judge is right `rate` of
    the time. Sums the probability of every outcome whose two-sided test would reject."""
    return sum(binom.pmf(k, n, rate)
               for k in range(n + 1) if binomtest(k, n).pvalue < ALPHA)


def main() -> None:
    labelled = golden()
    judge_only = ((labelled.judge == labelled.human) & (labelled.metric != labelled.human)).sum()
    metric_only = ((labelled.metric == labelled.human) & (labelled.judge != labelled.human)).sum()
    have = int(judge_only + metric_only)

    show("what the labelled set gives us", {
        "labelled records": len(labelled),
        "the graders agree on": int((labelled.judge == labelled.metric).sum()),
        "informative (exactly one right)": have,
        "  favouring the judge": int(judge_only),
        "  favouring the metric": int(metric_only),
    }, fmt="{:.0f}")
    print(f"\n  McNemar p = {binomtest(int(judge_only), have).pvalue:.3f}")
    print(f"  with {have} pairs the smallest p reachable is {binomtest(have, have).pvalue:.3f}, "
          f"so no outcome could reach {ALPHA}")

    judge_name, target = SHIPPED
    extraction = RUNS_DIR / f"extract_{target}/extract_{target}_n4_r1"
    verdicts = RUNS_DIR / f"judge_{judge_name}_on_{target}/judge_{judge_name}_on_{target}"
    both = scored(run=extraction).merge(judged(run=verdicts), on=["doi", "index"])
    disagree = both[both.metric != both.judge]
    evaluable = both.query("situation != 'no curated counterpart'")
    ev_disagree = evaluable[evaluable.metric != evaluable.judge]

    show(f"the pool for a new round, {judge_name} judging {target}", {
        "records": len(both),
        "the graders disagree on": len(disagree),
        "  of those, the metric could evaluate": len(ev_disagree),
    }, fmt="{:.0f}")

    rows = []
    for rate in [0.70, 0.75, 0.80, 0.90]:
        needed = next((n for n in range(4, 400) if power_at(n, rate) >= POWER), None)
        rows.append({"if the judge is right this often": rate,
                     f"pairs for {POWER:.0%} power": needed,
                     "pool available": len(disagree),
                     "pool, evaluable only": len(ev_disagree)})
    show(f"what a conclusive round would take, alpha {ALPHA}",
         pd.DataFrame(rows).set_index("if the judge is right this often"), fmt="{:.0f}")

    # The four pairs we hold came from a gpt-5.6-sol extraction judged by gpt-5.6-sol. Neither
    # half is what the database ships, so a round on the shipped pair starts from zero.
    print(f"\n  the {have} pairs we hold describe a different extraction and a different judge,")
    print(f"  so a round on {judge_name}/{target} starts at zero")


if __name__ == "__main__":
    main()
