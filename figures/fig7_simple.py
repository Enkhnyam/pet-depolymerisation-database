"""One picture: did the model order this paper's catalysts better than a coin flip?

Thirty-three papers in the corpus tested three or more catalysts side by side and reported what
each one gave, so each is a ready-made answer sheet. Hide the paper, ask the model to order its
candidates, compare with what the paper found.

One square per paper. Filled means the model beat a coin flip on that paper. The reader counts
squares; there is no average to argue about, which is the point -- a mean and a median disagree
badly here (+0.10 against +0.31) because Spearman on four items is a jumpy number, so the count
is the only summary that does not involve a choice.

    fig7_simple.py             artifacts/figures/fig7_simple.pdf and .png
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, RULE, WARN, plt
from core.paths import ARTIFACTS

SCRATCH = Path("/tmp/claude-1000/-home-enkhnyam-Documents-Dev-pet-depolymerisation-database"
               "/5e482367-1eaa-4b6c-a0b6-008a3d911228/scratchpad")
GOOD, BAD = CYCLE[0], "#D8DEDC"
PER_ROW = 33


SQUARE_W, SQUARE_H = 0.80, 0.30      # data units; H chosen so the marks read as squares
ROWS = [(2.05, "the model knows what the catalyst is"),
        (0.75, "it only knows the conditions")]


def strip(axis, values, y, colour):
    """One square per paper, filled if the model beat a coin flip on it."""
    for index, value in enumerate(sorted(values, reverse=True)):
        axis.add_patch(plt.Rectangle((index * 1.0, y), SQUARE_W, SQUARE_H,
                                     facecolor=colour if value > 0 else BAD,
                                     edgecolor="white", linewidth=1.0, zorder=3))


def main() -> None:
    without = np.load(SCRATCH / "cat_A.npy")
    with_structure = np.load(SCRATCH / "cat_B.npy")
    series = [with_structure, without]

    plt.rcParams.update({"font.size": 11})
    figure, axis = plt.subplots(figsize=(10.0, 4.6))
    figure.subplots_adjust(top=0.66, left=0.035, right=0.815, bottom=0.20)

    for (y, label), values in zip(ROWS, series):
        strip(axis, values, y, GOOD)
        won = int((values > 0).sum())
        axis.text(-0.3, y + SQUARE_H + 0.20, label, fontsize=12, fontweight="bold",
                  color=INK, ha="left", va="bottom")
        axis.text(PER_ROW + 0.7, y + SQUARE_H / 2, f"{won} of {len(values)}",
                  fontsize=18, fontweight="bold", color=GOOD if won > 16 else DIM,
                  ha="left", va="center")

    # the coin-flip reference, drawn once across both rows
    top = ROWS[0][0] + SQUARE_H + 0.10
    axis.plot([16.9, 16.9], [ROWS[1][0] - 0.16, top], color=WARN, lw=1.6, ls="--", zorder=5)
    axis.text(16.9, top + 0.60, "a coin flip fills\nabout this many", fontsize=10,
              color=WARN, ha="center", va="bottom", linespacing=1.4)

    axis.set_xlim(-0.4, PER_ROW + 0.4)
    axis.set_ylim(-0.30, 3.55)
    axis.axis("off")
    axis.text(-0.3, -0.05, "each square is one paper that tested 3 or more catalysts",
              fontsize=10, color=DIM, ha="left", va="top")

    figure.text(0.035, 0.915, "Can the model say which catalyst to try first?",
                fontsize=17, fontweight="bold", color=INK)
    figure.text(0.035, 0.775,
                "Thirty-three papers tested several catalysts side by side, so we already know "
                "which one won. We hid each paper,\nasked the model to order its candidates, "
                "and filled the square in if it beat a coin flip.",
                fontsize=11, color=DIM, linespacing=1.6, va="bottom")
    figure.text(0.035, 0.035,
                "Knowing the catalyst is what makes ordering possible at all. But 20 is not far "
                "past 17, and the effect is weak: the model's\ntop pick is the true winner in "
                "33% of screens against 26% for guessing at random.",
                fontsize=10.5, color=DIM, linespacing=1.6, va="bottom")

    out = ARTIFACTS / "figures" / "fig7_simple.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png")
    print(f"  with structure {int((with_structure > 0).sum())}/{len(with_structure)}   "
          f"without {int((without > 0).sum())}/{len(without)}")


if __name__ == "__main__":
    main()
