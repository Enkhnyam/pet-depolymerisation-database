"""Figure 4 -- why the hand-curated set lists more experiments than we extract.

One panel. The parity comparison that used to sit beside it is Figure 2 panel i now, where it
belongs: it is a test of the extracted conditions, and that is what Figure 2 is about.

What is left is the other half of the comparison, and it is a scope question rather than a
quality one. Gao et al.'s 364 curated glycolysis experiments decompose into exactly five
reasons, one per record, assigned by a chemist reading the paper. Most of the difference is
values read off a plotted curve, which the prompt tells the model to ignore in favour of tables.

Drawn single-column: it is one circle, and a double-column float around it was mostly margin.
"""
from _style import DATA, EMPHASIS, RAMP, SINGLE_COLUMN, canvas, pie, save
from curated import gao_overlap

# The wedge labels stay as sentences rather than one-word keys. Shortening them to "charts",
# "SI", "scope" made the panel tidier and the figure less readable on its own, which is the
# wrong trade for the one panel a reader meets without the caption in hand.
REASONS = [("both", "in both datasets", DATA),
           ("chart", "read off a plotted curve", RAMP[2]),
           ("si", "in Supporting Information we do not hold", RAMP[3]),
           ("rule", "a design table outside our scope", RAMP[4]),
           ("missed", "tabulated in text we read", EMPHASIS)]


def main() -> None:
    gao = gao_overlap.compute()

    figure, panel = canvas(1, 1, width=SINGLE_COLUMN, height=2.1)
    axis = panel[0]
    axis.set_title("")          # one panel needs no letter

    counts = gao["split"].reindex([key for key, _, _ in REASONS])
    counts.index = [label for _, label, _ in REASONS]
    pie(axis, counts, colours=[colour for _, _, colour in REASONS], gap=0.30)
    axis.set_xlabel(f"the {int(counts.sum())} hand-curated experiments")

    save(figure, "fig4_gao")


if __name__ == "__main__":
    main()
