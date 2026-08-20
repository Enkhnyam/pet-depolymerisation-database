"""What is in the human-labelled set, and how it was selected.

Records where the graders disagreed on the catalyst were kept whole; records with no curated
counterpart were sampled, there being too many; records both graders accepted form a control
group, where a grader agreeing only by luck would show up. The dev/test split was fixed before
the final rubric was written, so the test half is a clean estimate of anything tuned on dev.
"""
import hashlib
from _setup import *

labelled = golden()
show("set", {"records": len(labelled),
             "papers": labelled.doi.nunique(),
             "labels revised after criteria settled": labelled.correction.notna().sum()},
     fmt="{:.0f}")
print(f"\nsource run  {LABELLED.name}\nsha256      {hashlib.sha256(LABELS.read_bytes()).hexdigest()}")
show("labels by split", pd.crosstab(labelled.split, labelled.human), fmt="{:.0f}")
show("how the set was drawn", pd.crosstab(labelled.situation, labelled.human), fmt="{:.0f}")
