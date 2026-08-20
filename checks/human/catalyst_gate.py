"""Why the catalyst similarity requirement is 0.60.

Sweeps the requirement and scores each setting against the human labels. Demanding identical
names, or accepting any name at all, are both worse than the middle.
"""
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from _setup import LABELLED, golden, scored, show

REQUIREMENTS = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0]


def main() -> None:
    labelled = golden()[["doi", "index", "human", "judge"]]

    rows = {}
    for requirement in REQUIREMENTS:
        verdicts = scored(run=LABELLED, catalyst=requirement)[["doi", "index", "metric"]]
        merged = labelled.merge(verdicts, on=["doi", "index"])
        rows[requirement] = {
            "agreement": (merged.human == merged.metric).mean(),
            "kappa": cohen_kappa_score(merged.human, merged.metric),
            "flagged": (merged.metric == "incorrect").sum(),
        }

    frame = pd.DataFrame(rows).T
    frame.index.name = "similarity required"
    show("metric against the chemists, by catalyst gate", frame, fmt="{:.2f}")

    judge_kappa = cohen_kappa_score(labelled.human, labelled.judge)
    print(f"\nthe judge on the same records: kappa {judge_kappa:+.2f}")


if __name__ == "__main__":
    main()
