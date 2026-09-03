"""What the released collection contains, on one page.

Four panels, chosen because they are the four things a reader wants before deciding whether to
download it: how big it is and what got filtered out, what chemistry is in it, how complete the
rows are, and how much of it rests on a structure nobody verified.

The completeness panel is the important one and it is deliberately unflattering. Half the rows
carry no yield, so the number that matters for modelling is not 3,887 -- it is the 796 rows
that carry a yield, a temperature, a time and both masses.

    fig8_release.py            artifacts/figures/fig8_release.pdf and .png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, NEUTRAL, RULE, WARN, plt
from core.paths import ARTIFACTS

RELEASE = ARTIFACTS / "release" / "pet_homogeneous_release.csv"
TEAL, ROSE, AMBER, SLATE = CYCLE


def funnel(axis, data, excluded_solid, excluded_unknown):
    total = len(data) + excluded_solid + excluded_unknown
    steps = [("extracted from the literature", total, NEUTRAL),
             ("catalyst is a solid — removed", excluded_solid, ROSE),
             ("catalyst unidentifiable — removed", excluded_unknown, ROSE),
             ("released", len(data), TEAL)]
    for index, (label, value, colour) in enumerate(steps):
        axis.barh(index, value, height=0.6, color=colour, zorder=3)
        axis.text(value + total * 0.015, index, f"{value:,}", va="center", ha="left",
                  fontsize=10, fontweight="bold", color=colour)
    axis.set_yticks(range(len(steps)))
    axis.set_yticklabels([s[0] for s in steps], fontsize=9.5)
    axis.set_ylim(len(steps) - 0.4, -0.6)
    axis.set_xlim(0, total * 1.2)
    axis.set_xticks([])
    axis.set_title("a   what got in", loc="left", fontsize=10, fontweight="bold", pad=8)
    for side in ("top", "right", "bottom", "left"):
        axis.spines[side].set_visible(False)
    axis.tick_params(length=0)


def composition(axis, data):
    counts = data.route.fillna("no route").value_counts()
    colours = {"glycolysis": TEAL, "hydrolysis": ROSE, "methanolysis": AMBER,
               "no route": NEUTRAL, "other/unclear": NEUTRAL}
    axis.barh(range(len(counts)), counts.values, height=0.62, zorder=3,
              color=[colours.get(k, SLATE) for k in counts.index])
    for index, value in enumerate(counts.values):
        axis.text(value + counts.max() * 0.02, index, f"{value:,}", va="center",
                  fontsize=9.5, color=DIM)
    axis.set_yticks(range(len(counts)))
    axis.set_yticklabels(counts.index, fontsize=9.5)
    axis.set_ylim(len(counts) - 0.4, -0.6)
    axis.set_xlim(0, counts.max() * 1.2)
    axis.set_xticks([])
    axis.set_title("b   route (from the solvent)", loc="left",
                   fontsize=10, fontweight="bold", pad=8)
    for side in ("top", "right", "bottom", "left"):
        axis.spines[side].set_visible(False)
    axis.tick_params(length=0)


def completeness(axis, data):
    fields = [("temperature", "temperature_c"), ("reaction time", "reaction_time_min"),
              ("PET mass", "PET_amount_g"), ("catalyst mass", "catalyst_amount_g"),
              ("solvent mass", "solvent_amount_g"), ("yield", "yield_percent"),
              ("conversion", "conversion_percent"), ("pressure", "pressure_atm"),
              ("selectivity", "selectivity_percent")]
    share = [(label, 100 * data[column].notna().mean()) for label, column in fields]
    share.sort(key=lambda pair: pair[1], reverse=True)
    for index, (label, value) in enumerate(share):
        axis.barh(index, value, height=0.62, zorder=3,
                  color=TEAL if value >= 50 else ROSE)
        axis.text(value + 2, index, f"{value:.0f}%", va="center", fontsize=9.5,
                  color=TEAL if value >= 50 else ROSE, fontweight="bold")
    axis.set_yticks(range(len(share)))
    axis.set_yticklabels([s[0] for s in share], fontsize=9.5)
    axis.set_ylim(len(share) - 0.4, -0.6)
    axis.set_xlim(0, 118)
    axis.set_xticks([])
    axis.set_title("c   fields reported", loc="left",
                   fontsize=10, fontweight="bold", pad=8)
    for side in ("top", "right", "bottom", "left"):
        axis.spines[side].set_visible(False)
    axis.tick_params(length=0)


def structures(axis, data):
    """Horizontal bars, like the other panels: a stacked bar puts thin slices' labels on top
    of each other and the two smallest tiers are exactly the ones worth reading."""
    counts = data.structure_source.fillna("no usable structure").value_counts()
    label = {"LLM written": "a model wrote it,\nnothing checked it",
             "confirmed": "confirmed by OPSIN",
             "no catalyst": "no catalyst (baselines)"}
    colours = {"LLM written": ROSE, "confirmed": TEAL, "no catalyst": NEUTRAL}
    names = [label.get(k, k) for k in counts.index]
    for index, (key, value) in enumerate(counts.items()):
        colour = colours.get(key, SLATE)
        axis.barh(index, value, height=0.6, color=colour, zorder=3)
        axis.text(value + counts.max() * 0.03, index,
                  f"{value:,}  ({100 * value / len(data):.0f}%)",
                  va="center", fontsize=9.5, color=colour, fontweight="bold")
    axis.set_yticks(range(len(counts)))
    axis.set_yticklabels(names, fontsize=9.5)
    axis.set_ylim(len(counts) - 0.4, -0.6)
    axis.set_xlim(0, counts.max() * 1.55)
    axis.set_xticks([])
    axis.set_title("d   structure provenance", loc="left",
                   fontsize=10, fontweight="bold", pad=8)
    for side in ("top", "right", "bottom", "left"):
        axis.spines[side].set_visible(False)
    axis.tick_params(length=0)


def main() -> None:
    data = pd.read_csv(RELEASE, low_memory=False)
    plt.rcParams.update({"font.size": 9.5})
    figure, axes = plt.subplots(1, 4, figsize=(13.6, 4.0),
                                gridspec_kw={"width_ratios": [1.15, 1, 1, 1.05]})
    figure.subplots_adjust(top=0.66, bottom=0.10, left=0.135, right=0.985, wspace=1.05)

    funnel(axes[0], data, 1111, 565)
    composition(axes[1], data)
    completeness(axes[2], data)
    structures(axes[3], data)

    modelable = data[["yield_percent", "temperature_c", "reaction_time_min",
                      "catalyst_amount_g", "PET_amount_g"]].notna().all(axis=1)
    figure.text(0.008, 0.925,
                "PET depolymerisation by dissolved catalysts — what is in the release",
                fontsize=14.5, fontweight="bold", color=INK)
    figure.text(0.008, 0.855,
                f"{len(data):,} experiments from {data.doi.nunique()} papers, "
                f"{data.catalyst_smiles.nunique()} distinct catalyst structures, "
                f"{(data.phase == 'uncatalysed').sum()} of them uncatalysed baseline runs.",
                fontsize=10.5, color=DIM)
    figure.text(0.008, 0.795,
                f"Half the rows carry no yield. The subset complete enough to model — yield, "
                f"temperature, time and both masses — is {modelable.sum()} rows from "
                f"{data[modelable].doi.nunique()} papers.",
                fontsize=10.5, color=WARN)

    out = ARTIFACTS / "figures" / "fig8_release.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png")
    print(f"  {len(data):,} rows, {data.doi.nunique()} papers, "
          f"{data.catalyst_smiles.nunique()} structures, modelable core {modelable.sum()}")


if __name__ == "__main__":
    main()
