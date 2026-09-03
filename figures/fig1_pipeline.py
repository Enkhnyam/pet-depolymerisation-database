"""Figure 1 -- the pipeline, as a flow diagram with the real counts on it.

The manuscript has referenced this figure since the first draft, as `fig1.pdf` under a caption
reading "Overview of the full pipeline. XXXX", and no module ever drew it. It is a schematic
rather than a plot, so nothing about it is fitted or measured -- but every number written on it
comes from the same checks as every other figure, which is the only reason it belongs in the
generated set instead of in an illustrator's file.

Panels carry only their letter; what each is for belongs in the caption, which this prints.
"""
import matplotlib.patches as patches

from _style import CYCLE, DIM, GUIDE, INK, NEUTRAL, RULE, canvas, caption, save
from database import corpus as corpus_check
from database import verdicts as verdicts_check

CAPTION = r"""\textbf{How the database is built and audited.}
\textbf{a} Corpus assembly. A Scopus query returns __CANDIDATES__ candidate articles; title and
abstract screening against the scope -- PET, a named depolymerisation route, not a review --
keeps __FILTERED__, of which __CONVERTED__ could be obtained in full text and converted to
chunked markdown. The drop is licensing rather than relevance: we hold a text-and-data-mining
entitlement with one publisher.

\textbf{b} Extraction and audit, the two phases the paper measures separately. An extraction
model reads each paper's chunks under a fixed 12-field schema and writes one record per
experiment, optionally citing the chunk each value came from. A second, independent judge model
then reads the same paper alongside each record and returns a verdict: accept as written, accept
with named field corrections and the text supporting them, or reject outright. Over the
__JUDGED__ judged records the judge accepted __ACCEPTED__ (__PASSRATE__\%), corrected
__CORRECTED__ and rejected __DROPPED__. No human is in either loop; the human labels enter only
where the graders are themselves being scored (Fig.~\ref{fig:graders}).

The judge never grades its own output -- the extraction and judge models are always a different
pair -- and every record carries the DOI and chunk identifiers it was read from, so any value in
the release can be traced back to a sentence."""

# Phase b, as (label, sublabel) boxes left to right. The schematic is the argument, so the boxes
# say what happens and the numbers underneath say how much of it happened.
INK_ON = dict(ha="center", va="center", color=INK)


def box(axis, x, y, w, h, title, detail, *, edge=RULE, face="white", lw=1.0):
    axis.add_patch(patches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=lw, edgecolor=edge, facecolor=face, zorder=2))
    axis.text(x + w / 2, y + h * 0.62, title, fontsize=7, fontweight="bold", zorder=3, **INK_ON)
    if detail:
        axis.text(x + w / 2, y + h * 0.26, detail, fontsize=6, ha="center", va="center",
                  color=DIM, zorder=3)


def arrow(axis, x0, y0, x1, y1, *, colour=DIM):
    axis.annotate("", (x1, y1), (x0, y0), zorder=1,
                  arrowprops=dict(arrowstyle="-|>,head_width=0.18,head_length=0.4",
                                  color=colour, lw=0.9, shrinkA=1, shrinkB=1))


def blank(axis):
    # a little past the unit square: a rounded box at x=1.0 is clipped in half by the axes edge
    axis.set_xlim(-0.02, 1.02)
    axis.set_ylim(-0.02, 1.02)
    axis.axis("off")


def main() -> None:
    corpus = corpus_check.compute()
    judged = verdicts_check.compute()
    funnel, counts = corpus["funnel"], judged["counts"]

    figure, panel = canvas(2, 1, width=8.4, height=3.6)
    top, bottom = panel

    # --- a: the funnel, as three boxes narrowing left to right -------------------------------
    blank(top)
    stages = [("Scopus query", funnel["candidates found"], "candidates"),
              ("scope screening", funnel["passed the filter"], "in scope"),
              ("full text obtained", funnel["converted to chunked text"], "converted"),
              ("chunked corpus", funnel["extracted so far"], "papers read")]
    gap = 0.045
    width = (1 - gap * (len(stages) - 1)) / len(stages)
    biggest = max(count for _, count, _ in stages)
    for i, (title, count, unit) in enumerate(stages):
        x = i * (width + gap)
        # the box height tracks the count, so the funnel is visible before a number is read
        height = 0.22 + 0.56 * count / biggest
        box(top, x, 0.10, width, height, title, f"{count:,} {unit}")
        if i:
            arrow(top, x - gap - 0.004, 0.32, x + 0.004, 0.32)

    # --- b: extract, then judge --------------------------------------------------------------
    blank(bottom)
    box(bottom, 0.0, 0.30, 0.22, 0.42, "extraction model",
        "12-field schema\none record per experiment", edge=CYCLE[0], lw=1.3)
    box(bottom, 0.30, 0.30, 0.22, 0.42, "judge model",
        "reads the paper beside\neach record, field by field", edge=CYCLE[1], lw=1.3)
    arrow(bottom, 0.22, 0.51, 0.30, 0.51)
    bottom.text(0.26, 0.75, f"{counts['records judged']:,}\nrecords", fontsize=5.8,
                ha="center", va="bottom", color=DIM)

    verdict = [("accepted", counts["accepted"], NEUTRAL),
               ("corrected", counts["rejected, with a correction"], CYCLE[2]),
               ("rejected", counts["rejected outright"], CYCLE[3])]
    for i, (name, count, colour) in enumerate(verdict):
        y = 0.86 - i * 0.35
        box(bottom, 0.62, y - 0.13, 0.16, 0.26, name, f"{count:,}", edge=colour)
        arrow(bottom, 0.52, 0.51, 0.62, y, colour=colour)
        if name != "rejected":
            arrow(bottom, 0.78, y, 0.86, 0.51, colour=colour)

    box(bottom, 0.86, 0.30, 0.14, 0.42, "release",
        "records, audit\nand changelog", edge=RULE)

    save(figure, "fig1_pipeline")
    print("\n" + caption(
        CAPTION,
        candidates=f"{funnel['candidates found']:,}",
        filtered=f"{funnel['passed the filter']:,}",
        converted=f"{funnel['converted to chunked text']:,}",
        judged=f"{counts['records judged']:,}",
        accepted=f"{counts['accepted']:,}",
        passrate=f"{judged['pass rate'] * 100:.1f}",
        corrected=f"{counts['rejected, with a correction']:,}",
        dropped=f"{counts['rejected outright']:,}"))


if __name__ == "__main__":
    main()
