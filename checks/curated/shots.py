"""Does showing the model more worked examples help?

Each n_shots value is run several times, because run-to-run variance on this task is large enough
to swamp a small effect.

Reported as two questions rather than a ranking. Does having any example beat having none? And do
the settings that have examples differ from each other? Naming whichever mean came out highest
and testing it against the rest would be the winner's curse: with six noisy means, one is highest
by luck, and testing the winner it produced against the others is circular.

The power table at the end is the honest part. With three runs an arm and the variance this task
actually shows, only large differences are detectable, so "no difference between one example and
four" means "we could not have seen one", not "there is none".
"""
import glob
from pathlib import Path

import pandas as pd
from itertools import combinations

import numpy as np

from scipy.stats import f_oneway, ttest_ind

from _setup import ACCEPT, CATALYST, CURATED, RUNS_DIR, TOLERANCE, show, sources, totals

FOLDER = "shots_luna"


def summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean and spread per arm -- what main() prints and what Figure 4 draws, computed once."""
    return frame.groupby("n_shots").f1.agg(["mean", "std", "count"])


def contrast(frame: pd.DataFrame) -> dict:
    """The two comparisons the paper quotes, so the caption cannot hold a different number.

    They were printed only inside main(), which meant Figure 4 carried a hand-copied "+0.043,
    p=0.005" long after the answer key grew and moved them to +0.025, p=0.065.
    """
    none = frame.query("n_shots == 0").f1
    some = frame.query("n_shots > 0").f1
    groups = [group.f1.values for shots, group in frame.groupby("n_shots") if shots > 0]
    means = frame.groupby("n_shots").f1.mean()
    return {
        "delta": float(some.mean() - none.mean()) if len(none) and len(some) else float("nan"),
        "p": float(ttest_ind(some, none).pvalue) if len(none) and len(some) else float("nan"),
        "anova_p": float(f_oneway(*groups).pvalue) if len(groups) > 1 else float("nan"),
        "best": int(means.idxmax()) if len(means) else 0,
    }


def pairwise(frame: pd.DataFrame) -> pd.DataFrame:
    """Every pair of arms that include at least one example, with its p.

    The zero arm is a different question, answered by contrast(); mixing it in here is what
    made two parts of the project disagree about how many comparisons were run. main() printed
    all fifteen pairs over arms 0-5, while tools/paper_numbers.py computed ten over arms 1-5
    with its own local copy of the t-test -- and the paper's Bonferroni threshold, 0.05/10, came
    from the second. One definition, in the check that owns the ablation.
    """
    arms = [n for n in sorted(frame.n_shots.unique()) if n > 0]
    return pd.DataFrame(
        [{"a": a, "b": b, "p": float(ttest_ind(frame.query("n_shots == @a").f1,
                                               frame.query("n_shots == @b").f1).pvalue)}
         for a, b in combinations(arms, 2)]).set_index(["a", "b"])


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


def detectable(frame: pd.DataFrame) -> None:
    """What this design could have found, given the variance it actually shows."""
    groups = [g.f1.values for _, g in frame.groupby("n_shots")]
    pooled = np.sqrt(np.mean([np.var(v, ddof=1) for v in groups]))
    per_arm = int(np.median([len(v) for v in groups]))
    print(f"\npooled SD {pooled:.4f} across settings, {per_arm} runs an arm")

    generator = np.random.default_rng(0)
    rows = {}
    for effect in (0.01, 0.02, 0.03, 0.05, 0.08):
        row = {}
        for n in (per_arm, 5, 10, 20):
            a = generator.normal(0, pooled, (20000, n))
            b = generator.normal(effect, pooled, (20000, n))
            row[f"n={n}"] = (ttest_ind(a, b, axis=1).pvalue < 0.05).mean()
        rows[effect] = row
    table = pd.DataFrame(rows).T
    table.index.name = "true difference in F1"
    show("power to detect it, two arms, alpha 0.05", table, fmt="{:.2f}")


def main() -> None:
    sources(answer_key=CURATED, runs=RUNS_DIR / FOLDER)

    frame = compute()
    if frame is None:
        print(f"\nno runs yet under artifacts/runs/{FOLDER}")
        print("  scripts/run/ablation_shots.sh")
        return

    arms = summary(frame)
    show("F1 by number of worked examples", arms)

    found = contrast(frame)
    print(f"\nany example against none: {found['delta']:+.3f}, p = {found['p']:.4f}")
    print(f"do the settings with examples differ from each other? "
          f"one-way ANOVA p = {found['anova_p']:.3f}")

    detectable(frame)

    pairs = pairwise(frame)
    show("every pair of arms with at least one example (p)", pairs, fmt="{:.3f}")
    print(f"\n  {len(pairs)} comparisons, so Bonferroni asks for p < {0.05 / len(pairs):.3f}; "
          f"the smallest is {pairs.p.min():.2f}")


if __name__ == "__main__":
    main()
