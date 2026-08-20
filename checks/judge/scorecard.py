from sklearn.metrics import precision_recall_fscore_support
from _setup import *

labelled = golden()
rejected_by_chemists = (labelled.human == "incorrect").sum()

scorecard = {}
for grader in ["judge_v4", "metric"]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        labelled.human, labelled[grader], average="binary", pos_label="incorrect")
    scorecard[grader] = {"agreement": (labelled.human == labelled[grader]).mean(),
                         "precision": precision,
                         "recall": recall,
                         "f1": f1,
                         "records flagged": (labelled[grader] == "incorrect").sum()}

print("the chemists rejected", rejected_by_chemists, "of", len(labelled), "records")
print()
print(pd.DataFrame(scorecard).T.to_string(float_format="{:.2f}".format))
print()
print("precision: of what a grader flagged, how much the chemists also rejected")
print("recall:    of what the chemists rejected, how much the grader caught")
