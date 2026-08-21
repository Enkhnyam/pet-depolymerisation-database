"""Does showing the model more worked examples help?

Each n_shots value is run several times, because run-to-run variance on this task is large enough
to swamp a small effect.

Reported as two questions rather than a ranking. Does having any example beat having none? And do
the settings that have examples differ from each other? Naming whichever mean came out highest
and testing it against the rest would be the winner's curse: with six noisy means, one is highest
by luck, and testing the winner it produced against the others is circular.
"""
import glob
from pathlib import Path

import pandas as pd
from itertools import combinations

from scipy.stats import f_oneway, ttest_ind

from _setup import ACCEPT, CATALYST, CURATED, RUNS_DIR, TOLERANCE, show, sources, totals

FOLDER = "shots_luna"


def compute() -> pd.DataFrame | None:
    """F1 per number of worked examples, or None if the sweep has not run."""
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / FOLDER / "*/run_meta.json"))):
        run_dir = Path(path).parent
        shots = int(run_dir.name.split("_n")[1].split("_r")[0])   # shots_luna_n{N}_r{R}
        rows.append({"n_shots": shots, "run": run_dir.name, "f1": totals(run=run_dir)["f1"]})
    if not rows:
        return None
    return pd.DataFrame(rows)


def main() -> None:
    sources(answer_key=CURATED, runs=RUNS_DIR / FOLDER)

    frame = compute()
    if frame is None:
        print(f"\nno runs yet under artifacts/runs/{FOLDER}")
        print("  scripts/run/ablation_shots.sh")
        return

    summary = frame.groupby("n_shots").f1.agg(["mean", "std", "count"])
    show("F1 by number of worked examples", summary)

    none = frame.query("n_shots == 0").f1
    some = frame.query("n_shots > 0").f1
    if len(none) and len(some):
        print(f"\nany example against none: {some.mean() - none.mean():+.3f}, "
              f"p = {ttest_ind(some, none).pvalue:.4f}")

    groups = [g.f1.values for n, g in frame.groupby("n_shots") if n > 0]
    if len(groups) > 1:
        print(f"do the settings with examples differ from each other? "
              f"one-way ANOVA p = {f_oneway(*groups).pvalue:.3f}")

    show("every pair (p)", pd.DataFrame(
        [{"a": a, "b": b, "p": ttest_ind(frame.query("n_shots == @a").f1,
                                         frame.query("n_shots == @b").f1).pvalue}
         for a, b in combinations(sorted(summary.index), 2)]).set_index(["a", "b"]),
        fmt="{:.3f}")


if __name__ == "__main__":
    main()
