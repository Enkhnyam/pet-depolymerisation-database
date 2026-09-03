"""Figure 2 -- what the extracted conditions look like, and whether they behave.

Distributions rather than scatters: with five thousand records the scatters were mostly ink, and
the question these panels answer is what the corpus contains, not how two variables trade off.
The exceptions are the last two panels, where the relationship is the point.
"""
from _style import (ROUTE, ROUTES, WARN, canvas, caption, histogram, legend_above,
                    paired_rho, points, save, sci)
from database import chemistry as chem
from database import withinpaper as within

CAPTION = r"""\textbf{The conditions the corpus reports, and two tests of whether they behave like
chemistry.} Counts are records throughout; only the leftmost panel in each row is labelled.

The corpus looks like chemistry before anything is tested. Temperature is sharply peaked at
190--200\,\textdegree C (\textbf{a}), where ethylene glycol refluxes, with a thin tail past
400\,\textdegree C that is mostly pressurised hydrolysis. Reaction times span four orders of
magnitude but cluster on the round numbers experimenters actually choose --- 30, 60, 120 minutes
(\textbf{b}) --- a signature of real protocols rather than of a model inventing plausible values.
The outcome fields behave as a literature of optimised runs should, piling up against 100\%
(\textbf{c}, \textbf{d}), and they also expose the error rate: \textbf{__OVER__ records report a
yield above 100\%}, which is impossible and which panel \textbf{c} truncates rather than let
them set its axis. Conversion is reported for only __CONVERSION__\% of records. The three charge fields (\textbf{e}--\textbf{g}) each span five or six orders of
magnitude, from milligrams of catalyst to bulk solvent. The metric grader accepts numbers within
20\%, which means something very different at the two ends of a six-decade axis.

Two panels test rather than describe. Yield cannot exceed conversion --- an identity, not a
correlation --- so nothing may sit above the diagonal (\textbf{h}), and \textbf{only
__IMPOSSIBLE__ of __PAIRS__ records do}. The last panel (\textbf{i}) is the stronger test. It
shows, for each relationship, one dot per paper, a diamond at the median of those dots, and a
red bar at the single value obtained by pooling every record together. It begins as an apparent
failure: pooled across the whole corpus, temperature and yield are uncorrelated
($\rho=__POOLED__$ over __POOLEDN__ records), and so is every other relationship one would
expect to hold. Pooling, however, is the wrong operation on a
corpus of optimised experiments. Each paper reports a few runs around whatever optimum that lab
chose, on its own feedstock, catalyst and scale, so between-paper spread swamps the trend inside
any one of them. Comparing each paper only against itself removes the lab as a variable and the
chemistry reappears: \textbf{median $\rho=__WITHIN__$ across __PAPERS__ papers, __AGREE__\% of
them positive} ($p=__PVAL__$, Wilcoxon). More catalyst likewise gives more, and hotter runs
finish sooner, on the same within-paper reading. Nothing in the prompt or the schema mentions these relationships. This is a consistency check
rather than a measure of fidelity: a model drawing on chemical priors could produce the same
pattern, and getting ratios right while getting absolute masses wrong would preserve within-paper
correlations. It does show that the pooled view is the wrong one to fit a model to."""


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
    over = int(result["out of range"].loc["yield_percent", "above 100%"])
    histogram(panel[3], frame, "conversion_percent", xlabel="conversion (%)", **stack)
    histogram(panel[4], frame, "catalyst_amount_g", logx=True, xlabel="catalyst (g)",
              ylabel="", **stack)
    histogram(panel[5], frame, "PET_amount_g", logx=True, xlabel="PET (g)", ylabel="", **stack)
    histogram(panel[6], frame, "solvent_amount_g", logx=True, xlabel="solvent (g)", **stack)

    points(panel[7], frame, "conversion_percent", "yield_percent",
           colour_by="route", palette=ROUTE, order=ROUTES,
           xlabel="conversion (%)", ylabel="yield (%)")
    panel[7].plot([0, 100], [0, 100], color=WARN, lw=1, ls="--", zorder=3)

    paired_rho(panel[8], trends["table"], trends["per paper"],
               xlabel="Spearman ρ")

    legend_above(figure, panel[0])
    save(figure, "fig2_chemistry")

    identity = result["identity"]
    lead = trends["table"].loc["hotter gives more"]
    print("\n" + caption(
        CAPTION,
        conversion=f"{result['completeness']['conversion %'] * 100:.0f}",
        over=over,
        impossible=identity["yield above conversion"], pairs=identity["pairs with both"],
        pooled=f"{lead['pooled']:+.3f}", pooledn=f"{int(lead['pooled n']):,}",
        within=f"{lead['within']:+.2f}", papers=int(lead["papers"]),
        agree=f"{100 * lead['as predicted']:.0f}", pval=sci(lead['p'])))


if __name__ == "__main__":
    main()
