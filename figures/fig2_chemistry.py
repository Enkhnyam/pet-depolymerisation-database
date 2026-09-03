"""Figure 2 -- what the extracted conditions look like, and whether they behave.

Distributions rather than scatters: with five thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The exceptions are the last two panels, where the relationship is the point.
"""
from _style import (INK, ROUTE, ROUTES, canvas, density, histogram, legend_above,
                    paired_rho, save)
from database import chemistry as chem
from database import withinpaper as within


def main() -> None:
    result = chem.compute()
    trends = within.compute()
    frame = result["records"]
    stack = dict(split="route", palette=ROUTE, order=ROUTES)

    figure, panel = canvas(3, 3, height=5.73)

    histogram(panel[0], frame, "temperature_c", xlabel="temperature (°C)", **stack)
    histogram(panel[1], frame, "reaction_time_min", logx=True, ylabel="",
              xlabel="reaction time (min)", **stack)
    # a handful of yields exceed 100%; letting them set the axis wastes the panel
    histogram(panel[2], frame[frame.yield_percent <= 100], "yield_percent",
              xlabel="yield (%)", ylabel="", **stack)
    # from the check, not recounted: chemistry.py already publishes this and the two definitions
    # must not be allowed to drift apart
    histogram(panel[3], frame, "conversion_percent", xlabel="conversion (%)", **stack)
    histogram(panel[4], frame, "catalyst_amount_g", logx=True, xlabel="catalyst (g)",
              ylabel="", **stack)
    histogram(panel[5], frame, "PET_amount_g", logx=True, xlabel="PET (g)", ylabel="", **stack)
    histogram(panel[6], frame, "solvent_amount_g", logx=True, xlabel="solvent (g)", **stack)

    # A binned density, not a cloud of 1,400 translucent dots. The claim is that nothing sits
    # above the diagonal -- an identity, so it holds route by route trivially and needs no route
    # split -- and a density shows where the mass is, which an overplotted cloud cannot. The
    # diagonal is a solid hairline: it is a reference, and a dashed one read as data.
    density(panel[7], frame, "conversion_percent", "yield_percent",
            xlabel="conversion (%)", ylabel="yield (%)", xlim=(0, 100), ylim=(0, 100))
    panel[7].plot([0, 100], [0, 100], color=INK, lw=0.8, zorder=3)

    paired_rho(panel[8], trends["table"], trends["per paper"],
               xlabel="Spearman ρ")

    legend_above(figure, panel[0])
    save(figure, "fig2_chemistry")


if __name__ == "__main__":
    main()
