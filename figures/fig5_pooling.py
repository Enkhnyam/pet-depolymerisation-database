"""Why a line fitted through every row points the wrong way.

The dataset's temperature-yield relationship is positive inside a paper and negative across
papers. This figure shows both on one canvas, which is the only honest way to draw it: the
per-paper segments and the pooled fit are the same data, and they disagree.

What the panels argue, in order:

  a  every paper's own trend, drawn over the temperature range that paper actually scanned,
     against the line a pooled fit would learn. Most segments rise; the pooled line falls. The
     segments are short and far apart, which is the mechanism -- a paper scans a median of 18 C
     while the papers themselves are 83 C apart, so a pooled fit is dominated by the gaps
     between studies rather than by anything measured inside one.

  b  the slope, split by how each paper defines yield. This is what IS consistent: every
     definition class has a positive median slope. Heating helps regardless of how you count
     the product.

  c  the level, split the same way. This is what is NOT consistent, and what the definition
     explains: a mass-basis paper reports about half the number a molar-basis paper does for
     the same chemistry, because BHET weighs 254 g/mol and the PET unit it came from weighs 192.

Taken together: separating by yield definition corrects the LEVEL, not the SLOPE, and therefore
does not on its own make a pooled fit valid. The paper grouping is what does that.

The yield-basis annotation is artifacts/data/yield_basis.csv, read from the methods section of
each source paper. It is a CSV so it can be checked rather than trusted.

    fig5_pooling.py            artifacts/figures/fig5_pooling.pdf
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import (CYCLE, DIM, GUIDE, INK, NEUTRAL, RULE, WARN, canvas, plt, save)
from core.paths import ARTIFACTS

HOMO = ARTIFACTS / "release" / "pet_homogeneous.xlsx"
ANNOT = ARTIFACTS / "data" / "yield_basis.csv"

# molar is the commonest and the reference; unstated is not a class, so it takes the neutral ink
BASIS_ORDER = ["molar", "mass", "other", "petloss", "unstated"]
BASIS_COLOUR = {"molar": CYCLE[0], "mass": CYCLE[1], "other": CYCLE[2],
                "petloss": CYCLE[3], "unstated": NEUTRAL}
LABEL = {"molar": "molar", "mass": "mass", "other": "assay", "petloss": "PET loss",
         "unstated": "not stated"}

MIN_ROWS = 1          # no minimum: the only filter is "has a yield and a temperature"
MIN_LEVELS = 3        # and this many distinct temperatures before it has a slope worth fitting


def load() -> pd.DataFrame:
    frame = pd.read_excel(HOMO, sheet_name="Data")
    frame = frame.dropna(subset=["yield_percent", "temperature_c"])
    # Twelve rows report a yield above 100%, all from one paper that defines "yield" as a ratio
    # of titration acid numbers. They are a documented error rather than evidence, and left in
    # they alone drag the pooled fit from negative to flat -- which would understate the point
    # by making the pooled line merely wrong-magnitude instead of wrong-signed.
    frame = frame[frame.yield_percent <= 100]
    keep = frame.groupby("doi").size()[lambda s: s >= MIN_ROWS].index
    frame = frame[frame.doi.isin(keep)].copy()

    annot = pd.read_csv(ANNOT).set_index("doi").yield_basis
    frame["basis"] = frame.doi.map(annot).fillna("unstated").replace("", "unstated")
    return frame


def per_paper(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per paper: the range it scanned, its own slope, its own level."""
    out = []
    for doi, group in frame.groupby("doi"):
        pair = group[["temperature_c", "yield_percent"]].dropna()
        levels = pair.temperature_c.nunique()
        slope = (np.polyfit(pair.temperature_c, pair.yield_percent, 1)[0]
                 if levels >= MIN_LEVELS else np.nan)
        out.append({"doi": doi, "basis": group.basis.iat[0], "n": len(pair),
                    "tmin": pair.temperature_c.min(), "tmax": pair.temperature_c.max(),
                    "tmed": pair.temperature_c.median(), "ymed": pair.yield_percent.median(),
                    "slope": slope, "levels": levels})
    return pd.DataFrame(out)


def spaghetti(axis, frame, papers):
    """Each paper's own trend, over the range it actually scanned, against the pooled fit."""
    axis.scatter(frame.temperature_c, frame.yield_percent, s=5, alpha=0.13,
                 linewidths=0, color=NEUTRAL, zorder=1)

    # unstated last and thinner, so the classes we actually read out of the papers stay in front
    scanning = papers.dropna(subset=["slope"])
    scanning = scanning.assign(_o=scanning.basis.eq("unstated")).sort_values("_o")
    for row in scanning.itertuples():
        part = frame[frame.doi == row.doi]
        fit = np.polyfit(part.temperature_c, part.yield_percent, 1)
        span = np.array([row.tmin, row.tmax])
        quiet = row.basis == "unstated"
        axis.plot(span, np.polyval(fit, span), lw=1.0 if quiet else 1.7,
                  alpha=0.40 if quiet else 0.9, solid_capstyle="round",
                  color=BASIS_COLOUR[row.basis], zorder=2 if quiet else 3)

    # the line a pooled fit learns from exactly the same points
    pooled = np.polyfit(frame.temperature_c, frame.yield_percent, 1)
    grid = np.array([frame.temperature_c.min(), frame.temperature_c.max()])
    axis.plot(grid, np.polyval(pooled, grid), color=WARN, lw=2.2, ls="--", zorder=5,
              label=f"pooled across all  {pooled[0]:+.3f} %/°C")

    rising = int((scanning.slope > 0).sum())
    # The comparison goes in the legend rather than floating over the data: this panel is dense
    # everywhere, and a text block placed anywhere inside it lands on a segment.
    typical = plt.Line2D([], [], color=CYCLE[0], lw=1.7,
                         label=f"within a paper   {scanning.slope.median():+.2f} %/°C"
                               f"   ({rising} of {len(scanning)} rise)")
    handle, _ = axis.get_legend_handles_labels()
    axis.legend(handles=[typical, handle[0]], loc="lower left", handletextpad=0.6,
                borderpad=0.4, labelspacing=0.5, prop={"family": "monospace", "size": 6.2})
    axis.set_xlabel("reaction temperature (°C)")
    axis.set_ylabel("reported yield (%)")
    axis.set_ylim(-3, 103)
    axis.set_xlim(0, 300)


def by_class(axis, papers, column, *, zero_line, xlabel):
    """One class per row: the papers as points, the class median as a bar."""
    present = [b for b in BASIS_ORDER if papers[papers.basis == b][column].notna().sum()]
    rng = np.random.default_rng(0)
    for index, basis in enumerate(present):
        values = papers[papers.basis == basis][column].dropna()
        y = index + rng.uniform(-0.13, 0.13, len(values))
        axis.scatter(values, y, s=16, alpha=0.6, linewidths=0, color=BASIS_COLOUR[basis], zorder=3)
        axis.plot([values.median()] * 2, [index - 0.30, index + 0.30],
                  color=INK, lw=1.8, zorder=4)
        axis.text(0.99, index + 0.33, f"n={len(values)}", transform=axis.get_yaxis_transform(),
                  ha="right", va="bottom", fontsize=5.8, color=DIM)
    if zero_line:
        axis.axvline(0, color=WARN, lw=1, ls="--", zorder=2)
    axis.set_yticks(range(len(present)))
    axis.set_yticklabels([LABEL[b] for b in present])
    axis.set_ylim(-0.6, len(present) - 0.4)
    axis.invert_yaxis()
    axis.set_xlabel(xlabel)
    axis.set_ylabel("how the paper defines yield")


CAPTION = """\
**Figure 5. A line fitted across papers points the wrong way.**
(a) Every paper's own temperature-yield trend, drawn only over the range that paper scanned,
coloured by how the paper defines yield; faint points are the {rows:,} underlying records
(twelve records reporting a yield above 100% are excluded as a documented error).
{rising} of {scanning} papers that vary temperature show a rising trend, at a median
{within} % yield per °C, yet a fit through all the same points has the opposite sign
({pooled} % yield per °C). The segments are short and far apart -- a paper scans a median of
{span:.0f} °C while paper medians are spread over {spread:.0f} °C -- so the pooled fit is governed by
the gaps between studies rather than by anything measured within one.
(b) The slope is positive in every definition class, so heating helps however the product is
counted. (c) The level is not: a mass-basis paper reports a median {mass:.0f}% where a
molar-basis paper reports {molar:.0f}%, consistent with the 254/192 g mol⁻¹ ratio between BHET
and the PET repeat unit. Separating by definition therefore corrects the level and leaves the
pooled slope wrong; grouping by paper is what recovers the chemistry.
Yield definitions were read from the methods section of each source paper
(artifacts/data/yield_basis.csv); {unstated} of {total} papers state none."""


def main() -> None:
    frame = load()
    papers = per_paper(frame)

    figure, panel = canvas(1, 3, width=10.4)
    spaghetti(panel[0], frame, papers)
    handles = [plt.Line2D([], [], color=BASIS_COLOUR[b], lw=2.4, label=LABEL[b])
               for b in BASIS_ORDER if (papers.basis == b).any()]
    figure.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False,
                  bbox_to_anchor=(0.5, 1.03), handletextpad=0.5, columnspacing=1.6,
                  fontsize=6.8, title="how the paper defines yield", title_fontsize=6.8)
    by_class(panel[1], papers, "slope", zero_line=True,
             xlabel="slope within the paper (% yield per °C)")
    by_class(panel[2], papers, "ymed", zero_line=False,
             xlabel="the paper's median reported yield (%)")
    save(figure, "fig5_pooling", legend_room=True)

    scanning = papers.dropna(subset=["slope"])
    pooled = np.polyfit(frame.temperature_c, frame.yield_percent, 1)[0]
    span = (papers.tmax - papers.tmin).median()
    print(CAPTION.format(
        rows=len(frame), rising=int((scanning.slope > 0).sum()), scanning=len(scanning),
        pooled=f"{pooled:+.3f}", within=f"{scanning.slope.median():+.2f}",
        span=span, spread=papers.tmed.std(),
        mass=papers[papers.basis == "mass"].ymed.median(),
        molar=papers[papers.basis == "molar"].ymed.median(),
        unstated=int((papers.basis == "unstated").sum()), total=len(papers)))

    print("\nslope by definition class (median % yield per °C):")
    print(scanning.groupby("basis").slope.agg(papers="size", median="median").to_string())


if __name__ == "__main__":
    main()
