"""Agreement for every judge/extraction pair, three ways, with what each pair costs at scale.

The third panel is a range, not a value. Supervisors are reviewing the records the metric had no
counterpart for: every one they confirm joins the table and becomes an agreement, every one they
reject stays a disagreement. Rejecting all of them lands on the left panel, confirming all of them
lands at the top of the range, and the truth is somewhere between.
"""
import glob, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

from _setup import (ARTIFACTS, RUNS_DIR, data_path, as_experiments,
                    accept_threshold, catalyst_threshold, numeric_tolerance)
from core.evaluation import evaluate
from core.schema import load_curated, Experiment

SURFACE="#fcfcfb"; INK="#0b0b0b"; MUTED="#52514e"; GRID="#dedcd6"
plt.rcParams.update({"figure.facecolor":SURFACE,"axes.facecolor":SURFACE,"axes.edgecolor":GRID,
 "axes.labelcolor":MUTED,"text.color":INK,"xtick.color":MUTED,"ytick.color":MUTED,"font.size":10,
 "axes.titlesize":10.5,"axes.spines.top":False,"axes.spines.right":False})

M = ["oss", "luna", "terra"]
# measured on the 24-paper runs, scaled to 1000 papers
EXT_1000   = {"oss": 0.0, "luna": 0.44/24*1000, "terra": 5.12/24*1000}
JUDGE_1000 = {"oss": 0.0, "luna": 0.20/24*1000, "terra": 1.89/24*1000}

base = json.loads(data_path("curated_table_final.json").read_text())
ref = load_curated(data_path("curated_table_final.json"))

records = {t: {json.loads(Path(f).read_text())["doi"]: json.loads(Path(f).read_text())["records"]
               for f in glob.glob(str(RUNS_DIR / f"extract_{t}/extract_{t}_n4_r1/extractions/*.json"))}
           for t in M}

def verdicts(j, t):
    rows = []
    for f in glob.glob(str(RUNS_DIR / f"judge_{j}_on_{t}/judge_{j}_on_{t}/verdicts/*.json")):
        p = json.loads(Path(f).read_text())
        rows += [{"doi": p["doi"], "index": v["extracted_index"], "judge": v["verdict"]}
                 for v in p["verdicts"] if v.get("parsed_ok")]
    return pd.DataFrame(rows)

def scored(reference, t):
    _, lab = evaluate(reference, as_experiments(f"extract_{t}/extract_{t}_n4_r1"),
                      accept_threshold, catalyst_threshold, numeric_tolerance)
    m = pd.DataFrame(lab); m = m[m.extracted_index.notna()].copy()
    m["index"] = m.extracted_index.astype(int)
    m["metric"] = m.verdict.map({"TP": "correct"}).fillna("incorrect")
    m["unmatched"] = m.reason.fillna("").str.contains("unmatched extracted")
    return m

raw   = pd.DataFrame(index=M, columns=M, dtype=float)
drop  = pd.DataFrame(index=M, columns=M, dtype=float)
added = pd.DataFrame(index=M, columns=M, dtype=float)
cost  = pd.DataFrame(index=M, columns=M, dtype=float)

for t in M:
    m = scored(ref, t)
    for j in M:
        b = m.merge(verdicts(j, t), on=["doi", "index"])
        rescue = b.unmatched & (b.judge == "correct")
        raw.loc[j, t]  = (b.judge == b.metric).mean()
        drop.loc[j, t] = (b[~rescue].judge == b[~rescue].metric).mean()
        grown = {p["doi"]: [e["experiment_data"] for e in p["extracted_experiments"]] for p in base}
        for r in b[rescue].itertuples():
            grown.setdefault(r.doi, []).append(records[t][r.doi][r.index])
        m4 = scored({d: [Experiment.model_validate(x) for x in v] for d, v in grown.items()}, t)
        b4 = m4.merge(verdicts(j, t), on=["doi", "index"])
        added.loc[j, t] = (b4.judge == b4.metric).mean()
        cost.loc[j, t] = EXT_1000[t] + JUDGE_1000[j]

def money(v):
    return "free" if v < 1 else f"${v:,.0f}"

fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6))
panels = [
    (raw,   None,  "1. every record\n(supervisors reject every candidate)"),
    (drop,  None,  "2. records the metric could not evaluate removed\n(mechanical, no review needed)"),
    (added, raw,   "3. range once supervisors review\n(reject all → confirm all)"),
]
for ax, (grid, low, title) in zip(axes, panels):
    values = grid.values.astype(float)
    im = ax.imshow(values, cmap="Blues", vmin=0.65, vmax=0.96, aspect="auto")
    ax.set_xticks(range(3)); ax.set_xticklabels(M)
    ax.set_yticks(range(3)); ax.set_yticklabels(M if grid is raw else [])
    ax.set_xlabel("extraction model")
    if grid is raw: ax.set_ylabel("judge model")
    ax.set_title(title, loc="left", color=INK)
    for i in range(3):
        for j in range(3):
            v = values[i, j]
            pale = "#ffffff" if v > 0.86 else INK
            text = f"{low.values[i, j]:.2f}–{v:.2f}" if low is not None else f"{v:.3f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=11.5 if low is None else 10.5,
                    color=pale, weight="700" if M[i] == M[j] else "500")
            ax.text(j, i + 0.30, money(cost.values[i, j]), ha="center", va="center",
                    fontsize=8.5, color=pale, alpha=0.85)
    ax.grid(False)
fig.colorbar(im, ax=axes, fraction=0.018, pad=0.012).outline.set_visible(False)
fig.text(0.012, 0.015, "cost under each cell is for 1000 papers: extraction + judging. "
         "Bold = the model judging its own output.", fontsize=8.6, color=MUTED)
fig.savefig(ARTIFACTS / "fig_grid.png", dpi=190, facecolor=SURFACE, bbox_inches="tight")

out = pd.DataFrame({"pair": [f"{j}->{t}" for j in M for t in M],
                    "raw": [raw.loc[j, t] for j in M for t in M],
                    "rescues_removed": [drop.loc[j, t] for j in M for t in M],
                    "rescues_added": [added.loc[j, t] for j in M for t in M],
                    "cost_1000": [cost.loc[j, t] for j in M for t in M]})
out["range"] = out.rescues_added - out.raw
print(out.sort_values("rescues_removed", ascending=False).to_string(index=False, float_format="{:.3f}".format))
print(f"\nwrote {ARTIFACTS/'fig_grid.png'}")
