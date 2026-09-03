"""Figure 4 -- the database against hand curation, and the test that outlives it.

Gao et al. curated 364 ionic-liquid glycolysis experiments by hand. It is the only external
reference this work has and the only one it will get: nobody has hand-curated hydrolysis or
methanolysis at this scale. Panels a and b are that comparison. Panel c is the argument that
reaches all three routes without any external reference at all, which is why it is here rather
than in a figure of its own.

Every mark is a step of _style.RAMP. Nothing is hatched.
"""
from _style import (DIM, EMPHASIS, INK, RAMP, ROUTE, ROUTES, RULE, WASH, canvas,
                    marker_for, ranked_bars, save)
from curated import gao_overlap
from database import withinpaper

# Why a curated record is or is not in ours, in the order the argument runs: agreed, then three
# kinds of explained, then ours. Five reasons, five steps of the ramp, one each. The shortfall
# takes the darkest step rather than a red one -- it is the number that matters, not an alarm.
GAP = [("both", "in both", RAMP[1]),
       ("chart", "read off a chart", RAMP[2]),
       ("si", "in SI we lack", RAMP[3]),
       ("rule", "a design table we skip", RAMP[4]),
       ("missed", "in a table we read", EMPHASIS)]

FIELDS = {"temperature_c": "temperature", "reaction_time_min": "reaction time",
          "catalyst_amount_g": "catalyst mass", "PET_amount_g": "PET mass",
          "solvent_amount_g": "solvent mass", "yield_percent": "BHET yield",
          "conversion_percent": "conversion", "selectivity_percent": "selectivity",
          "catalyst": "catalyst name", "solvent": "solvent name"}


def main() -> None:
    gao = gao_overlap.compute()
    trends = withinpaper.by_route()

    figure, panel = canvas(1, 3, height=2.5)

    # --- a: where the two datasets overlap, do they agree ------------------------------------
    agree = gao["agreement"]
    shares = (agree.share * 100).rename(index=FIELDS)
    ranked_bars(panel[0], shares, colour=RAMP[1], fmt="{:.0f}%",
                xlabel="fields agreeing, of the records both hold")
    # the denominator, because 90% of 58 records and 90% of 127 are different claims
    for position, name in enumerate(shares.sort_values().index):
        field = next(k for k, v in FIELDS.items() if v == name)
        panel[0].annotate(f"n={int(agree.loc[field, 'both report it'])}",
                          (0, position), textcoords="offset points", xytext=(3, 0),
                          fontsize=4.8, color="white", va="center", ha="left")

    # --- b: and where they do not, why -------------------------------------------------------
    total = int(gao["split"].sum())
    for position, (key, label, colour) in enumerate(GAP):
        count = int(gao["split"][key])
        panel[1].barh([len(GAP) - 1 - position], [count], height=0.6, color=colour)
        panel[1].annotate(f"{count}  ({count / total:.0%})",
                          (count, len(GAP) - 1 - position), textcoords="offset points",
                          xytext=(4, 0), fontsize=5.4, va="center",
                          color=EMPHASIS if key == "missed" else DIM,
                          fontweight="bold" if key == "missed" else "normal")
    panel[1].set_yticks(range(len(GAP))[::-1], [label for _, label, _ in GAP], fontsize=5.6)
    panel[1].set_xlim(0, int(gao["split"].max()) * 1.45)
    panel[1].set_xticks([])
    panel[1].spines["bottom"].set_visible(False)
    panel[1].set_xlabel(f"of the {total} curated experiments")

    # --- c: the test that needs no external reference, in every route ------------------------
    axis = panel[2]
    relationships = list(trends[ROUTES[0]]["table"].index)
    axis.axvline(0, color=INK, lw=0.8, zorder=3)
    for position, name in enumerate(relationships[::-1]):
        expected = trends[ROUTES[0]]["table"].loc[name, "expected"]
        # the half of the row chemistry predicts, so "the right side" needs no number read
        axis.axhspan(position - 0.44, position + 0.44,
                     xmin=0.5 if expected == "+" else 0.0,
                     xmax=1.0 if expected == "+" else 0.5, color=WASH, zorder=0)
        medians = [trends[route]["table"].loc[name, "within"] for route in ROUTES]
        axis.hlines(position, min(medians), max(medians), color=RULE, lw=1.2, zorder=1)
        # a lane per route, in ROUTES order: two medians 0.009 apart would otherwise hide
        # one another, and the lane is a second cue after lightness
        for offset, route, median in zip((0.17, 0.0, -0.17), ROUTES, medians):
            axis.plot(median, position + offset, marker=marker_for(ROUTE[route]), ms=4.0,
                      color=ROUTE[route], markeredgecolor="white", markeredgewidth=0.5,
                      lw=0, zorder=4, label=route if position == 0 else None)
    axis.set_yticks(range(len(relationships)), relationships[::-1], fontsize=5.6)
    axis.set_xlim(-1, 1)
    axis.set_ylim(-0.65, len(relationships) - 0.35)
    axis.set_xlabel("median within-paper ρ")
    axis.legend(fontsize=5.4, loc="upper left", handletextpad=0.1, borderpad=0.15,
                borderaxespad=0.2, labelspacing=0.22)

    save(figure, "fig4_gao")


if __name__ == "__main__":
    main()
