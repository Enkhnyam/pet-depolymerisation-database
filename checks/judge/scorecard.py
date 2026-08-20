"""Each grader against the chemists, as a detection task: of what it flagged, how much the
chemists also rejected, and of what they rejected, how much it caught. A grader that flags
everything gets perfect recall and useless precision, which this makes visible.

The test split was fixed before the final rubric was written, so it is held out.
"""
from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support
from _setup import *

labelled = golden()
print(f"\nthe chemists rejected {(labelled.human == 'incorrect').sum()} of {len(labelled)} records")

rows = {}
for grader in ["judge", "metric"]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        labelled.human, labelled[grader], average="binary", pos_label="incorrect")
    rows[grader] = {"agreement": (labelled.human == labelled[grader]).mean(),
                    "kappa": cohen_kappa_score(labelled.human, labelled[grader]),
                    "precision": precision, "recall": recall, "f1": f1,
                    "flagged": (labelled[grader] == "incorrect").sum()}
show("against the chemists", pd.DataFrame(rows).T, fmt="{:.2f}")

splits = pd.DataFrame({
    split: {grader: (part.human == part[grader]).mean() for grader in ["judge", "metric"]}
    for split, part in [("all", labelled), ("dev", labelled.query("split == 'dev'")),
                        ("test (held out)", labelled.query("split == 'test'"))]})
show("agreement by split", splits, fmt="{:.0%}")
