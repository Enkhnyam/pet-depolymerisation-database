"""What the judge's corrections are worth, separated by what they actually change.

The manuscript can quote one number for this round -- the chemists accepted the judge's value on
76 of 120 sampled corrections -- and that number is misleading in both directions. It is
misleading because a "correction" is not one kind of act. Emptying a field the paper never
supported and re-reading which ionic liquid was used are different claims, cost different
amounts to make, and are not equally often right. Pooling them produces a figure dominated by
whichever kind happens to be commonest, which here is the cheap kind.

So the panels separate the two questions a reader actually has:

  (a) What does a correction change? Determined from the correction itself -- whether a value
      was absent before, absent after, or replaced -- so no reviewer's opinion enters it.
      Three quarters of them have a null on one side: the judge is mostly filling holes and
      deleting unsupported numbers, not disputing readings.

  (b) Within each kind, what did the chemists find? The review offered four answers and let
      more than one be chosen, so a stacked share of raw votes would double-count. The panel
      partitions instead, on the answer that carries the most information: "both defensible"
      means the extractor was not wrong, so the correction arbitrated a convention rather than
      catching an error. That is the distinction the pooled number erases.

The result is the opposite of flattering, which is why it belongs in the paper. The judge earns
its 63% on the cases that cost nothing -- gaps and deletions, where it catches a real error
around three times in five. On substance identity, the one place a wrong record would mislead a
chemist reading the database, it caught a genuine error once in twenty-two attempts; the other
twenty-one were two defensible spellings of the same thing.

Severity is deliberately not drawn. The review asked for it as a separate yes/no and the answers
do not reconcile with the verdicts -- cards marked "both defensible" also carry "the extractor's
error is severe" -- so it cannot carry a published claim. The counts are in the caption's reach
if that is ever resolved.
"""
import json
from pathlib import Path

from matplotlib.patheffects import withStroke

from _style import (BAR, CATEGORICAL, DIM, EMPHASIS, INK, canvas, caption, legend_above,
                    note, save)

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "artifacts/gold/corrections/decisions.json"

# The four things a correction can do, in the order the panel stacks them: the two that involve
# a null first, because that is the split the figure exists to show.
KINDS = ["Emptied a value", "Filled a gap", "Changed a substance", "Changed a number"]
IDENTITY_FIELDS = {"catalyst", "solvent"}

# Outcome colours. Blue is the house's single-series colour and takes the thing being measured;
# the convention calls take the de-emphasis ink because they are not errors either way; red is
# reserved for the judge being wrong. Hatching repeats the encoding for a reader who cannot
# separate the hues, and every segment wide enough also carries its own number.
OUTCOMES = ["Judge caught an error", "Both defensible", "Judge was wrong"]
OUTCOME_COLOUR = {"Judge caught an error": CATEGORICAL["blue"],
                  "Both defensible": DIM,
                  "Judge was wrong": CATEGORICAL["red"]}
OUTCOME_HATCH = {"Judge caught an error": "", "Both defensible": "//", "Judge was wrong": "xx"}


def _blank(value):
    return value is None or value == ""


def kind_of(row: dict) -> str:
    """What this correction changes, read off the correction itself.

    No reviewer's judgment enters here, which is the point: panel (a) has to be a property of
    the corrections the judge proposed, not of how anyone later felt about them.
    """
    if _blank(row["was"]) and not _blank(row["to"]):
        return "Filled a gap"
    if not _blank(row["was"]) and _blank(row["to"]):
        return "Emptied a value"
    return "Changed a substance" if row["field"] in IDENTITY_FIELDS else "Changed a number"


def outcome_of(row: dict) -> str:
    """The review's verdict, collapsed to one mutually exclusive answer.

    The page let a reviewer tick more than one box, and 57 of 120 cards carry both "the judge's
    value is right" and "both defensible". Those are not two votes for the judge: the second says
    the extractor was not wrong, which makes the correction a preference rather than a fix.
    "Both" therefore wins the collapse -- claiming those 57 as errors caught is exactly the
    overstatement this figure is here to remove.
    """
    answers = set(row["answers"])
    if "both" in answers:
        return "Both defensible"
    if "judge" in answers:
        return "Judge caught an error"
    if "extractor" in answers:
        return "Judge was wrong"
    return "Neither"


def load():
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    rows = [row for row in payload["decisions"].values() if row.get("answers")]
    tally = {kind: {outcome: 0 for outcome in OUTCOMES + ["Neither"]} for kind in KINDS}
    for row in rows:
        tally[kind_of(row)][outcome_of(row)] += 1
    return payload, rows, tally


def panel_composition(axis, tally):
    """(a) How many corrections of each kind, and how many touch a null at all."""
    totals = [sum(tally[kind].values()) for kind in KINDS]
    positions = range(len(KINDS))[::-1]
    # The two null-involving kinds are the finding, so they take the emphasis ink and the other
    # two recede -- weight rather than a new hue, per the house rule.
    colours = [EMPHASIS if kind in ("Emptied a value", "Filled a gap") else DIM for kind in KINDS]
    axis.barh(list(positions), totals, color=colours, height=BAR)
    for position, total in zip(positions, totals):
        axis.text(total + 1.2, position, f"{total}", va="center", fontsize=6, color=INK)
    axis.set_yticks(list(positions), KINDS)
    axis.set_xlabel("Corrections in the sample")
    axis.set_xlim(0, max(totals) * 1.18)
    axis.spines[["top", "right"]].set_visible(False)

    with_null = sum(t for kind, t in zip(KINDS, totals) if kind in ("Emptied a value", "Filled a gap"))
    note(axis, f"{with_null} of {sum(totals)} add or remove a value\nrather than dispute one",
         x=0.34, y=0.06)


def panel_outcomes(axis, tally):
    """(b) Within each kind, what the chemists decided."""
    positions = range(len(KINDS))[::-1]
    for position, kind in zip(positions, KINDS):
        total = sum(tally[kind].values())
        left = 0.0
        for outcome in OUTCOMES:
            count = tally[kind][outcome]
            if not count:
                continue
            share = 100 * count / total
            axis.barh(position, share, left=left, height=BAR, color=OUTCOME_COLOUR[outcome],
                      hatch=OUTCOME_HATCH[outcome], edgecolor="white", linewidth=0.6)
            # Every count is shown. A segment wide enough carries it inside, with a halo so the
            # hatching cannot cut through the digits; a narrow one carries it just below, which
            # matters because the narrowest segment in this panel -- one substance correction in
            # twenty-two -- is the figure's whole point and must not be the one number missing.
            if share >= 13:
                axis.text(left + share / 2, position, f"{count}", ha="center", va="center",
                          fontsize=6, color="white", zorder=6,
                          path_effects=[withStroke(linewidth=1.6, foreground=OUTCOME_COLOUR[outcome])])
            elif count:
                axis.annotate(f"{count}", xy=(left + share / 2, position - 0.36),
                              ha="center", va="top", fontsize=5.8,
                              color=OUTCOME_COLOUR[outcome])
            left += share
        axis.text(101.5, position, f"n={total}", va="center", fontsize=5.8, color=DIM)

    axis.set_yticks(list(positions), ["" for _ in KINDS])   # (a) already names the rows
    axis.set_xlim(0, 100)
    axis.set_xlabel("Share of that kind (%)")
    axis.spines[["top", "right"]].set_visible(False)

    pooled = sum(tally[kind]["Judge caught an error"] for kind in KINDS)
    overall = sum(sum(tally[kind].values()) for kind in KINDS)
    axis.axvline(100 * pooled / overall, color=INK, linestyle=(0, (2, 2)), linewidth=0.8, zorder=5)
    axis.text(100 * pooled / overall + 1.5, len(KINDS) - 0.62,
              f"pooled, {100 * pooled / overall:.0f}%", fontsize=5.8, color=INK)


def build():
    payload, rows, tally = load()
    figure, (left, right) = canvas(1, 2)
    panel_composition(left, tally)
    panel_outcomes(right, tally)

    handles = [
        (OUTCOME_COLOUR[outcome], OUTCOME_HATCH[outcome], outcome) for outcome in OUTCOMES
    ]
    for index, (colour, hatch, label) in enumerate(handles):
        right.barh(-9, 0, color=colour, hatch=hatch, edgecolor="white", label=label)
    right.set_ylim(left.get_ylim())
    legend_above(figure, right)

    left.set_title("(a) What the correction changes", loc="left", fontsize=7)
    right.set_title("(b) What the chemists found", loc="left", fontsize=7)
    save(figure, "fig_corrections", legend_room=True)

    caught = sum(tally[kind]["Judge caught an error"] for kind in KINDS)
    both = sum(tally[kind]["Both defensible"] for kind in KINDS)
    substance = tally["Changed a substance"]
    return caption(
        r"\textbf{A corrected field is not a corrected record.} The judge proposed "
        r"__POOL__ field-level corrections across the mass extraction; __SAMPLED__ were drawn "
        r"stratified by field and ruled on by chemists, who could mark more than one answer per "
        r"card. (\textbf{a}) What each correction does, read from the correction itself: "
        r"__WITHNULL__ of __SAMPLED__ either supply a value the record lacked or remove one the "
        r"paper does not support, rather than disputing a value already present. "
        r"(\textbf{b}) Within each kind, the chemists' verdict, collapsed so that ``both "
        r"defensible'' -- the extractor was not wrong -- is counted apart from ``the judge "
        r"caught an error''. The judge caught a genuine error in __CAUGHT__ of __SAMPLED__ "
        r"cases (dashed line), while __BOTH__ arbitrated between two defensible readings rather "
        r"than fixing anything. The separation matters most where the stakes are highest: of "
        r"__SUBN__ corrections to a catalyst or solvent identity, __SUBCAUGHT__ was judged a "
        r"real error and __SUBBOTH__ were two acceptable spellings of the same substance. "
        r"Replacements of an existing number are too few here (__NUMN__) to read a rate from. "
        r"This is why the released database applies no correction automatically, and why the "
        r"accompanying toolkit puts the judge's proposal beside the paper for a chemist to "
        r"accept or reject one at a time.",
        pool=f"{payload.get('pool', 2163):,}", sampled=len(rows),
        withnull=sum(sum(tally[k].values()) for k in ("Emptied a value", "Filled a gap")),
        caught=caught, both=both, subn=sum(substance.values()),
        subcaught=substance["Judge caught an error"], subboth=substance["Both defensible"],
        numn=sum(tally["Changed a number"].values()))


if __name__ == "__main__":
    print(build())
