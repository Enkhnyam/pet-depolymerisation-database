"""SI -- the two things about the Gao comparison that are counts rather than distributions.

Split out of fig_gao, which is a grid of densities and had these bar charts wedged into its
bottom row. Two panels, two questions, in the order a referee asks them:

  (a) Why do the two sets differ in size at all? Not two pie charts: a pie cannot show that the
      sets overlap -- two circles side by side say nothing about their intersection -- and the
      reasons are signed, four raising Gao's count and one raising ours. A diverging bar reads
      left for "only Gao" and right for "only this work" against a single axis of records.

  (b) Where both hold a record, do they say the same thing? At the tolerance the heuristic
      grader uses everywhere else in this project, so "agrees" means one thing throughout.

A third panel asked whether the records this work holds alone are worth having, by counting
fields per record. It is cut: the answer was that the two sets are within a fifth of a field of
each other, and a panel whose finding is "these two distributions are the same" spends a third
of the figure to say nothing a sentence could not. The numbers behind it are still computed --
gao_overlap.compute() returns "fields per record" and the macros derived from it stand -- so the
claim can be made in prose without the reader paying for a chart to carry it.

Every category in (a) was settled by a person reading the paper: an automatic rule proposed each
label and a chemist overruled it fourteen times. That is why the classification is a fixed table
in artifacts/data/gao/ and not a computation.
"""
from _style import CATEGORICAL, DIM, INK, RAMP, canvas, save
from curated import gao_overlap

# Why a record sits in one dataset and not the other, largest first, coloured by whose count it
# raises: the blue ramp for Gao's reasons, red for the one that is our error, blue for ours.
REASONS = [("chart", "read off a chart", RAMP[1]),
           ("si", "in SI we lack", RAMP[2]),
           ("rule", "design table", RAMP[3]),
           ("missed", "we missed it", CATEGORICAL["red"])]

# The schema's field names as a chemist writes them, units in parentheses where the field has
# one, so panel (b) never spells a field two ways -- "catalyst amount g" beside "catalyst (g)"
# leaves a reader matching rows by position.
# Where a field stops counting as agreeing. Named because panel (b) both colours and rounds
# against it, and those two must not disagree about where it is.
AGREE_GATE = 0.9

FIELDS = {"temperature_c": "Temperature (°C)", "reaction_time_min": "Reaction time",
          "catalyst_amount_g": "Catalyst (g)", "PET_amount_g": "PET (g)",
          "solvent_amount_g": "Solvent (g)", "yield_percent": "BHET yield (%)",
          "conversion_percent": "Conversion (%)", "selectivity_percent": "Selectivity (%)",
          "catalyst": "Catalyst", "solvent": "Solvent"}


def main() -> None:
    result = gao_overlap.compute()
    counts = gao_overlap.records().category.value_counts()

    figure, panel = canvas(1, 2, height=2.55)

    # --- a: why the two sets differ in size ---------------------------------------------------
    axis = panel[0]
    shared, ours_only = int(counts["both"]), int(counts["ours"])
    rows = [(label, -int(counts[key]), colour) for key, label, colour in REASONS]
    rows.append(("ours alone", ours_only, CATEGORICAL["blue"]))
    for position, (label, value, colour) in enumerate(rows):
        y = len(rows) - 1 - position
        axis.barh(y, value, height=0.62, color=colour)
        inside = abs(value) > 60
        axis.annotate(f"{abs(value)}", (value, y),
                      xytext=((5 if value < 0 else -5) if inside
                              else (-4 if value < 0 else 4), 0),
                      textcoords="offset points",
                      ha=("left" if value < 0 else "right") if inside
                         else ("right" if value < 0 else "left"),
                      va="center", fontsize=6, color="white" if inside else DIM)
    axis.axvline(0, color=INK, lw=0.8)
    axis.set_yticks(range(len(rows)), [label for label, *_ in reversed(rows)], fontsize=6)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(-215, 150)
    ticks = [-200, -100, 0, 100]
    axis.set_xticks(ticks, [str(abs(v)) for v in ticks])
    axis.set_xlabel(f"records, {shared} shared")

    # --- b: on the records both hold, do they agree -------------------------------------------
    axis = panel[1]
    agree = result["agreement"].sort_values("share")
    for position, (field, row) in enumerate(agree.iterrows()):
        share = row["share"]
        good = share >= AGREE_GATE
        axis.barh(position, share * 100, height=0.62,
                  color=CATEGORICAL["blue"] if good else CATEGORICAL["red"])
        # Yield is 0.8966: below the gate, and "90%" printed in the below-the-gate colour reads
        # as a mistake in the figure rather than as a rounding. A value that rounds onto the gate
        # from either side gets the decimal that puts it back on its own side of it.
        digits = 1 if round(share * 100) == AGREE_GATE * 100 and share != AGREE_GATE else 0
        axis.annotate(f"{share * 100:.{digits}f}% of {int(row['both report it'])}",
                      (share * 100, position), xytext=(3, 0),
                      textcoords="offset points", va="center", fontsize=5.4, color=DIM)
    axis.set_yticks(range(len(agree)),
                    [FIELDS.get(str(name), str(name)) for name in agree.index], fontsize=5.4)
    axis.tick_params(axis="y", length=0)
    axis.spines["left"].set_visible(False)
    axis.set_xlim(0, 142)
    axis.set_xticks([0, 50, 100])
    axis.set_xlabel("shared records agreeing, per field")

    save(figure, "fig_gao_records")


if __name__ == "__main__":
    main()
