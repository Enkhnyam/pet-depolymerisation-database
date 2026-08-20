"""Turn a judge's pass rate into an estimate of the metric's F1.

On a corpus with no curated table only the judge can run, so the projection needs a mapping from
what the judge reports to what the metric would have said. This fits that mapping on the 24 papers
where both graders can run, one point per paper per extraction model, and measures how far a
prediction lands from the truth by refitting with each paper held out.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from _setup import (RUNS_DIR, data_path, as_experiments, accept_threshold,
                    catalyst_threshold, numeric_tolerance)
from core.evaluation import evaluate
from core.schema import load_curated

REFERENCE = "curated_table_final.json"
JUDGE = "oss"          # highest agreement with the metric, and free to run at scale
MODELS = ["oss", "luna", "terra", "mistral"]


def per_paper(model, judge):
    """(paper, model) rows: what the judge reported, and what the metric measured."""
    ext = f"extract_{model}/extract_{model}_n4_r1"
    bundle = RUNS_DIR / f"judge_{judge}_on_{model}" / f"judge_{judge}_on_{model}"
    if not (RUNS_DIR / ext).exists() or not bundle.exists():
        return []

    result, _ = evaluate(load_curated(data_path(REFERENCE)), as_experiments(ext),
                         accept_threshold, catalyst_threshold, numeric_tolerance)
    metric = {p["doi"]: p for p in result["per_paper"]}

    rows = []
    for path in glob.glob(str(bundle / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        seen = [v for v in paper["verdicts"] if v.get("parsed_ok")]
        if not seen or paper["doi"] not in metric:
            continue
        m = metric[paper["doi"]]
        denominator = 2 * m["tp"] + m["fp"] + m["fn"]
        rows.append({
            "doi": paper["doi"], "model": model, "judge": judge,
            "records": len(seen),
            "pass_rate": sum(v["verdict"] == "correct" for v in seen) / len(seen),
            "f1": (2 * m["tp"] / denominator) if denominator else 0.0,
        })
    return rows


def leave_one_out(frame):
    """Refit without each paper, predict it, and collect the error. Papers rather than rows,
    because rows from one paper share its curation and are not independent."""
    errors = []
    for doi in frame.doi.unique():
        train, test = frame[frame.doi != doi], frame[frame.doi == doi]
        if len(train) < 3 or train.pass_rate.nunique() < 2:
            continue
        fit = stats.linregress(train.pass_rate, train.f1)
        for row in test.itertuples():
            errors.append(fit.intercept + fit.slope * row.pass_rate - row.f1)
    return np.array(errors)


rows = [r for model in MODELS for r in per_paper(model, JUDGE)]
frame = pd.DataFrame(rows)
if frame.empty:
    print("No paired judge/extraction bundles found.")
    raise SystemExit(0)

out = data_path("calibration_points.csv")
frame.to_csv(out, index=False)

print(f"judge used            {JUDGE}")
print(f"calibration points    {len(frame)}  ({frame.doi.nunique()} papers x "
      f"{frame.model.nunique()} extraction models)")
print(f"pass rate             {frame.pass_rate.mean():.3f} mean, "
      f"{frame.pass_rate.min():.2f}-{frame.pass_rate.max():.2f}")
print(f"metric F1             {frame.f1.mean():.3f} mean, "
      f"{frame.f1.min():.2f}-{frame.f1.max():.2f}")

fit = stats.linregress(frame.pass_rate, frame.f1)
print(f"\nFIT   F1 = {fit.slope:.3f} * pass_rate + {fit.intercept:.3f}")
print(f"      r = {fit.rvalue:.3f}   r^2 = {fit.rvalue ** 2:.3f}   p = {fit.pvalue:.2e}")

residuals = frame.f1 - (fit.intercept + fit.slope * frame.pass_rate)
print(f"      residual sd (in-sample) {residuals.std():.3f}")

errors = leave_one_out(frame)
if len(errors):
    print(f"\nLEAVE-ONE-PAPER-OUT   {len(errors)} predictions")
    print(f"      mean error  {errors.mean():+.3f}   (bias)")
    print(f"      sd          {errors.std():.3f}    <- the band to quote")
    print(f"      90% within  +/-{np.percentile(np.abs(errors), 90):.3f}")

rho, rho_p = stats.spearmanr(frame.pass_rate, frame.f1)
print(f"\nRANK  Spearman rho {rho:.3f} (p = {rho_p:.2e}) — does a higher pass rate mean a better "
      f"extraction,\n      even when the value cannot be predicted?")

by_model = frame.groupby("model").agg(pass_rate=("pass_rate", "mean"), f1=("f1", "mean"))
by_model["predicted"] = fit.intercept + fit.slope * by_model.pass_rate
by_model["error"] = by_model.predicted - by_model.f1
print("\nper extraction model, predicted against measured:")
print(by_model.to_string(float_format="{:.3f}".format))

print(f"\nHOW TO USE IT: a judge pass rate of p implies F1 = {fit.slope:.3f}p + {fit.intercept:.3f}, "
      f"give or take {errors.std():.3f}" if len(errors) else "")
print(f"\nwrote {out}")

# ---------------------------------------------------------------------------
# Per-paper prediction is noisy, but the mass extraction never needs one paper: it needs the mean
# over hundreds. Averaging shrinks the error by sqrt(n), so the question is how accurate the
# corpus-level estimate is, not the per-paper one.
generator = np.random.default_rng(0)
print("\n" + "=" * 74)
print("CORPUS-LEVEL PREDICTION — what the mass extraction actually asks for")
print("=" * 74)

for size in (10, 24, 100, 500, 900):
    spread = []
    for _ in range(4000):
        sample = frame.sample(n=min(size, len(frame)), replace=True, random_state=None)
        predicted = fit.intercept + fit.slope * sample.pass_rate.mean()
        spread.append(predicted - sample.f1.mean())
    spread = np.array(spread)
    print(f"  corpus of {size:4d} papers   error {spread.mean():+.3f} +/- {spread.std():.3f}"
          f"   (95% within +/-{np.percentile(np.abs(spread), 95):.3f})")

print("\n  held-out check — predict each model's corpus mean from its pass rate alone:")
for row in by_model.itertuples():
    others = frame[frame.model != row.Index]
    refit = stats.linregress(others.pass_rate, others.f1)
    predicted = refit.intercept + refit.slope * row.pass_rate
    print(f"    {row.Index:8s} predicted {predicted:.3f}  measured {row.f1:.3f}  "
          f"error {predicted - row.f1:+.3f}")
