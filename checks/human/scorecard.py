"""Each grader against the two chemists, on the 48 adjudicated records.

Reported as agreement and as a detection task: of what a grader flagged, how much the chemists
also rejected, and of what they rejected, how much it caught. A grader that flags everything gets
perfect recall and useless precision, which this makes visible.

The test half was fixed before the final rubric was written, so it is genuinely held out.
"""
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from _setup import golden, show

GRADERS = ["judge", "metric"]


def main() -> None:
    labelled = golden()
    rejected = (labelled.human == "incorrect").sum()
    print(f"\nthe chemists rejected {rejected} of {len(labelled)} records")

    rows = {}
    for grader in GRADERS:
        precision, recall, f1, _ = precision_recall_fscore_support(
            labelled.human, labelled[grader], average="binary", pos_label="incorrect")
        rows[grader] = {
            "agreement": (labelled.human == labelled[grader]).mean(),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "flagged": (labelled[grader] == "incorrect").sum(),
        }
    show("against the chemists", pd.DataFrame(rows).T, fmt="{:.2f}")

    halves = {"all": labelled,
              "dev": labelled.query("split == 'dev'"),
              "test (held out)": labelled.query("split == 'test'")}
    by_split = pd.DataFrame({
        name: {grader: (part.human == part[grader]).mean() for grader in GRADERS}
        for name, part in halves.items()})
    show("agreement by split", by_split, fmt="{:.0%}")


if __name__ == "__main__":
    main()
