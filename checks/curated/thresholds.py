"""Answers 'did you tune the thresholds until the number looked good?'.

If the reported settings sit on a plateau rather than a peak, they were not cherry-picked.
"""
import pandas as pd

from _setup import (ACCEPT, CATALYST, CURATED, EXTRACTION, TOLERANCE, show, sources, totals)


def sweep(setting: str, values: list[float]) -> pd.DataFrame:
    """Re-score the run once per value of one threshold, holding the other two fixed."""
    results = {value: totals(**{setting: value}) for value in values}

    frame = pd.DataFrame(results).T
    frame.index.name = setting
    return frame[["f1", "precision", "recall"]]


def compute() -> dict:
    """One frame per threshold, scored across a range of settings."""
    return {
        "accept": sweep("accept", [0.2, 0.25, 0.3, 0.35, 0.4, 0.5]),
        "catalyst": sweep("catalyst", [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]),
        "tolerance": sweep("tolerance", [0.05, 0.1, 0.2, 0.3, 0.5]),
    }


def main() -> None:
    sources(answer_key=CURATED, extraction=EXTRACTION)
    result = compute()
    show(f"acceptance cutoff (using {ACCEPT:.2f})", result["accept"])
    show(f"catalyst similarity (using {CATALYST:.2f})", result["catalyst"])
    show(f"numeric tolerance (using {TOLERANCE:.2f})", result["tolerance"])


if __name__ == "__main__":
    main()
