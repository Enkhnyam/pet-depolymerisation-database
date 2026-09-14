"""What the judge's corrections are worth, separated by what they ask you to do.

The manuscript can quote one number for this round -- the chemists accepted the judge's value on
76 of the 120 sampled corrections -- and it flatters the judge twice over.

Once because a "correction" is not one kind of act. Supplying a value the record lacked and
re-reading which ionic liquid was used cost different amounts to be wrong about and are not
equally often right, so a pooled rate averages over a gradient steep enough to reverse the
conclusion at either end of it.

And once because the review let a chemist tick more than one box. The chemists accepted the
judge's value on 76 of the 120 cards, and 17 of those 76 also carry "both readings defensible".
Those 17 are not two votes for the judge: the second answer says the extractor had not erred,
which makes the correction a preference rather than a fix. Removing them takes the round from 76
of 120 to 59, and that is before the gradient below, which is the larger effect of the two.

The verdict collapse is therefore a partition and not a filter: every card lands in exactly one
of three outcomes and the three sum to the sample. An earlier version dropped the one card marked
"neither value is right" on the floor, which is how a 100%-stacked bar came to stop at 98%.

    corrections.py
"""
import json

import pandas as pd

from _setup import ARTIFACTS, show, sources

DECISIONS = ARTIFACTS / "gold" / "corrections" / "decisions.json"

# What the judge asks you to do, said as an instruction rather than as a past-tense verb with no
# subject. "Emptied a value" left a reader asking who emptied it.
KINDS = {
    "fill": "Add a value",
    "empty": "Delete a value",
    "number": "Replace a number",
    "substance": "Rename a substance",
}
# The two fields where a wrong record misleads a chemist reading the database, rather than
# costing them a recalculation.
IDENTITY_FIELDS = {"catalyst", "solvent"}

# Three outcomes, mutually exclusive and exhaustive over the sample.
CAUGHT, BOTH, REJECTED = ("Judge correction was correct", "Extraction and judge both correct",
                          "Judge correction rejected")
OUTCOMES = [CAUGHT, BOTH, REJECTED]


def _blank(value) -> bool:
    return value is None or value == ""


def kind_of(row: dict) -> str:
    """What the correction asks for, read off the correction itself rather than off an opinion."""
    if _blank(row["was"]) and not _blank(row["to"]):
        return "fill"
    if not _blank(row["was"]) and _blank(row["to"]):
        return "empty"
    return "substance" if row["field"] in IDENTITY_FIELDS else "number"


def outcome_of(row: dict) -> str:
    """The review's verdict, collapsed to one answer of three.

    "both" wins over "judge" wherever a card carries both, for the reason in the docstring: a
    correction the extractor did not need is not an error caught. Everything the chemists did not
    accept the judge's value on -- they backed the extractor, or neither value -- is one outcome,
    because the panel's question is whether the proposal was worth applying and both answers to
    that are no.
    """
    answers = set(row["answers"])
    if "both" in answers:
        return BOTH
    if "judge" in answers:
        return CAUGHT
    return REJECTED


def compute() -> pd.DataFrame:
    """One row per kind of correction, one column per outcome, in counts.

    Counts rather than shares, because the four kinds are sampled 6 to 59 deep and a rate read
    off six cards is not a rate. The figure draws the shares and carries the depth in the
    thickness of each bar, so neither reading is available without the other.
    """
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    rows = [row for row in payload["decisions"].values() if row.get("answers")]

    table = pd.DataFrame(0, index=list(KINDS), columns=OUTCOMES)
    for row in rows:
        table.loc[kind_of(row), outcome_of(row)] += 1

    table["cases"] = table[OUTCOMES].sum(axis=1)
    table["caught share"] = table[CAUGHT] / table["cases"]
    # Worst last: the gradient is the finding, so the order is computed and not chosen.
    table = table.sort_values("caught share", ascending=False)
    table.attrs["sampled"] = len(rows)
    # The pool the sample was drawn from. verdicts.py counts the same field-level changes for
    # the manuscript's \JudgeFieldFixes, and the figure states the sample beside the pool, so
    # the two must come from one place rather than from a number typed into a caption.
    from database import verdicts as verdicts_check
    table.attrs["pool"] = int(verdicts_check.compute()["fields"].sum())
    # What a pooled number would have said, kept beside the split it hides.
    table.attrs["accepted"] = sum(1 for row in rows if "judge" in row["answers"])
    # The overlap that makes the pooled number an overstatement, counted rather than asserted:
    # cards where the chemists took the judge's value and also said the extractor's would do.
    table.attrs["accepted but defensible"] = sum(
        1 for row in rows if {"judge", "both"} <= set(row["answers"]))
    table.index.name = "the correction asks you to"
    return table


def main() -> None:
    sources(decisions=DECISIONS)
    table = compute()
    show("corrections the chemists ruled on, by what each one asks for",
         table[OUTCOMES + ["cases"]], fmt="{:.0f}")
    show("of that kind, the share that caught a real error", table["caught share"], fmt="{:.2f}")
    print(f"\n  {table.attrs['sampled']} cards ruled on, "
          f"{int(table[CAUGHT].sum())} of them a real error caught")
    print(f"  a pooled rate would say {table.attrs['accepted']}: the chemists accepted the "
          f"judge's value that often, but marked "
          f"{table.attrs['accepted but defensible']} of those {table.attrs['accepted']} "
          f"defensible either way, so the extractor had not erred on them")
    assert int(table["cases"].sum()) == table.attrs["sampled"], "the three outcomes must partition"


if __name__ == "__main__":
    main()
