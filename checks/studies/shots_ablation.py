from scipy.stats import ttest_ind

from _setup import *

models = {"gpt-oss-120b": "shots_oss", "mistral-small": "shots_mistral"}

for model_name, folder in models.items():
    results = scores_by_run(folder)
    if results.empty:
        print(model_name + ": not run yet")
        print()
        continue

    by_shots = results.groupby("n_shots").f1.agg(["mean", "std", "count"])
    print(model_name)
    print(by_shots.to_string(float_format="{:.3f}".format))

    best = by_shots["mean"].idxmax()
    best_runs = results[results.n_shots == best].f1
    comparisons = {}
    for shots in sorted(by_shots.index):
        if shots == best:
            continue
        other = results[results.n_shots == shots].f1
        comparisons[shots] = ttest_ind(best_runs, other).pvalue

    print(f"\nbest setting: {best} example(s), F1 {by_shots['mean'][best]:.3f}")
    print("best against every other setting:")
    for shots, p in comparisons.items():
        print(f"  vs {shots}: p = {p:.4f}")
    worst_case = max(p for shots, p in comparisons.items() if shots != 0)
    print(f"largest p among settings that produced output: {worst_case:.4f}")
    print()
