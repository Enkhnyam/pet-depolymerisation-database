"""Figure 2 -- does the extracted database behave like chemistry?

Each panel is a relationship a chemist can check without any ground truth. Route is the colour
throughout, so the eye carries the same meaning across the whole canvas.

Numbers come from checks/database/chemistry.py, which prints the same correlations.
"""
import numpy as np

from _style import DIM, ROUTE, canvas, save, scatter
from database import chemistry as chem

ROUTES = ["glycolysis", "hydrolysis", "methanolysis"]


YIELD_CAP = 105     # a yield above 100% is an extraction error, not a measurement


def by_route(axis, frame, x, y, logx=False, logy=False):
    """One scatter per route, drawn largest-group-first so small routes stay visible."""
    for route in ROUTES:
        part = frame[frame.route == route][[x, y]].dropna()
        part = part[(part[x] > 0) & (part[y] > 0)] if logx or logy else part
        if len(part):
            scatter(axis, part[x], part[y], ROUTE[route], label=route)
    if logx:
        axis.set_xscale("log")
    if logy:
        axis.set_yscale("log")


def trend(axis, frame, x, y, logx=False):
    """A rolling median through the cloud -- the shape, without implying a fitted model."""
    part = frame[[x, y]].dropna()
    part = part[(part[x] > 0)] if logx else part
    if len(part) < 40:
        return
    part = part.sort_values(x)
    window = max(20, len(part) // 12)
    axis.plot(part[x], part[y].rolling(window, center=True, min_periods=window // 2).median(),
              color=DIM, lw=1.1, ls="--", zorder=3)


def main() -> None:
    result = chem.compute()
    frame = result["records"]

    figure, panel = canvas(2, 4, width=9.2, height=4.6)

    by_route(panel[0], frame, "temperature_c", "yield_percent")
    trend(panel[0], frame, "temperature_c", "yield_percent")
    panel[0].set_xlabel("temperature (°C)"); panel[0].set_ylabel("yield (%)")

    by_route(panel[1], frame, "reaction_time_min", "yield_percent", logx=True)
    trend(panel[1], frame, "reaction_time_min", "yield_percent", logx=True)
    panel[1].set_xlabel("reaction time (min)"); panel[1].set_ylabel("yield (%)")

    by_route(panel[2], frame, "temperature_c", "reaction_time_min", logy=True)
    panel[2].set_xlabel("temperature (°C)"); panel[2].set_ylabel("reaction time (min)")

    by_route(panel[3], frame, "catalyst_amount_g", "yield_percent", logx=True)
    panel[3].set_xlabel("catalyst (g)"); panel[3].set_ylabel("yield (%)")

    # the identity panel: yield cannot exceed conversion, so nothing may sit above the diagonal
    by_route(panel[4], frame, "conversion_percent", "yield_percent")
    panel[4].plot([0, 100], [0, 100], color="#A33A2E", lw=1, ls="--", zorder=3)
    impossible = result["identity"]["yield above conversion"]
    panel[4].text(0.04, 0.93, f"{impossible} above the line", transform=panel[4].transAxes,
                  fontsize=6, color="#A33A2E")
    panel[4].set_xlabel("conversion (%)"); panel[4].set_ylabel("yield (%)")

    order = [r for r in ROUTES if (frame.route == r).any()]
    capped = frame[frame.yield_percent <= 100]
    panel[5].boxplot([capped[capped.route == r].yield_percent.dropna() for r in order],
                     tick_labels=[r[:5] for r in order], showfliers=False, widths=0.6,
                     medianprops=dict(color="#12201F"))
    panel[5].set_ylabel("yield (%)"); panel[5].set_xlabel("route")

    classes = result["by catalyst class"].index.tolist()[:5]
    panel[6].boxplot([capped[capped["catalyst class"] == c].yield_percent.dropna() for c in classes],
                     tick_labels=[c.split()[0] for c in classes], showfliers=False, widths=0.6,
                     medianprops=dict(color="#12201F"))
    panel[6].set_ylabel("yield (%)"); panel[6].set_xlabel("catalyst class")
    panel[6].tick_params(axis="x", labelrotation=30)

    by_route(panel[7], frame, "catalyst per g PET", "yield_percent", logx=True)
    trend(panel[7], frame, "catalyst per g PET", "yield_percent", logx=True)
    panel[7].set_xlabel("catalyst per g PET"); panel[7].set_ylabel("yield (%)")

    # 18 records report a yield above 100%, which is impossible; they come from two papers and
    # would otherwise stretch four y-axes to 460%. Capped and counted rather than silently kept.
    over = int((frame.yield_percent > 100).sum())
    for index in (0, 1, 3, 7):
        panel[index].set_ylim(-4, YIELD_CAP)
    panel[0].text(0.03, 0.04, f"{over} yields > 100%, off scale",
                  transform=panel[0].transAxes, fontsize=5.6, color="#A33A2E")

    # one legend for the whole canvas, so no panel loses points behind a key
    handles, labels = panel[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=len(labels), markerscale=1.6,
                  handletextpad=0.25, columnspacing=1.4, bbox_to_anchor=(0.5, 1.02))
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    save(figure, "fig2_chemistry")


if __name__ == "__main__":
    main()
