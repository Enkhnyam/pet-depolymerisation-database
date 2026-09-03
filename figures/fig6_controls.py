"""What has to be held constant before the temperature effect appears.

The pooled temperature coefficient is indistinguishable from zero. Add controls one at a time
and it climbs across zero into a clear positive effect. This figure is that climb.

The point the figure has to make, and the reason the last three rows are shaded: the controls
that finally move the coefficient are not chemistry. Catalyst structure appears in exactly one
paper 78% of the time and a solvent spelling 91% of the time, so conditioning on them is
conditioning on which study the row came from. The DOI row makes that explicit by using the
study label itself.

That distinction is the whole argument. The coefficient becoming positive proves the negative
pooled slope was confounding rather than bad measurement -- a real result. It does not make the
data predictive, because a study label has no value for a study you have not seen.

Coefficients are ordinary least squares on 1,196 records with both a temperature and a yield;
bars are 95% intervals. Categorical controls enter as dummies.

    fig6_controls.py           artifacts/figures/fig6_controls.pdf and .png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, NEUTRAL, RULE, WARN, plt
from core.paths import ARTIFACTS

HOMO = ARTIFACTS / "release" / "pet_homogeneous.xlsx"
SOLID, FAINT = CYCLE[0], CYCLE[1]

# label, extra numeric columns, extra categorical columns, is this control a study fingerprint
LADDER = [
    ("temperature only", [], [], False),
    ("+ reaction time", ["logtime"], [], False),
    ("+ catalyst loading", ["logtime", "logload"], [], False),
    ("+ route", ["logtime", "logload"], ["route"], False),
    ("+ catalyst class", ["logtime", "logload"], ["route", "catalyst_class"], False),
    ("+ catalyst structure", ["logtime", "logload"], ["route", "cat"], True),
    ("+ solvent identity", ["logtime", "logload"], ["route", "cat", "sol"], True),
    ("+ which paper it came from", ["logtime", "logload"], ["doi"], True),
]


def load():
    frame = pd.read_excel(HOMO, sheet_name="Data")
    frame = frame[frame.yield_percent.notna() & frame.temperature_c.notna()]
    frame = frame[frame.yield_percent <= 100].copy()
    loading = frame.catalyst_amount_g / frame.PET_amount_g
    frame["logtime"] = np.log10(frame.reaction_time_min.clip(lower=1)).fillna(0)
    frame["logload"] = np.log10(loading.clip(lower=1e-5)).fillna(-2)
    frame["cat"] = frame.catalyst_smiles.fillna("none")
    frame["sol"] = frame.solvent.fillna("none")
    return frame


def coefficient(frame, numeric, categorical):
    """OLS slope on temperature, and its standard error, with everything else held constant."""
    y = frame.yield_percent.values
    blocks = [np.ones((len(frame), 1)), frame.temperature_c.values[:, None].astype(float)]
    blocks += [frame[c].values[:, None].astype(float) for c in numeric]
    for column in categorical:
        dummies = pd.get_dummies(frame[column], drop_first=True).values.astype(float)
        if dummies.shape[1]:
            blocks.append(dummies)
    design = np.hstack(blocks)

    beta, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ beta
    variance = (residual ** 2).sum() / (len(y) - rank)
    error = np.sqrt(variance * np.linalg.pinv(design.T @ design)[1, 1])
    return beta[1], error, rank


def main() -> None:
    frame = load()
    rows = [(label, *coefficient(frame, numeric, categorical), fingerprint)
            for label, numeric, categorical, fingerprint in LADDER]

    plt.rcParams.update({"font.size": 10, "axes.labelsize": 11.5,
                         "xtick.labelsize": 10, "ytick.labelsize": 11})
    figure, axis = plt.subplots(figsize=(9.6, 6.4))
    figure.subplots_adjust(top=0.715, left=0.315, right=0.965, bottom=0.115)

    # the band behind the rows whose control is really a label for the study
    first = next(i for i, r in enumerate(rows) if r[4])
    axis.axhspan(first - 0.5, len(rows) - 0.5, color=NEUTRAL, alpha=0.055, zorder=0)
    axis.axvline(0, color=WARN, lw=1.6, ls="--", zorder=2)

    for index, (label, beta, error, _, fingerprint) in enumerate(rows):
        low, high = beta - 1.96 * error, beta + 1.96 * error
        solid = low > 0
        colour = SOLID if solid else FAINT
        axis.plot([low, high], [index, index], color=colour, lw=2.4, alpha=0.85,
                  solid_capstyle="round", zorder=3)
        axis.scatter([beta], [index], s=110, color=colour, zorder=4, linewidths=0)
        axis.text(high + 0.012, index, f"{beta:+.3f}", va="center", ha="left",
                  fontsize=10, color=colour, fontweight="bold" if solid else "normal")

    axis.set_yticks(range(len(rows)))
    axis.set_yticklabels([r[0] for r in rows])
    for tick, row in zip(axis.get_yticklabels(), rows):
        tick.set_color(INK if row[4] else DIM)
    axis.set_ylim(len(rows) - 0.4, -0.6)
    axis.set_xlabel("effect of temperature on yield  (% yield per °C, with 95% interval)")
    axis.set_xlim(-0.09, 0.545)
    axis.grid(axis="x", color=RULE, lw=0.6, alpha=0.5, zorder=0)
    axis.set_axisbelow(True)
    axis.spines["left"].set_visible(False)
    axis.tick_params(axis="y", length=0)

    axis.text(0.0, 1.012, "no effect", transform=axis.get_xaxis_transform(),
              ha="center", va="bottom", fontsize=9.5, color=WARN)

    figure.text(0.012, 0.940, "Heat only looks like it helps once you know which study you are in.",
                fontsize=15, fontweight="bold", color=INK)
    figure.text(0.012, 0.760,
                "Each row adds one more thing held constant. The effect of temperature starts "
                "at nothing and becomes clearly positive.\n"
                "But the three shaded controls are not chemistry — 78% of catalyst structures "
                "and 91% of solvent names appear in exactly one\npaper, so holding them constant "
                "is holding the study constant. That proves the pooled result was confounded; "
                "it does not\nmake the data predictive, because a new study brings a label the "
                "model has never seen.",
                fontsize=10.5, color=DIM, linespacing=1.6, va="bottom")

    axis.annotate("these controls are really\nlabels for the study",
                  xy=(0.075, 5.55), xytext=(0.33, 3.9), fontsize=10, color=INK,
                  ha="center", va="center", zorder=6,
                  bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=RULE, lw=0.9),
                  arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.55",
                                  color=DIM, lw=1.1, connectionstyle="arc3,rad=0.22",
                                  shrinkA=4, shrinkB=6))

    out = ARTIFACTS / "figures" / "fig6_controls.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png\n")
    for label, beta, error, rank, fingerprint in rows:
        mark = "study label" if fingerprint else "chemistry"
        print(f"  {label:32s} {beta:+.4f} ± {error:.4f}   params={rank:4d}   {mark}")


if __name__ == "__main__":
    main()
