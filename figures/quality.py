"""Figure 3 -- how far we can vouch for the database.

Every panel draws numbers imported from the check that prints them, so the figure and
`scripts/results_curated.sh` cannot disagree. Nothing is recomputed here.
"""
import numpy as np

from _style import GRADER, SEQUENTIAL, canvas, save
from curated import matrix as matrix_check


def agreement_heatmap(axis, frame, column, title):
    grid = frame.pivot(index="judge", columns="extraction", values=column)
    image = axis.imshow(grid.values, cmap=SEQUENTIAL, vmin=0.6, vmax=1.0, aspect="auto")

    axis.set_xticks(range(len(grid.columns)), grid.columns)
    axis.set_yticks(range(len(grid.index)), grid.index)
    axis.set_xlabel("extraction")
    # get_title() reads the centre title; the panel letter was set with loc="left"
    axis.set_title(f"{axis.get_title(loc='left')}   {title}", loc="left", fontsize=8)

    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            value = grid.values[i, j]
            axis.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=6.5,
                      color="white" if value > 0.85 else "#12201F")
    return image


def main() -> None:
    frame = matrix_check.compute()          # the same numbers curated/matrix.py prints

    figure, panels = canvas(1, 2, width=6.4, height=2.6)
    agreement_heatmap(panels[0], frame, "agreement", "every record")
    panels[0].set_ylabel("judge")
    image = agreement_heatmap(panels[1], frame, "agreement, evaluable",
                              "records the metric could evaluate")
    figure.colorbar(image, ax=panels, fraction=0.03, pad=0.02, label="agreement")
    save(figure, "fig3_quality")


if __name__ == "__main__":
    main()
