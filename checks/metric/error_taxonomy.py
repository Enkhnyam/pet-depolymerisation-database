"""What the metric did to each record, crossed with what the judge said.

A MISMATCH is a pair that was matched and then rejected, so it counts as both a false positive
and a false negative -- which is why reported FP and FN exceed these counts.
"""
from _setup import *

labels = scored()
show("the metric's verdict on every record", labels.verdict.value_counts(), fmt="{:.0f}")

rejected = labels.query("verdict == 'MISMATCH'")
show("rejected matches", {"total": len(rejected),
                          "on the catalyst name": (rejected.catalyst_match == False).sum()},
     fmt="{:.0f}")

both = labels.merge(judged(), on=["doi", "index"])
show("judge against metric situation", pd.crosstab(both.situation, both.judge), fmt="{:.0f}")
