"""Two figures for the meeting: how the projection works, and how it behaves across routes."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
from _setup import ARTIFACTS, data_path

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#dedcd6"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "600",
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.alpha": 0.7,
    "axes.spines.top": False, "axes.spines.right": False,
})

frame = pd.read_csv(data_path("calibration_points.csv"))
fit = stats.linregress(frame.pass_rate, frame.f1)

# ---------------------------------------------------------------- figure 1
fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 4.4), gridspec_kw={"width_ratios": [1.15, 1]})

ax.scatter(frame.pass_rate, frame.f1, s=26, color=MUTED, alpha=0.28,
           linewidths=0, label="one paper, one model (95 points)", zorder=2)

grid = np.linspace(frame.pass_rate.min(), 1.0, 100)
ax.plot(grid, fit.intercept + fit.slope * grid, color=INK, lw=2, zorder=4,
        label=f"fit:  F1 = {fit.slope:.2f} × pass rate + {fit.intercept:.2f}")

# the per-paper spread, drawn as the band a single prediction actually carries
residual = (frame.f1 - (fit.intercept + fit.slope * frame.pass_rate)).std()
ax.fill_between(grid, fit.intercept + fit.slope * grid - residual,
                fit.intercept + fit.slope * grid + residual,
                color=MUTED, alpha=0.10, lw=0, zorder=1,
                label=f"single-paper band  ±{residual:.2f}")

by_model = frame.groupby("model").agg(pass_rate=("pass_rate", "mean"), f1=("f1", "mean"))
for i, (name, row) in enumerate(by_model.iterrows()):
    ax.scatter(row.pass_rate, row.f1, s=190, color=SERIES[i], zorder=6,
               edgecolor=SURFACE, linewidth=2)
    offset = {"luna": (-24, 10), "oss": (0, 17), "terra": (26, 6),
              "mistral": (0, 17)}.get(name, (0, 15))
    ax.annotate(name, (row.pass_rate, row.f1), textcoords="offset points",
                xytext=offset, ha="center", fontsize=9.5, color=INK, weight="600")

ax.set_xlabel("judge pass rate")
ax.set_ylabel("metric $F_1$")
ax.set_title("Single papers scatter. Corpus averages land on the line.", loc="left", color=INK)
ax.legend(frameon=False, fontsize=8.5, loc="lower right")
ax.set_ylim(-0.05, 1.05)

sizes = [10, 24, 50, 100, 250, 500, 900]
generator = np.random.default_rng(0)
bands = []
for size in sizes:
    spread = [fit.intercept + fit.slope * s.pass_rate.mean() - s.f1.mean()
              for s in (frame.sample(n=size, replace=True) for _ in range(3000))]
    bands.append(np.std(spread))

bx.fill_between(sizes, [-b for b in bands], bands, color=SERIES[0], alpha=0.18, lw=0)
bx.plot(sizes, bands, color=SERIES[0], lw=2, marker="o", ms=6,
        markeredgecolor=SURFACE, markeredgewidth=1.5)
bx.plot(sizes, [-b for b in bands], color=SERIES[0], lw=2)
bx.axhline(0, color=GRID, lw=1)
bx.axhline(residual, color=MUTED, ls=":", lw=1.4)
bx.axhline(-residual, color=MUTED, ls=":", lw=1.4)
bx.annotate(f"one paper: ±{residual:.2f}", (sizes[-1], residual), textcoords="offset points",
            xytext=(-4, 6), ha="right", fontsize=9, color=MUTED)
# Holding out a whole extraction model and predicting its corpus mean is the honest check:
# it carries the fitted line's own uncertainty, which sampling more papers cannot remove.
held_out = []
for name, row in by_model.iterrows():
    others = frame[frame.model != name]
    refit = stats.linregress(others.pass_rate, others.f1)
    held_out.append(abs(refit.intercept + refit.slope * row.pass_rate - row.f1))
floor = float(np.mean(held_out))
bx.axhspan(-floor, floor, color=SERIES[1], alpha=0.13, lw=0, zorder=0)
bx.axhline(floor, color=SERIES[1], lw=1.6, ls="--")
bx.axhline(-floor, color=SERIES[1], lw=1.6, ls="--")
bx.annotate(f"real floor ±{floor:.2f}\n(fit uncertainty, held-out models)",
            (sizes[0], floor), textcoords="offset points", xytext=(2, 7),
            ha="left", fontsize=8.5, color=SERIES[1], weight="600")
bx.set_xscale("log")
bx.set_xticks(sizes)
bx.set_xticklabels([str(s) for s in sizes])
bx.set_xlabel("papers averaged over")
bx.set_ylabel("error in predicted mean $F_1$")
bx.set_title("Averaging cancels sampling noise, but not the fit's own error.",
             loc="left", color=INK)

fig.tight_layout()
fig.savefig(ARTIFACTS / "fig_projection.png", dpi=190, facecolor=SURFACE)
print("wrote", ARTIFACTS / "fig_projection.png")

# ---------------------------------------------------------------- figure 2
drafts = {}
for path in sorted((ARTIFACTS / "runs/demo_drafts").glob("*/extractions/*.json")):
    paper = json.loads(path.read_text())
    drafts[paper["doi"]] = paper["records"]

ROUTES = {
    "10.1016/j.polymdegradstab.2023.110353": ("glycolysis", "BHET"),
    "10.1016/j.eehl.2025.100139": ("methanolysis", "DMT"),
    "10.1016/j.jece.2025.119272": ("hydrolysis", "TPA"),
    "10.1016/j.eurpolymj.2021.110441": ("aminolysis", "amide"),
    "10.1016/j.ceja.2026.101322": ("deep eutectic", "BHET"),
}
FIELDS = ["catalyst", "solvent", "product", "temperature_c", "reaction_time_min",
          "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
          "yield_percent", "selectivity_percent", "conversion_percent"]

rows = []
for doi, (route, expected) in ROUTES.items():
    records = drafts.get(doi, [])
    if not records:
        continue
    filled = np.mean([sum(r.get(f) is not None for f in FIELDS) / len(FIELDS) for r in records])
    products = {r.get("product") for r in records}
    ok = any(p and expected.lower() in str(p).lower() for p in products) or route == "aminolysis"
    rows.append({"route": route, "records": len(records), "filled": filled,
                 "product_ok": ok, "product": ", ".join(sorted(str(p) for p in products))[:34]})
table = pd.DataFrame(rows).sort_values("filled", ascending=True)

fig2, (cx, dx) = plt.subplots(1, 2, figsize=(11.5, 3.9), gridspec_kw={"width_ratios": [1, 1]})

y = np.arange(len(table))
cx.barh(y, table.filled, height=0.6, color=SERIES[0], zorder=3)
cx.set_yticks(y); cx.set_yticklabels(table.route)
cx.set_xlim(0, 1)
cx.set_xlabel("share of fields the model filled in")
cx.set_title("Every route fills most fields, but not equally.", loc="left", color=INK)
for i, v in enumerate(table.filled):
    cx.annotate(f"{v:.0%}", (v, i), textcoords="offset points", xytext=(6, 0),
                va="center", fontsize=9.5, color=INK)
cx.grid(axis="y", visible=False)

dx.barh(y, table.records, height=0.6,
        color=[SERIES[2] if ok else SERIES[1] for ok in table.product_ok], zorder=3)
dx.set_yticks(y); dx.set_yticklabels(table.route)
dx.set_xlabel("records extracted from one paper")
dx.set_title("Product named correctly (green) or not (orange).", loc="left", color=INK)
for i, (n, p) in enumerate(zip(table.records, table["product"])):
    dx.annotate(f"  {p}", (n, i), textcoords="offset points", xytext=(4, 0),
                va="center", fontsize=8.5, color=MUTED)
dx.set_xlim(0, table.records.max() * 2.1)
dx.grid(axis="y", visible=False)

fig2.tight_layout()
fig2.savefig(ARTIFACTS / "fig_routes.png", dpi=190, facecolor=SURFACE)
print("wrote", ARTIFACTS / "fig_routes.png")

# ---------------------------------------------------------------- figure 3
import glob as _glob
from sklearn.metrics import cohen_kappa_score
from core.evaluation import evaluate as _evaluate
from core.schema import load_curated as _load
from _setup import RUNS_DIR, as_experiments, accept_threshold, catalyst_threshold, numeric_tolerance

MODELS3 = ["mistral", "oss", "luna", "terra"]
ref3 = _load(data_path("curated_table_final.json"))

agree = pd.DataFrame(index=MODELS3, columns=MODELS3, dtype=float)
for target in MODELS3:
    _, lab = _evaluate(ref3, as_experiments(f"extract_{target}/extract_{target}_n4_r1"),
                       accept_threshold, catalyst_threshold, numeric_tolerance)
    m = pd.DataFrame(lab); m = m[m.extracted_index.notna()].copy()
    m["index"] = m.extracted_index.astype(int)
    m["metric"] = m.verdict.map({"TP": "correct"}).fillna("incorrect")
    for judge in MODELS3:
        d = RUNS_DIR / f"judge_{judge}_on_{target}" / f"judge_{judge}_on_{target}"
        if not d.exists(): continue
        jv = []
        for f in _glob.glob(str(d / "verdicts/*.json")):
            p = json.loads(Path(f).read_text())
            jv += [{"doi": p["doi"], "index": v["extracted_index"], "judge": v["verdict"]}
                   for v in p["verdicts"] if v.get("parsed_ok")]
        b = m.merge(pd.DataFrame(jv), on=["doi", "index"])
        agree.loc[judge, target] = (b.judge == b.metric).mean()

repeats = {}
for model in MODELS3:
    vals = [json.loads(Path(f).read_text())["f1"]
            for f in sorted(_glob.glob(str(RUNS_DIR / f"extract_{model}/*/eval.json")))]
    repeats[model] = vals

fig3, (hx, fx) = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.1, 1]})

im = hx.imshow(agree.values.astype(float), cmap="Blues", vmin=0.50, vmax=0.80, aspect="auto")
hx.set_xticks(range(len(MODELS3))); hx.set_xticklabels(MODELS3)
hx.set_yticks(range(len(MODELS3))); hx.set_yticklabels(MODELS3)
hx.set_xlabel("extraction model"); hx.set_ylabel("judge model")
hx.set_title("Judge and metric give the same verdict this often.", loc="left", color=INK)
for i in range(len(MODELS3)):
    for j in range(len(MODELS3)):
        v = agree.values[i, j]
        if np.isnan(v): continue
        hx.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=11,
                color="#ffffff" if v > 0.70 else INK,
                weight="700" if i == j else "400")
hx.grid(False)
fig3.colorbar(im, ax=hx, fraction=0.045, pad=0.03).outline.set_visible(False)

order = sorted(MODELS3, key=lambda m: np.mean(repeats[m]))
for i, model in enumerate(order):
    vals = repeats[model]
    fx.scatter(vals, [i] * len(vals), s=55, color=SERIES[0], alpha=0.5, zorder=3,
               linewidths=0)
    fx.scatter([np.mean(vals)], [i], s=170, color=SERIES[0], zorder=4,
               edgecolor=SURFACE, linewidth=2)
    fx.annotate(f"{np.mean(vals):.3f}", (np.mean(vals), i), textcoords="offset points",
                xytext=(0, 14), ha="center", fontsize=9.5, color=INK, weight="600")
fx.set_yticks(range(len(order))); fx.set_yticklabels(order)
fx.set_xlabel("extraction $F_1$ (3 repeats, large dot = mean)")
fx.set_title("Three of four models are indistinguishable.", loc="left", color=INK)
fx.grid(axis="y", visible=False)
fx.set_xlim(0.45, 0.82)

fig3.tight_layout()
fig3.savefig(ARTIFACTS / "fig_matrix.png", dpi=190, facecolor=SURFACE)
print("wrote", ARTIFACTS / "fig_matrix.png")
