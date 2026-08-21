"""Does requiring the model to cite its source chunks change what it extracts?

Two arms differing in one flag: the OFF arm strips chunk ids from the worked examples and from
the response schema, so the model is never taught to cite. Everything else is held identical.

The question matters beyond provenance -- being asked to point at the sentence may change how
carefully the model reads it.
"""
import glob
from pathlib import Path

import pandas as pd
from scipy.stats import ttest_ind

from _setup import CURATED, RUNS_DIR, show, sources, totals

ARMS = {"citing sources": "src_luna_on", "not citing": "src_luna_off"}


def scores(folder: str) -> list:
    return [totals(run=Path(path).parent)["f1"]
            for path in sorted(glob.glob(str(RUNS_DIR / folder / "*/run_meta.json")))]


def compute() -> pd.DataFrame:
    """Mean F1 for each arm, with the t-test attached as frame metadata."""
    arms = {}
    for label, folder in ARMS.items():
        scores = [totals(run=Path(path).parent)["f1"]
                  for path in glob.glob(str(RUNS_DIR / folder / "*/run_meta.json"))]
        if scores:
            arms[label] = scores

    frame = pd.DataFrame({label: pd.Series(scores).agg(["mean", "std", "count"])
                          for label, scores in arms.items()}).T
    if len(arms) == 2:
        frame.attrs["p"] = ttest_ind(*arms.values()).pvalue
    return frame


def main() -> None:
    sources(answer_key=CURATED, on=RUNS_DIR / ARMS["citing sources"],
            off=RUNS_DIR / ARMS["not citing"])

    arms = {label: scores(folder) for label, folder in ARMS.items()}
    if not all(arms.values()):
        print("\nboth arms not run yet")
        print("  scripts/ablation_source.sh")
        return

    frame = pd.DataFrame({label: pd.Series(values) for label, values in arms.items()})
    show("F1 by arm", frame.agg(["mean", "std", "count"]).T)

    citing, not_citing = arms["citing sources"], arms["not citing"]
    difference = pd.Series(citing).mean() - pd.Series(not_citing).mean()
    print(f"\ndifference {difference:+.3f}   p = {ttest_ind(citing, not_citing).pvalue:.3f}")


if __name__ == "__main__":
    main()
