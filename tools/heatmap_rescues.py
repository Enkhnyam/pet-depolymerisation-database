"""Agreement between judge and metric, counted three ways.

A record the metric marked wrong purely because the curated table had no counterpart is not a
disagreement about chemistry -- the metric could not have been right. How many of those to remove
changes the headline number, so all three counts are shown side by side.
"""
import glob, json
from pathlib import Path

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from _setup import (ARTIFACTS, RUNS_DIR, data_path, experiments,
                    ACCEPT, CATALYST, TOLERANCE)
from core.evaluation import evaluate
from core.schema import load_curated

SURFACE="#fcfcfb"; INK="#0b0b0b"; MUTED="#52514e"; GRID="#dedcd6"
plt.rcParams.update({"figure.facecolor":SURFACE,"axes.facecolor":SURFACE,"axes.edgecolor":GRID,
 "axes.labelcolor":MUTED,"text.color":INK,"xtick.color":MUTED,"ytick.color":MUTED,"font.size":10,
 "axes.titlesize":10.5,"axes.spines.top":False,"axes.spines.right":False})

MODELS = ["oss", "luna", "terra"]
reference = load_curated(data_path("curated_table_final.json"))

views = {k: pd.DataFrame(index=MODELS, columns=MODELS, dtype=float)
         for k in ("all", "no_rescues", "no_unmatched")}
counts = pd.DataFrame(index=MODELS, columns=MODELS, dtype=float)

for target in MODELS:
    _, labels = evaluate(reference, experiments(RUNS_DIR / f"extract_{target}/extract_{target}_n4_r1"),
                         ACCEPT, CATALYST, TOLERANCE)
    m = pd.DataFrame(labels); m = m[m.extracted_index.notna()].copy()
    m["index"] = m.extracted_index.astype(int)
    m["metric"] = m.verdict.map({"TP": "correct"}).fillna("incorrect")
    m["unmatched"] = m.reason.fillna("").str.contains("unmatched extracted")
    for judge in MODELS:
        d = RUNS_DIR / f"judge_{judge}_on_{target}" / f"judge_{judge}_on_{target}"
        if not d.exists(): continue
        jv = []
        for f in glob.glob(str(d / "verdicts/*.json")):
            p = json.loads(Path(f).read_text())
            jv += [{"doi": p["doi"], "index": v["extracted_index"], "judge": v["verdict"]}
                   for v in p["verdicts"] if v.get("parsed_ok")]
        b = m.merge(pd.DataFrame(jv), on=["doi", "index"])
        rescue = b.unmatched & (b.judge == "correct")
        views["all"].loc[judge, target] = (b.judge == b.metric).mean()
        views["no_rescues"].loc[judge, target] = (b[~rescue].judge == b[~rescue].metric).mean()
        views["no_unmatched"].loc[judge, target] = (b[~b.unmatched].judge == b[~b.unmatched].metric).mean()
        counts.loc[judge, target] = int(rescue.sum())

TITLES = {"all": "every record", "no_rescues": "minus judge-vouched rescues",
          "no_unmatched": "minus every unmatched record"}
fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.2))
for ax, key in zip(axes, ["all", "no_rescues", "no_unmatched"]):
    grid = views[key].values.astype(float)
    im = ax.imshow(grid, cmap="Blues", vmin=0.50, vmax=0.95, aspect="auto")
    ax.set_xticks(range(len(MODELS))); ax.set_xticklabels(MODELS)
    ax.set_yticks(range(len(MODELS))); ax.set_yticklabels(MODELS if key == "all" else [])
    ax.set_xlabel("extraction")
    if key == "all": ax.set_ylabel("judge")
    ax.set_title(f"{TITLES[key]}   (mean {np.nanmean(grid):.2f})", loc="left", color=INK)
    for i in range(len(MODELS)):
        for j in range(len(MODELS)):
            v = grid[i, j]
            if np.isnan(v): continue
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=11,
                    color="#ffffff" if v > 0.78 else INK, weight="700" if i == j else "400")
    ax.grid(False)
fig.colorbar(im, ax=axes, fraction=0.02, pad=0.015).outline.set_visible(False)
fig.savefig(ARTIFACTS / "fig_agreement.png", dpi=190, facecolor=SURFACE, bbox_inches="tight")

print("mean agreement by view:")
for k, t in TITLES.items():
    print(f"  {t:34s} {np.nanmean(views[k].values.astype(float)):.3f}")
print("\nminus judge-vouched rescues — judges down, extractions across:")
print(views["no_rescues"].to_string(float_format="{:.3f}".format))
print("\nrescues removed per cell:")
print(counts.astype("Int64").to_string())
best = views["no_rescues"].stack().idxmax()
print(f"\nbest pair: judge {best[0]} on extraction {best[1]} = "
      f"{views['no_rescues'].loc[best[0], best[1]]:.3f}")
print(f"wrote {ARTIFACTS / 'fig_agreement.png'}")
