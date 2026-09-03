"""Figure 4 -- the extracted conditions, route by route, against hand curation where it exists.

The argument the figure has to make, in the order a reader meets it.

Panel a is the check: Gao et al. curated 364 ionic-liquid glycolysis experiments by hand, and
their points and ours occupy the same region of temperature and yield. Panels b and c are the
transfer: hydrolysis and methanolysis have no curated set to check against and never will, so
what they offer is that they look like the same kind of data, gathered around their own working
temperatures. Panel d accounts for the difference in size between the two glycolysis sets, which
is a scope decision rather than a failure -- most of Gao's extra records are values read off a
plotted curve, which the prompt tells the model to ignore in favour of tables.

An earlier version tabulated field agreement as a row of bars and the per-route correlations as
a row of dots. Both were the numbers printed sideways. A scatter shows the two datasets landing
in the same place, which is what agreement means.
"""
from _style import (DATA, DIM, EMPHASIS, RAMP, canvas, cloud, pie, save)
from curated import gao_overlap
from database import chemistry as chem

# The window the panels share. Almost every run in the corpus sits inside it; what falls outside
# is mostly pressurised hydrolysis above the plotted range, and each panel says how many.
TEMPERATURE = (80, 320)

# Why a curated record is or is not in ours. Five reasons, five steps of one ramp, the shortfall
# on the darkest -- it is the number that matters, not an alarm.
REASONS = [("both", "in both", DATA),
           ("chart", "read off a plotted curve", RAMP[2]),
           ("si", "in SI we do not hold", RAMP[3]),
           ("rule", "a design table, out of scope", RAMP[4]),
           ("missed", "in a table we read", EMPHASIS)]


def scatter(axis, frame, route, *, ylabel=""):
    """One route's temperature against its yield, and how much of it is off the plotted range."""
    pair = frame[frame.route == route][["temperature_c", "yield_percent"]].dropna()
    inside = pair[pair.temperature_c.between(*TEMPERATURE)]
    cloud(axis, inside.temperature_c, inside.yield_percent, colour=RAMP[3], size=5)
    axis.set_xlim(*TEMPERATURE)
    axis.set_ylim(0, 118)
    axis.set_xlabel("temperature (°C)")
    axis.set_ylabel(ylabel)
    outside = len(pair) - len(inside)
    axis.set_yticks([0, 20, 40, 60, 80, 100])
    axis.annotate(f"{route} — {len(inside):,} experiments"
                  + (f", {outside} outside the range" if outside else ""),
                  (0.075, 1.02), xycoords="axes fraction", ha="left", va="bottom",
                  fontsize=5.6, color=DIM)
    return inside


def main() -> None:
    gao = gao_overlap.compute()
    ours = chem.compute()["records"]
    curated = gao["records"]
    curated = curated[curated.category != "ours"]

    figure, panel = canvas(2, 2, height=4.4)

    # --- a: glycolysis, with the hand-curated set overlaid -----------------------------------
    scatter(panel[0], ours, "glycolysis", ylabel="BHET yield (%)")
    theirs = curated[["gao_temperature_c", "gao_yield_percent"]].dropna()
    theirs = theirs[theirs.gao_temperature_c.between(*TEMPERATURE)]
    # drawn second and darker, so the overlay reads as sitting on top of our cloud rather than
    # beside it. Diamond as well as dark: two channels, no hatch.
    cloud(panel[0], theirs.gao_temperature_c, theirs.gao_yield_percent,
          colour=EMPHASIS, marker="D", size=9, edge="white",
          label=f"Gao et al. ({len(theirs)})")
    panel[0].legend(fontsize=5.4, loc="lower right", handletextpad=0.2, borderpad=0.2,
                    borderaxespad=0.3, markerscale=1.1)

    # --- b, c: the two routes no curated set covers ------------------------------------------
    scatter(panel[1], ours, "hydrolysis")
    scatter(panel[2], ours, "methanolysis", ylabel="BHET yield (%)")

    # --- d: what the size difference between the two glycolysis sets is made of --------------
    counts = gao["split"].reindex([key for key, _, _ in REASONS])
    counts.index = [label for _, label, _ in REASONS]
    pie(panel[3], counts, colours=[colour for _, _, colour in REASONS])
    panel[3].set_xlabel(f"Gao et al.'s {int(counts.sum())} curated experiments")

    save(figure, "fig4_gao")


if __name__ == "__main__":
    main()
