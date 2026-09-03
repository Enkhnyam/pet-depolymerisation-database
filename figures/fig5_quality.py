"""Figure 5 -- is the data any good, and does the answer reach all three routes.

Two legs, and the figure has to make clear which one carries the weight.

The external leg is Gao et al.: 364 glycolysis experiments curated by hand, the only external
reference this work has. Panels a and b are that comparison -- where the two datasets overlap
they agree, and where they do not, the gap is accounted for rather than unexplained.

The external leg cannot reach hydrolysis or methanolysis, because nobody has hand-curated them.
Panel c is the leg that does: within each paper, the relationships chemistry fixes the sign of
appear in every route, with no external reference involved. That is the argument, and a is the
support for it -- not the other way round.

Panels carry only their letter; what each is for belongs in the caption, which this prints.
"""
import numpy as np

from _style import (CYCLE, DIM, GUIDE, INK, NEUTRAL, ROUTE, ROUTES, RULE, WARN, canvas,
                    caption, lollipop, redundant, save)
from curated import gao_overlap
from database import withinpaper

# Panel b encodes the argument, not the categories: one colour for what both datasets hold, one
# family of greys for a gap that is explained, and WARN for the part that is genuinely our miss.
# Five arbitrary hues would make the reader hunt for which segment matters.
GAP = {
    "both": ("in both", CYCLE[0], ""),
    "chart": ("read off a chart", NEUTRAL, "///"),
    "si": ("in SI we lack", "#7C8D91", "..."),
    "rule": ("a design table we skip", "#A3B0B3", "xxx"),
    "missed": ("in a table we read", WARN, ""),
}

FIELD_LABELS = {
    "temperature_c": "temperature", "reaction_time_min": "reaction time",
    "catalyst_amount_g": "catalyst mass", "PET_amount_g": "PET mass",
    "solvent_amount_g": "solvent mass", "yield_percent": "BHET yield",
    "conversion_percent": "conversion", "selectivity_percent": "selectivity",
    "catalyst": "catalyst name", "solvent": "solvent name",
}

CAPTION = r"""\textbf{The database agrees with hand curation where it can be checked, and behaves
like chemistry where it cannot.}
\textbf{a} Field-by-field agreement with Gao \emph{et al.}'s hand-curated ionic-liquid glycolysis
set on the __SHARED__ experiments both datasets describe, over the __PAPERS__ papers they share.
A numeric field agrees when the two values fall within the same __TOLERANCE__\% tolerance the
string-matching baseline uses; names agree after normalising bracket convention, since
[BMIM]Br and [Bmim][Br] are one substance written two ways. Temperature and reaction time agree
on every record; the weakest field is __WORSTFIELD__ at __WORSTSHARE__\%.

\textbf{b} Why the hand-curated set lists more experiments than we extract from the same papers,
every one of Gao's __GAORECORDS__ records assigned a reason by a chemist reading the paper.
__CHARTSHARE__\% are values read off a plotted curve --- papers typically chart yield against
catalyst loading, so one tabulated condition reappears many times with only the loading varied
--- and our prompt instructs the model to read tables and ignore figures. __SIRECORDS__ sit in
Supporting Information we do not hold and __RULERECORDS__ are response-surface design tables our
scope excludes. That leaves __MISSED__ records, __MISSEDSHARE__\% of the set, in a table the
model read and did not pick up: the extraction shortfall, and it is small. We also hold
__OURSONLY__ tabulated experiments on those papers that the hand curation does not.

\textbf{c} The test that needs no external reference, and the only one that reaches all three
routes. Within a single paper the laboratory, feedstock and scale are fixed, so the sign of each
relationship is chemistry rather than convention: hotter gives more, more catalyst gives more,
hotter finishes sooner. Points are the median within-paper Spearman $\rho$ for each route, over
papers reporting at least five runs that vary both quantities; the shaded side of each row is the
sign chemistry predicts, and each median rests on __MINPAPERS__--__MAXPAPERS__ papers.
__ROWSAGREE__ of __ROWSTOTAL__ route-relationship pairs fall on the predicted side, including
in the two routes no external dataset covers. The exception is the one cell where the median is
exactly zero rather than the wrong sign --- reaction time against temperature in hydrolysis ---
and time against yield is weak in every route, which is what a corpus of optimised experiments
should look like: authors stop the reaction once it has finished. Nothing in the prompt or the
schema mentions any of these relationships."""


def main() -> None:
    gao = gao_overlap.compute()
    routes = withinpaper.by_route()

    figure, panel = canvas(1, 3, height=2.55)

    # --- a: agreement per field, worst first so the eye lands on the weakest claim -----------
    agree = gao["agreement"].sort_values("share")
    shares = (agree.share * 100).rename(index=FIELD_LABELS)
    lollipop(panel[0], shares, colour=CYCLE[0], xlabel="records agreeing (%)", xmax=100)
    # the count behind each share, because 90% of 58 records and 90% of 127 are different claims
    for position, (name, row) in zip(range(len(agree))[::-1], agree.iterrows()):
        panel[0].annotate(f"{row.share:.0%} of {int(row['both report it'])}",
                          (row.share * 100, position), textcoords="offset points",
                          xytext=(4, 0), fontsize=5.2, color=DIM, va="center")
    panel[0].set_xlim(0, 132)

    # --- b: the gap, accounted for -----------------------------------------------------------
    # One row per reason, in the order the argument runs -- agreed, then three kinds of
    # explained, then ours -- rather than sorted by size, so it reads top to bottom. WARN on the
    # last row is the only red on the canvas and it is where the eye should land.
    total = int(gao["split"].sum())
    keys = list(gao["split"].index)
    for position, key in enumerate(keys):
        count = int(gao["split"][key])
        label, colour, hatch = GAP[key]
        panel[1].barh([len(keys) - 1 - position], [count], height=0.52, color=colour,
                      hatch=hatch, edgecolor="white", linewidth=0.4)
        panel[1].annotate(f"{count} ({count / total:.0%})",
                          (count, len(keys) - 1 - position), textcoords="offset points",
                          xytext=(4, 0), fontsize=5.4, va="center",
                          color=WARN if key == "missed" else DIM,
                          fontweight="bold" if key == "missed" else "normal")
    panel[1].set_yticks(range(len(keys))[::-1], [GAP[k][0] for k in keys], fontsize=5.6)
    panel[1].set_xlim(0, int(gao["split"].max()) * 1.42)
    panel[1].set_xlabel(f"of Gao et al.'s {total} curated experiments")

    # --- c: the internal test, per route -----------------------------------------------------
    relationships = list(routes[ROUTES[0]]["table"].index)
    axis = panel[2]
    axis.axvline(0, color=INK, lw=0.8, zorder=2)
    agreeing, supports = 0, []
    for position, name in enumerate(relationships[::-1]):
        sign = routes[ROUTES[0]]["table"].loc[name, "expected"]
        # shade the half of the row chemistry predicts, so "on the right side" is visible
        # without reading a single number
        axis.axhspan(position - 0.42, position + 0.42, xmin=0.5 if sign == "+" else 0.0,
                     xmax=1.0 if sign == "+" else 0.5, color=GUIDE, alpha=0.45, zorder=0)
        medians = [routes[route]["table"].loc[name, "within"] for route in ROUTES]
        supports += [int(routes[route]["table"].loc[name, "papers"]) for route in ROUTES]
        axis.hlines(position, min(medians), max(medians), color=RULE, lw=1.0, zorder=1)
        # Each route keeps its own lane within the row, in the fixed ROUTES order. Two medians
        # 0.009 apart -- glycolysis and hydrolysis on time against yield -- drew one marker on
        # top of the other, and a lane is both the fix and a third cue after colour and shape.
        for offset, (route, median) in zip((0.16, 0.0, -0.16), zip(ROUTES, medians)):
            _, marker = redundant(ROUTE[route])
            axis.plot(median, position + offset, marker=marker, ms=3.8, color=ROUTE[route],
                      markeredgecolor="white", markeredgewidth=0.5, lw=0, zorder=3,
                      label=route if position == len(relationships) - 1 else None)
            agreeing += (median > 0) if sign == "+" else (median < 0)
    axis.set_yticks(range(len(relationships)),
                    [str(n) for n in relationships[::-1]], fontsize=5.6)
    axis.set_xlim(-1, 1)
    axis.set_ylim(-0.6, len(relationships) + 0.05)
    axis.set_xlabel("median within-paper ρ")
    # top-left: every median in the predicted direction leaves that corner empty, and a legend
    # over the markers is what the first draft did
    axis.legend(fontsize=5.4, loc="upper left", handletextpad=0.1, borderpad=0.15,
                borderaxespad=0.2, labelspacing=0.22)

    save(figure, "fig5_quality")

    worst = shares.idxmin()
    print("\n" + caption(
        CAPTION,
        shared=f"{gao['counts']['shared records']:,}",
        papers=gao["counts"]["Gao papers"],
        tolerance="20",
        worstfield=worst,
        worstshare=f"{shares.min():.0f}",
        gaorecords=f"{total:,}",
        chartshare=f"{gao['chart share'] * 100:.0f}",
        sirecords=int(gao["split"]["si"]),
        rulerecords=int(gao["split"]["rule"]),
        missed=int(gao["split"]["missed"]),
        missedshare=f"{gao['true miss share'] * 100:.0f}",
        oursonly=gao["counts"]["ours alone"],
        rowsagree=agreeing,
        rowstotal=len(relationships) * len(ROUTES),
        minpapers=min(supports),
        maxpapers=max(supports)))


if __name__ == "__main__":
    main()
