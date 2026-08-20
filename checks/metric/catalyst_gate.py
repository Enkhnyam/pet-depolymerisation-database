"""Why the catalyst similarity requirement is 0.60: sweep it against the human labels."""
from sklearn.metrics import cohen_kappa_score
from _setup import *

labelled = golden()[["doi", "index", "human", "judge"]]
rows = {}
for requirement in [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0]:
    verdicts = scored(run=LABELLED, catalyst=requirement)[["doi", "index", "metric"]]
    merged = labelled.merge(verdicts, on=["doi", "index"])
    rows[requirement] = {"agreement": (merged.human == merged.metric).mean(),
                         "kappa": cohen_kappa_score(merged.human, merged.metric),
                         "flagged": (merged.metric == "incorrect").sum()}

frame = pd.DataFrame(rows).T
frame.index.name = "similarity required"
show("metric against the chemists, by catalyst gate", frame, fmt="{:.2f}")
print(f"\nthe judge on the same records: kappa "
      f"{cohen_kappa_score(labelled.human, labelled.judge):+.2f}")
