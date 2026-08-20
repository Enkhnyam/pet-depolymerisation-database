"""The visual language every figure shares.

One palette, one panel helper, one save path. A figure module imports the numbers from the check
that prints them, so a panel and its printed table cannot disagree.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))          # checks import each other by bare name
from core.paths import ARTIFACTS

# Two roles, never mixed: route in the chemistry figure, grader in the quality figure.
ROUTE = {"glycolysis": "#0E7C6B", "hydrolysis": "#C4527A",
         "methanolysis": "#9A6510", "other/unclear": "#4A6B8A"}
GRADER = {"metric": "#0E7C6B", "judge": "#C4527A"}
VERDICT = {"accepted": "#0E7C6B", "corrected": "#9A6510", "dropped": "#A33A2E"}
SEQUENTIAL = "BuGn"          # single hue, so heatmaps never compete with the categoricals

INK, DIM, RULE = "#12201F", "#5D716E", "#D2DEDB"

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": RULE, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": DIM, "ytick.color": DIM, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 6.5,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def canvas(rows: int, cols: int, width: float = 7.2, height: float = None):
    """A multi-panel figure with panel letters already placed."""
    height = height or width * rows / cols * 0.78
    figure, axes = plt.subplots(rows, cols, figsize=(width, height))
    flat = axes.ravel() if rows * cols > 1 else [axes]
    for letter, axis in zip("abcdefghijklmnopqrstuvwxyz", flat):
        axis.set_title(letter, loc="left", fontsize=9, fontweight="bold", pad=6)
    return figure, list(flat)


def scatter(axis, x, y, colour, label=None):
    """The house scatter: translucent, small, so 1,800 points read as a cloud."""
    axis.scatter(x, y, s=13, alpha=0.45, linewidths=0, color=colour, label=label)


def save(figure, name: str) -> Path:
    out = ARTIFACTS / "figures" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)}")
    return out
