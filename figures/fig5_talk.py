"""One panel that explains the pooling problem to someone who has not read the paper.

fig5_pooling.py is the manuscript figure: three panels, small type, argued in a caption.
This is the version for a slide or a supervisor meeting, where nobody reads a caption and the
picture has to carry the whole argument on its own.

Three decisions make it readable without explanation:

  colour encodes the answer, not the category. A paper whose own yield rises with temperature
  is teal, one whose yield falls is rose. The reader counts colours instead of reading a
  legend, and the count IS the finding: 23 of 29 rise.

  every segment is drawn only across the temperature range that paper actually scanned, so the
  gaps between segments are visible. Those gaps are the mechanism -- 18 C scanned inside a
  paper against 83 C between papers -- and a figure that hid them by extending the lines would
  be hiding the point.

  the callouts are sentences, not labels. "each short line is one paper's own experiments" is
  what a first-time reader needs; "per-paper OLS fit" is not.

    fig5_talk.py               artifacts/figures/fig5_talk.pdf
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, NEUTRAL, RULE, WARN, plt, save
from core.paths import ARTIFACTS

HOMO = ARTIFACTS / "release" / "pet_homogeneous.xlsx"

RISE, FALL = CYCLE[0], CYCLE[1]        # teal, rose
# No minimum row count: the only filter is "has a yield and a temperature".
# A segment still needs three distinct temperatures, because a paper that ran
# everything at one temperature has no slope to draw -- that is a fact about the
# paper, not a selection we made.
MIN_ROWS, MIN_LEVELS = 1, 3


def load():
    frame = pd.read_excel(HOMO, sheet_name="Data")
    frame = frame.dropna(subset=["yield_percent", "temperature_c"])
    frame = frame[frame.yield_percent <= 100]          # twelve documented-bad rows
    keep = frame.groupby("doi").size()[lambda s: s >= MIN_ROWS].index
    return frame[frame.doi.isin(keep)].copy()


def main() -> None:
    frame = load()

    # Bigger type than the manuscript figures: this one is read from across a room.
    plt.rcParams.update({"font.size": 10, "axes.labelsize": 11.5,
                         "xtick.labelsize": 10, "ytick.labelsize": 10})
    figure, axis = plt.subplots(figsize=(9.8, 7.1))
    # Explicit margins rather than tight_layout: the headline block lives in figure coordinates
    # above the axes, and tight_layout does not know it is there.
    figure.subplots_adjust(top=0.715, left=0.075, right=0.975, bottom=0.095)

    axis.scatter(frame.temperature_c, frame.yield_percent, s=8, alpha=0.08,
                 linewidths=0, color=NEUTRAL, zorder=1)

    segments = []
    for doi, group in frame.groupby("doi"):
        pair = group[["temperature_c", "yield_percent"]].dropna()
        if pair.temperature_c.nunique() < MIN_LEVELS:
            continue
        fit = np.polyfit(pair.temperature_c, pair.yield_percent, 1)
        span = np.array([pair.temperature_c.min(), pair.temperature_c.max()])
        # A steep fit over a wide scan extrapolates below zero at the cold end. Clipping to the
        # possible range keeps the slope honest and stops segments leaving the axes.
        segments.append((span, np.clip(np.polyval(fit, span), 0, 100), fit[0]))

    for span, values, slope in segments:
        colour = RISE if slope > 0 else FALL
        axis.plot(span, values, lw=2.6, alpha=0.88, color=colour,
                  solid_capstyle="round", zorder=3)
        # a dot at the hot end gives every segment a direction the eye can follow
        axis.scatter(span[1], values[1], s=28, color=colour, zorder=4, linewidths=0)

    rising = sum(1 for *_, slope in segments if slope > 0)
    drawn_span = np.median([span[1] - span[0] for span, *_ in segments])
    # How many papers cannot appear at all, and why. This is not a caveat about the figure;
    # it is the finding stated in its strongest form.
    levels = frame.groupby("doi").temperature_c.nunique()
    single = int((levels == 1).sum())
    within = np.median([slope for *_, slope in segments])
    pooled = np.polyfit(frame.temperature_c, frame.yield_percent, 1)
    axis.plot(np.array([18, 288]), np.polyval(pooled, np.array([18, 288])),
              color=WARN, lw=3.8, ls=(0, (7, 4)), zorder=6, solid_capstyle="round")

    axis.set_xlabel("reaction temperature (°C)")
    axis.set_ylabel("reported yield (%)")
    axis.set_xlim(0, 300)
    axis.set_ylim(-3, 103)
    axis.set_yticks([0, 20, 40, 60, 80, 100])
    axis.spines["left"].set_bounds(0, 100)
    axis.grid(axis="y", color=RULE, lw=0.6, alpha=0.5, zorder=0)
    axis.set_axisbelow(True)

    figure.text(0.012, 0.945, "Heat helps inside almost every paper.",
                fontsize=16, fontweight="bold", color=INK)
    figure.text(0.012, 0.885, "Pool the papers together and the effect flips sign.",
                fontsize=16, fontweight="bold", color=WARN)
    # One text object rather than two: separate figure.text calls at hand-picked y positions
    # collide the moment the wording changes length.
    figure.text(0.012, 0.755,
                "Each short line is one paper's own experiments, drawn only across the "
                "temperatures that paper actually tested.\n"
                f"Only {len(segments)} of the {len(levels)} papers with a usable yield tested more than two "
                f"temperatures — {single} ran every experiment at a single one.\n"
                "That is the problem in one sentence: the dashed line is fitted across the gaps "
                "between studies, not across anything a chemist varied.",
                fontsize=10.5, color=DIM, linespacing=1.65, va="bottom")

    # Points at the cold end of the pooled line, into the emptiest corner of the panel.
    axis.annotate("one line fitted through every record,\nignoring which paper each came from",
                  xy=(52, np.polyval(pooled, 52)), xytext=(9, 9),
                  fontsize=10.5, color=WARN, va="bottom", ha="left", zorder=8,
                  bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=RULE, lw=0.9),
                  arrowprops=dict(arrowstyle="->,head_width=0.28,head_length=0.6",
                                  color=WARN, lw=1.3, alpha=0.85,
                                  connectionstyle="arc3,rad=-0.12", shrinkA=6, shrinkB=4))

    key = (r"$\bf{" + str(rising) + r"\ of\ " + str(len(segments)) + r"}$ papers rise"
           + "          median  " + r"$\bf{+" + f"{within:.2f}" + r"}$ % per °C" + "\n"
           + "the pooled line falls          "
           + r"$\bf{" + f"{pooled[0]:+.3f}" + r"}$ % per °C")
    axis.text(0.982, 0.045, key, transform=axis.transAxes, ha="right", va="bottom",
              fontsize=11, color=INK, linespacing=1.9,
              bbox=dict(boxstyle="round,pad=0.7", fc="#F4F8F7", ec=RULE, lw=1.0), zorder=9)

    handles = [plt.Line2D([], [], color=RISE, lw=2.8, marker="o", markersize=6.5,
                          label=f"yield rises with heat   {rising} papers"),
               plt.Line2D([], [], color=FALL, lw=2.8, marker="o", markersize=6.5,
                          label=f"yield falls   {len(segments) - rising} papers")]
    axis.legend(handles=handles, loc="upper left", fontsize=10.5, frameon=False,
                handlelength=2.4, labelspacing=0.6, borderaxespad=0.9)

    out = ARTIFACTS / "figures" / "fig5_talk.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png")
    print(f"{rising} of {len(segments)} rise; within {within:+.2f}; "
          f"pooled {pooled[0]:+.4f}; drawn span {drawn_span:.0f} C")


if __name__ == "__main__":
    main()
