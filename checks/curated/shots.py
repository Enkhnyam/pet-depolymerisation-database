"""Does showing the model more worked examples help?

Each n_shots value is run several times, because run-to-run variance on this task is large enough
to swamp a small effect. The t-test compares the best setting against each other one; a gap that
does not clear the noise is reported as such rather than as a winner.
"""
import glob
from pathlib import Path

import pandas as pd
from scipy.stats import ttest_ind

from _setup import ACCEPT, CATALYST, CURATED, RUNS_DIR, TOLERANCE, show, sources, totals

FOLDER = "shots_luna"


def main() -> None:
    sources(answer_key=CURATED, runs=RUNS_DIR / FOLDER)

    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / FOLDER / "*/run_meta.json"))):
        run_dir = Path(path).parent
        name = run_dir.name                       # shots_luna_n{N}_r{R}
        shots = int(name.split("_n")[1].split("_r")[0])
        rows.append({"n_shots": shots, "run": name, "f1": totals(run=run_dir)["f1"]})

    if not rows:
        print(f"\nno runs yet under artifacts/runs/{FOLDER}")
        print("  scripts/ablation_shots.sh")
        return

    frame = pd.DataFrame(rows)
    summary = frame.groupby("n_shots").f1.agg(["mean", "std", "count"])
    show("F1 by number of worked examples", summary)

    best = summary["mean"].idxmax()
    best_runs = frame.query("n_shots == @best").f1
    comparisons = {}
    for shots in sorted(summary.index):
        if shots != best:
            comparisons[shots] = ttest_ind(best_runs, frame.query("n_shots == @shots").f1).pvalue

    print(f"\nbest setting: {best} example(s), F1 {summary['mean'][best]:.3f}")
    show("best against every other setting (p)", pd.Series(comparisons), fmt="{:.4f}")
    if comparisons:
        print(f"\nlargest p among the others: {max(comparisons.values()):.4f}")


if __name__ == "__main__":
    main()
