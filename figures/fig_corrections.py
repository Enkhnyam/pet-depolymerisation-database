"""What the judge's corrections are worth, separated by what they ask you to do.

The manuscript can quote one number for this round -- the chemists accepted the judge's value on
76 of 120 sampled corrections -- and it flatters the judge twice over. Once because a
"correction" is not one kind of act: supplying a value the record lacked and re-reading which
ionic liquid was used cost different amounts to be wrong about, and are not equally often right.
And once because half of those accepted corrections were also marked "both defensible", meaning
the extractor had not erred at all -- the judge settled a naming convention rather than fixing
anything.

An earlier draft of this figure failed as a figure. It named the rows in past-tense verbs with
no subject ("Emptied a value"), labelled the rows in only one of two panels so the eye had to
shuttle between them on trust, and put the comparison that matters -- what the pooled number
hides -- in a thin dashed line captioned "pooled, 49%". A reader who had not already done the
analysis could not recover the finding from it. This version puts the finding in the row labels,
the panel titles and the legend, and orders the rows so the gradient is itself the argument.

  (a) The composition, in one bar: three quarters of what the judge calls a correction is adding
      or removing a value, not disputing one that is already there. Read off the corrections
      themselves, so no reviewer's opinion enters it.

  (b) Reliability by what was proposed, worst at the bottom. The judge earns its reputation on
      the cheap edits and loses it on the one a chemist reading the database would be misled by:
      of 22 proposals to rename a substance, one was a real error and 21 were two acceptable
      names for the same compound.

Severity is deliberately not drawn. The review asked for it as a separate yes/no and the answers
do not reconcile with the verdicts -- cards marked "both defensible" also carry "the extractor's
error is severe" -- so it cannot carry a published claim.
"""
import json
from pathlib import Path

from matplotlib.patheffects import withStroke

from _style import BAR, CATEGORICAL, DIM, INK, canvas, caption, save

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "artifacts/gold/corrections/decisions.json"

# What the judge asks you to do, said as an instruction rather than as a past-tense verb with no
# subject. "Emptied a value" left a reader asking who emptied it.
KINDS = {
    "fill": "Add a value the record was missing",
    "empty": "Delete a value the paper does not support",
    "number": "Replace one number with another",
    "substance": "Rename the substance",
}
# Edits that touch a field empty on one side, as against edits that dispute a value already there.
CHEAP = {"fill", "empty"}
IDENTITY_FIELDS = {"catalyst", "solvent"}

# Reader-facing outcome names. "Both defensible" was the review page's own wording and meant
# nothing on its own, though it is half the data: the point is that the extractor had not erred.
OUTCOMES = ["Fixed a real error", "No error — both acceptable", "Judge was wrong"]
COLOUR = {OUTCOMES[0]: CATEGORICAL["blue"], OUTCOMES[1]: DIM, OUTCOMES[2]: CATEGORICAL["red"]}
HATCH = {OUTCOMES[0]: "", OUTCOMES[1]: "//", OUTCOMES[2]: "xx"}


def _blank(value):
    return value is None or value == ""


def kind_of(row: dict) -> str:
    """What the correction asks for, read off the correction itself."""
    if _blank(row["was"]) and not _blank(row["to"]):
        return "fill"
    if not _blank(row["was"]) and _blank(row["to"]):
        return "empty"
    return "substance" if row["field"] in IDENTITY_FIELDS else "number"


def outcome_of(row: dict) -> str:
    """The review's verdict, collapsed to one mutually exclusive answer.

    The page let a reviewer tick more than one box, and 57 of 120 cards carry both "the judge's
    value is right" and "both defensible". Those are not two votes for the judge: the second says
    the extractor was not wrong, which makes the correction a preference rather than a fix.
    "Both" therefore wins the collapse -- counting those 57 as errors caught is exactly the
    overstatement this figure exists to remove.
    """
    answers = set(row["answers"])
    if "both" in answers:
        return OUTCOMES[1]
    if "judge" in answers:
        return OUTCOMES[0]
    if "extractor" in answers:
        return OUTCOMES[2]
    return "Neither"


def load():
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    rows = [row for row in payload["decisions"].values() if row.get("answers")]
    tally = {key: {outcome: 0 for outcome in OUTCOMES + ["Neither"]} for key in KINDS}
    for row in rows:
        tally[kind_of(row)][outcome_of(row)] += 1
    return payload, rows, tally


def panel_composition(axis, tally):
    """(a) One bar, split once: is this edit filling a hole, or disputing a reading?"""
    cheap = sum(sum(tally[k].values()) for k in CHEAP)
    disputed = sum(sum(tally[k].values()) for k in KINDS if k not in CHEAP)
    total = cheap + disputed

    # The labels anchor to the ends of the bar rather than the middles of their segments: the
    # narrower segment cannot centre a phrase this long without colliding with its neighbour.
    for start, width, colour, label, anchor, align in (
            (0, cheap, CATEGORICAL["blue"], "Adds or deletes\na value", 0, "left"),
            (cheap, disputed, DIM, "Disputes a value\nalready there", cheap + disputed, "right")):
        axis.barh(0, width, left=start, height=0.40, color=colour, edgecolor="white", linewidth=0.8)
        axis.text(start + width / 2, 0, f"{width}", ha="center", va="center", fontsize=8.5,
                  color="white", fontweight="bold",
                  path_effects=[withStroke(linewidth=2.2, foreground=colour)])
        axis.text(anchor, -0.33, label, ha=align, va="top", fontsize=6, color=INK,
                  linespacing=1.35)

    axis.set_xlim(0, total)
    axis.set_ylim(-1.05, 0.45)
    axis.set_yticks([])
    axis.set_xlabel(f"All {total} corrections the chemists ruled on")
    axis.spines[["top", "right", "left"]].set_visible(False)


def panel_reliability(axis, tally, order):
    """(b) How often each kind of proposal was actually right, worst last."""
    positions = range(len(order))[::-1]
    for position, key in zip(positions, order):
        total = sum(tally[key].values())
        left = 0.0
        for outcome in OUTCOMES:
            count = tally[key][outcome]
            if not count:
                continue
            share = 100 * count / total
            axis.barh(position, share, left=left, height=BAR, color=COLOUR[outcome],
                      hatch=HATCH[outcome], edgecolor="white", linewidth=0.6)
            if share >= 14:
                axis.text(left + share / 2, position, f"{count}", ha="center", va="center",
                          fontsize=6.5, color="white", zorder=6,
                          path_effects=[withStroke(linewidth=1.8, foreground=COLOUR[outcome])])
            else:
                # The narrowest segment here is one substance rename in twenty-two, which is the
                # figure's whole point and must never be the number that would not fit.
                axis.annotate(f"{count}", xy=(left + share / 2, position - 0.32), ha="center",
                              va="top", fontsize=6, color=COLOUR[outcome])
            left += share
        axis.text(102, position, f"{total} cases", va="center", fontsize=6, color=DIM)

    axis.set_yticks(list(positions), [KINDS[key] for key in order])
    axis.set_xlim(0, 100)
    axis.set_xlabel("Of that kind (%)")
    axis.spines[["top", "right"]].set_visible(False)


def build():
    payload, rows, tally = load()
    # Worst last: the ordering carries the argument, so it is computed, not chosen.
    order = sorted(KINDS, key=lambda k: -tally[k][OUTCOMES[0]] / max(sum(tally[k].values()), 1))

    figure, (left, right) = canvas(1, 2, height=2.2)
    panel_composition(left, tally)
    panel_reliability(right, tally, order)

    for outcome in OUTCOMES:
        right.barh(-9, 0, color=COLOUR[outcome], hatch=HATCH[outcome], edgecolor="white",
                   label=outcome)
    handles, labels = right.get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False,
                  handlelength=1.3, handletextpad=0.4, columnspacing=1.6,
                  bbox_to_anchor=(0.5, 1.015))
    right.set_ylim(-0.75, len(order) - 0.25)

    left.set_title("(a) Most corrections only add or remove a value", loc="left", fontsize=7)
    right.set_title("(b) The judge is least reliable where it matters most",
                    loc="left", fontsize=7)
    save(figure, "fig_corrections", legend_room=True)

    caught = sum(tally[k][OUTCOMES[0]] for k in KINDS)
    both = sum(tally[k][OUTCOMES[1]] for k in KINDS)
    substance = tally["substance"]
    accepted = sum(1 for row in rows if "judge" in row["answers"])
    return caption(
        r"\textbf{A corrected field is not a corrected record.} The judge proposed __POOL__ "
        r"field-level corrections across the mass extraction; __SAMPLED__ were drawn stratified "
        r"by field and ruled on by chemists, who could give more than one answer per card. "
        r"(\textbf{a}) What the corrections ask for, read from the corrections themselves: "
        r"__CHEAP__ of __SAMPLED__ add a value the record lacked or delete one the paper does "
        r"not support, rather than disputing a value already present. (\textbf{b}) How often "
        r"each kind was right, worst at the bottom. The chemists accepted the judge's value on "
        r"__ACCEPTED__ cards, but on __BOTH__ of those they also marked both readings defensible "
        r"-- the extractor had not erred, so the correction settled a naming convention rather "
        r"than fixing an error. Counting only genuine errors, the judge caught __CAUGHT__ of "
        r"__SAMPLED__. The gap between the kinds is the finding: of __SUBN__ proposals to rename "
        r"a catalyst or solvent -- the one field where a wrong record misleads a chemist reading "
        r"the database -- __SUBCAUGHT__ was a real error and __SUBBOTH__ were two acceptable "
        r"names for the same compound. Replacements of an existing number are too few here "
        r"(__NUMN__) to read a rate from. This is why the released database applies no "
        r"correction automatically, and why the accompanying toolkit shows each proposal beside "
        r"the paper, labelled with what it would change, for a chemist to accept or reject one "
        r"at a time.",
        pool=f"{payload.get('pool', 2163):,}", sampled=len(rows),
        cheap=sum(sum(tally[k].values()) for k in CHEAP),
        accepted=accepted, caught=caught, both=both,
        subn=sum(substance.values()), subcaught=substance[OUTCOMES[0]],
        subboth=substance[OUTCOMES[1]], numn=sum(tally["number"].values()))


if __name__ == "__main__":
    print(build())
