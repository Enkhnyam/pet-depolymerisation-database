"""Why the catalyst similarity requirement is 0.60.

Sweeps the requirement and scores each setting against the human labels. Demanding identical
names, or accepting any name at all, are both worse than the middle.
"""
import pandas as pd

from _setup import CURATED, LABELLED, LABELS, golden, scored, show, sources

REQUIREMENTS = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0]


def main() -> None:
    sources(labels=LABELS, labelled_run=LABELLED, answer_key=CURATED)
    labelled = golden()[["doi", "index", "human", "judge"]]

    rows = {}
    for requirement in REQUIREMENTS:
        verdicts = scored(run=LABELLED, catalyst=requirement)[["doi", "index", "metric"]]
        merged = labelled.merge(verdicts, on=["doi", "index"])
        rows[requirement] = {
            "agreement with the chemists": (merged.human == merged.metric).mean(),
            "records flagged": (merged.metric == "incorrect").sum(),
        }

    frame = pd.DataFrame(rows).T
    frame.index.name = "similarity required"
    show("metric against the chemists, by catalyst gate", frame, fmt="{:.2f}")
    print(f"\n  the judge on the same records: "
          f"{(labelled.human == labelled.judge).mean():.2f} agreement")


if __name__ == "__main__":
    main()
