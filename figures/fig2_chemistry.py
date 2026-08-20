"""Figure 2 -- does the extracted database behave like chemistry?

Each panel is a relationship a chemist can check without any ground truth. Route is the colour
throughout, so the eye carries one meaning across the whole canvas.

Numbers come from checks/database/chemistry.py, which prints the same correlations.
"""
from _style import ROUTE, WARN, box, canvas, legend_above, note, points, save
from database import chemistry as chem

ROUTES = ["glycolysis", "hydrolysis", "methanolysis"]
YIELD = (-4, 105)          # a yield above 100% is an extraction error, not a measurement


def main() -> None:
    result = chem.compute()
    frame = result["records"]
    plausible = frame[frame.yield_percent.isna() | (frame.yield_percent <= 100)]

    figure, panel = canvas(2, 4, width=9.2, height=4.6)
    route = dict(colour_by="route", palette=ROUTE, order=ROUTES)

    points(panel[0], frame, "temperature_c", "yield_percent", **route, trend=True,
           xlabel="temperature (°C)", ylabel="yield (%)", ylim=YIELD, legend=True)
    points(panel[1], frame, "reaction_time_min", "yield_percent", **route, trend=True, logx=True,
           xlabel="reaction time (min)", ylabel="yield (%)", ylim=YIELD)
    points(panel[2], frame, "temperature_c", "reaction_time_min", **route, logy=True,
           xlabel="temperature (°C)", ylabel="reaction time (min)",
           title="hotter runs finish sooner")
    points(panel[3], frame, "catalyst_amount_g", "yield_percent", **route, logx=True,
           xlabel="catalyst (g)", ylabel="yield (%)", ylim=YIELD)

    # the identity panel: yield cannot exceed conversion, so nothing may sit above the diagonal
    points(panel[4], frame, "conversion_percent", "yield_percent", **route,
           xlabel="conversion (%)", ylabel="yield (%)", title="yield cannot exceed conversion")
    panel[4].plot([0, 100], [0, 100], color=WARN, lw=1, ls="--", zorder=3)
    note(panel[4], f"{result['identity']['yield above conversion']} of "
                   f"{result['identity']['pairs with both']} above the line", y=0.92)

    box(panel[5], plausible, "route", "yield_percent", order=ROUTES,
        xlabel="route", ylabel="yield (%)")
    box(panel[6], plausible, "catalyst class", "yield_percent",
        order=result["by catalyst class"].index[:5].tolist(),
        xlabel="catalyst class", ylabel="yield (%)", rotate=30)
    points(panel[7], frame, "catalyst per g PET", "yield_percent", **route, trend=True, logx=True,
           xlabel="catalyst per g PET", ylabel="yield (%)", ylim=YIELD)

    over = int((frame.yield_percent > 100).sum())
    note(panel[0], f"{over} yields > 100%, off scale")
    legend_above(figure, panel[0])
    save(figure, "fig2_chemistry", legend_room=True)


if __name__ == "__main__":
    main()
