"""Which judge/extraction pair to deploy, and whether the rescue review changes the answer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
from _setup import ARTIFACTS, data_path

SURFACE="#fcfcfb"; INK="#0b0b0b"; MUTED="#52514e"; GRID="#dedcd6"
BLUE="#2a78d6"; ORANGE="#eb6834"; AQUA="#1baf7a"
plt.rcParams.update({"figure.facecolor":SURFACE,"axes.facecolor":SURFACE,"axes.edgecolor":GRID,
 "axes.labelcolor":MUTED,"text.color":INK,"xtick.color":MUTED,"ytick.color":MUTED,"font.size":10,
 "axes.titlesize":11,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.6,"grid.alpha":0.7,
 "axes.spines.top":False,"axes.spines.right":False})

f = pd.read_csv(data_path("pair_comparison.csv")).sort_values("no_resc")

fig, (ax, bx) = plt.subplots(1, 2, figsize=(13.5, 5.0), gridspec_kw={"width_ratios":[1.15,1]})

# --- left: the deployment decision
for diag, marker, label in [(False, "o", "different models"), (True, "^", "model judging itself")]:
    s = f[f.diag == diag]
    ax.scatter(s.cost1000, s.no_resc, s=90 + s.rescues*2.2, marker=marker,
               color=BLUE if not diag else ORANGE, alpha=0.85, zorder=3,
               edgecolor=SURFACE, linewidth=1.5, label=label)
for r in f.itertuples():
    ax.annotate(r.pair, (r.cost1000, r.no_resc), textcoords="offset points",
                xytext=(9, -3), fontsize=8.8, color=INK)
ax.set_xlabel("cost to run on 1000 papers  ($)")
ax.set_ylabel("agreement, rescues excluded")
ax.set_title("Pick a pair: agreement against cost\n(marker size = rescues needing review)",
             loc="left", color=INK)
ax.legend(frameon=False, fontsize=9, loc="lower right")
ax.set_xlim(-18, 320)

# --- right: does the exclusion rule matter?
y = np.arange(len(f))
bx.hlines(y, f.no_unm, f.no_resc, color=MUTED, lw=1.4, alpha=0.5, zorder=2)
bx.scatter(f.no_unm, y, s=90, color=AQUA, zorder=3, edgecolor=SURFACE, linewidth=1.5,
           label="drop every unmatched record  (mechanical, no review)")
bx.scatter(f.no_resc, y, s=90, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=1.5,
           label="drop only judge-vouched rescues  (needs review)")
bx.set_yticks(y); bx.set_yticklabels(f.pair)
bx.set_xlabel("agreement")
bx.set_title(f"The two exclusion rules barely differ\n(mean gap {f.gap.mean():.3f}, "
             f"largest {f.gap.max():.3f})", loc="left", color=INK)
bx.legend(frameon=False, fontsize=8.6, loc="lower right")
bx.grid(axis="y", visible=False)
for r, i in zip(f.itertuples(), y):
    bx.annotate(f"{r.gap:+.3f}", (max(r.no_resc, r.no_unm), i), textcoords="offset points",
                xytext=(8, -3), fontsize=8.5, color=MUTED)
bx.set_xlim(0.72, 0.98)

fig.tight_layout()
fig.savefig(ARTIFACTS / "fig_pairs.png", dpi=190, facecolor=SURFACE)
print("wrote", ARTIFACTS / "fig_pairs.png")
