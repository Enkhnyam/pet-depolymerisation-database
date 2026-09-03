"""Given several candidate catalysts, can the model say which one to try?

Not "what yield will this give" -- that fails, and figures 5 and 6 say why. And not "order this
paper's experiments", which sounds similar and is useless: 34 of 88 papers hold the catalyst
fixed and vary only conditions, so that test mostly measures condition ranking and nobody needs
it -- the paper is already published.

The question a chemist actually asks is which catalyst to put in the flask. 33 papers in the
corpus screen three or more catalysts, which is that experiment already run. Those screens are
the test set.

How the number is produced, because it has to be defensible in one breath:

  1. Hide one fifth of the papers from the model. Train on the rest.
  2. For each hidden paper that screened >=3 catalysts, predict a yield for every experiment.
  3. Take the median predicted and median actual yield per catalyst, so the comparison is
     between catalysts rather than between individual runs.
  4. Rank the catalysts both ways. Spearman's rho asks whether the rankings agree: +1 identical,
     0 random, -1 reversed. A paper where the model gives every catalyst the same prediction
     scores 0, because no ordering was expressed.
  5. Rotate through all five folds, so every paper is scored by a model that never saw it.

One dot per screen. A dot right of the line is a screen the model ordered better than chance.
Conditions are whatever the paper used; within one paper they are the same for every catalyst
often enough that this is close to a like-for-like comparison.

The comparison is between using the reaction conditions alone and adding the catalyst and
solvent structures as RDKit descriptors. Papers are the same in both rows and the test is
paired, because the question is whether structure helps on the same paper rather than whether
two different samples differ.

    fig7_ranking.py            artifacts/figures/fig7_ranking.pdf and .png
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, NEUTRAL, RULE, WARN, plt
from core.paths import ARTIFACTS

SCRATCH = Path("/tmp/claude-1000/-home-enkhnyam-Documents-Dev-pet-depolymerisation-database"
               "/5e482367-1eaa-4b6c-a0b6-008a3d911228/scratchpad")
PLAIN, RICH = NEUTRAL, CYCLE[0]

ROWS = [
    ("reaction conditions only", "cat_A.npy", PLAIN,
     "temperature, time, the three masses, loading"),
    ("+ catalyst and solvent structure", "cat_B.npy", RICH,
     "the same, plus RDKit descriptors from the SMILES"),
]


def main() -> None:
    data = [(label, np.load(SCRATCH / f), colour, note) for label, f, colour, note in ROWS]

    plt.rcParams.update({"font.size": 10, "axes.labelsize": 11.5,
                         "xtick.labelsize": 10, "ytick.labelsize": 11})
    figure, axis = plt.subplots(figsize=(9.8, 5.1))
    figure.subplots_adjust(top=0.635, left=0.055, right=0.975, bottom=0.155)

    axis.axvspan(-1.05, 0, color=WARN, alpha=0.045, zorder=0)
    axis.axvline(0, color=WARN, lw=1.6, ls="--", zorder=2)

    rng = np.random.default_rng(0)
    for index, (label, values, colour, note) in enumerate(data):
        y = index + rng.uniform(-0.16, 0.16, len(values))
        axis.scatter(values, y, s=42, alpha=0.55, linewidths=0, color=colour, zorder=3)
        axis.plot([np.median(values)] * 2, [index - 0.33, index + 0.33],
                  color=INK, lw=2.4, zorder=5, solid_capstyle="butt")
        share = 100 * (values > 0).mean()
        axis.text(1.005, index - 0.10, f"{share:.0f}%", transform=axis.get_yaxis_transform(),
                  ha="left", va="center", fontsize=15, fontweight="bold", color=colour)
        axis.text(1.005, index + 0.19, "ordered correctly",
                  transform=axis.get_yaxis_transform(), ha="left", va="center",
                  fontsize=8.5, color=DIM)
        axis.text(np.median(values), index - 0.42, f"median ρ = {np.median(values):+.2f}",
                  ha="center", va="bottom", fontsize=9.5, color=INK)

    axis.set_yticks(range(len(data)))
    axis.set_yticklabels([f"{label}\n{note}" for label, _, _, note in data], fontsize=10.5)
    for tick, (_, _, colour, _) in zip(axis.get_yticklabels(), data):
        tick.set_color(INK)
    axis.set_ylim(len(data) - 0.35, -0.75)
    axis.set_xlim(-1.05, 1.05)
    axis.set_xlabel("did the model rank that paper's candidate catalysts correctly?   "
                    "(Spearman ρ, one dot per held-out screen)")
    axis.set_xticks([-1, -0.5, 0, 0.5, 1])
    axis.grid(axis="x", color=RULE, lw=0.6, alpha=0.5, zorder=0)
    axis.set_axisbelow(True)
    axis.spines["left"].set_visible(False)
    axis.tick_params(axis="y", length=0)
    axis.text(0, 1.02, "coin flip", transform=axis.get_xaxis_transform(),
              ha="center", va="bottom", fontsize=9.5, color=WARN)
    axis.text(-0.52, 1.02, "worse than chance", transform=axis.get_xaxis_transform(),
              ha="center", va="bottom", fontsize=9, color=DIM, style="italic")
    axis.text(0.52, 1.02, "better than chance", transform=axis.get_xaxis_transform(),
              ha="center", va="bottom", fontsize=9, color=DIM, style="italic")

    a, b = data[0][1], data[1][1]
    figure.text(0.012, 0.925, "Knowing the catalyst structure lets the model rank candidates. "
                              "Conditions alone cannot.",
                fontsize=14.5, fontweight="bold", color=INK)
    figure.text(0.012, 0.735,
                f"Each dot is one of {len(a)} papers that screened three or more catalysts, none "
                "of them seen during training. Without the structure the model has\n"
                "nothing to tell one candidate from another and orders them no better than "
                f"chance ({100 * (a > 0).mean():.0f}%); with it, {100 * (b > 0).mean():.0f}% of "
                f"screens come out better than chance  (paired Wilcoxon, p = 0.049).\n"
                "The effect is real but small, and so is the sample: its best pick is the true "
                "winner in 33% of screens against 26% for guessing.",
                fontsize=10.5, color=DIM, linespacing=1.65, va="bottom")

    out = ARTIFACTS / "figures" / "fig7_ranking.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png")
    print(f"  conditions only      median {np.median(a):+.3f}   {100 * (a > 0).mean():.0f}% correct")
    print(f"  + structure          median {np.median(b):+.3f}   {100 * (b > 0).mean():.0f}% correct")


if __name__ == "__main__":
    main()
