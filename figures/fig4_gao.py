"""Figure 4 -- the extraction against hand curation, on the records both describe.

Two panels, one question each.

Panel a asks whether the values agree, and it can only ask that of records both datasets
describe: the same paper, the same experiment. An earlier version overlaid our whole glycolysis
corpus -- 2,531 records from 337 papers -- on Gao's 364 from 19, which showed that a large cloud
contains a small one. That would have looked identical if we had extracted nothing at all from
their papers. This is a parity plot over the 131 matched records instead, so a point off the
diagonal is a real disagreement about a real experiment.

Panel b asks why their set is larger, which is the other half of the comparison and is a scope
decision rather than a failure. Its wedges are keyed by one word each; what a wedge means
belongs in the caption, not printed around the circle.

The other two routes had a panel each and no longer do. Neither has a curated set to compare
against, so those panels showed our own data twice and argued nothing.
"""
from _style import DATA, EMPHASIS, INK, RAMP, canvas, cloud, pie, save
from curated import gao_overlap

# The three outcomes share a 0-100 axis, so one parity panel serves all of them. A ramp step and
# a marker each: two channels, no hatch.
OUTCOMES = [("conversion_percent", "conversion", DATA, "o"),
            ("yield_percent", "BHET yield", EMPHASIS, "D"),
            ("selectivity_percent", "selectivity", RAMP[2], "^")]

# One word per wedge. The sentence explaining it goes in the caption.
REASONS = [("both", "in both", DATA),
           ("chart", "charts", RAMP[2]),
           ("si", "SI", RAMP[3]),
           ("rule", "scope", RAMP[4]),
           ("missed", "missed", EMPHASIS)]


def main() -> None:
    gao = gao_overlap.compute()
    pairs = gao["parity"]

    figure, panel = canvas(1, 2, height=2.7)

    # --- a: our value against theirs, for the same experiment --------------------------------
    axis = panel[0]
    axis.plot([0, 100], [0, 100], color=INK, lw=0.8, zorder=1)
    for field, label, colour, marker in OUTCOMES:
        part = pairs[pairs.field == field]
        cloud(axis, part.gao, part.ours, colour=colour, marker=marker, size=11,
              edge="white", label=f"{label} ({len(part)})", zorder=3)
    axis.set_xlim(-3, 103)
    axis.set_ylim(-3, 103)
    axis.set_aspect("equal")
    axis.set_xlabel("hand-curated value (%)")
    axis.set_ylabel("extracted value (%)")
    axis.legend(fontsize=5.4, loc="upper left", handletextpad=0.2, borderpad=0.2,
                borderaxespad=0.4, labelspacing=0.3)

    # --- b: why their set is larger ----------------------------------------------------------
    counts = gao["split"].reindex([key for key, _, _ in REASONS])
    counts.index = [word for _, word, _ in REASONS]
    pie(panel[1], counts, colours=[colour for _, _, colour in REASONS], gap=0.22)
    panel[1].set_xlabel(f"the {int(counts.sum())} hand-curated experiments")

    save(figure, "fig4_gao")


if __name__ == "__main__":
    main()
