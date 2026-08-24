"""Which records the next adjudication round should use, and how many.

The round runs on the 24 curated papers, not on the database: the metric grader has no verdict
without a curated answer key, and comparing the two graders is the point.

Two strata, because two different questions have to be answered at once.

Every disagreement is included -- a census, not a sample, so that stratum carries no sampling
error at all and the picture of where the graders differ is complete. Most already have an answer
from the rescue review; those are carried in pre-filled so the chemists only decide what is new.

A sample of the records they agree on is included as well, and this is the part that is easy to
leave out. It is drawn only from records the rescue review never touched: the forty-two it added
agree solely because their curated row was created from the chemists' own decision about them,
and asking again would be asking whether they agree with themselves. A chemist rejecting something *both* graders accepted is a miss neither of them
caught, and no amount of labelling disagreements would ever reveal one. That rate is what recall
depends on, so it has to be estimated rather than assumed.
"""
import json

import numpy as np
import pandas as pd

from _setup import ARTIFACTS, RUNS_DIR, judged, scored, show, sources

JUDGE, TARGET = "oss", "luna"        # the pair the database ships
AGREEMENTS = 50                      # sampled from the records both graders accepted
SEED = 20260824

DECIDED = ARTIFACTS / "gold/decisions/rescue_decisions_full.json"
EXTRACTION = RUNS_DIR / f"extract_{TARGET}/extract_{TARGET}_n4_r1"
VERDICTS = RUNS_DIR / f"judge_{JUDGE}_on_{TARGET}/judge_{JUDGE}_on_{TARGET}"


def already_decided() -> dict:
    """What the chemists have already ruled on, keyed by (doi, index)."""
    if not DECIDED.exists():
        return {}
    payload = json.loads(DECIDED.read_text(encoding="utf-8"))
    return {(d["doi"], d["index"]): d["answer"] for d in payload["decisions"]}


def cells() -> pd.DataFrame:
    """Every benchmark record, with which graders flagged it and why the metric objected."""
    both = scored(run=EXTRACTION).merge(judged(run=VERDICTS), on=["doi", "index"])
    both["agree"] = both.metric == both.judge

    # Why the metric objected. `situation` already separates the cases; naming them here keeps
    # the taxonomy in one place and avoids the evaluator's `reason` column, which carries penalty
    # arithmetic rather than a category.
    both["dispute"] = np.select(
        [both.agree,
         both.situation == "no curated counterpart",
         both.situation == "matched, names differ"],
        ["the graders agree",
         "the answer key has no such row",
         "matched, but the catalyst names differ"],
        default="matched, but the fields disagree")
    return both


def compute() -> pd.DataFrame:
    """The worklist: every disagreement, plus a weighted sample of the agreements."""
    frame = cells()
    settled = already_decided()

    disputed = frame[~frame.agree].copy()
    disputed["stratum"] = "graders disagree"
    disputed["weight"] = 1.0                       # a census carries no sampling error

    # Records added by the rescue review agree only because their own curated row was created
    # from the chemists' decision about them. Sampling those would be asking whether they agree
    # with themselves, so the agreement stratum is drawn from the records the review never
    # touched -- and the weight reflects that smaller population.
    agreed = frame[frame.agree & ~frame.apply(
        lambda r: (r.doi, r["index"]) in settled, axis=1)]
    take = min(AGREEMENTS, len(agreed))
    generator = np.random.default_rng(SEED)
    sample = agreed.iloc[generator.choice(len(agreed), take, replace=False)].copy()
    sample["stratum"] = "graders agree"
    sample["weight"] = len(agreed) / take

    work = pd.concat([disputed, sample])
    work["prefilled"] = [settled.get((r.doi, r.index), "") for r in work.itertuples()]
    columns = ["doi", "index", "stratum", "dispute", "weight", "prefilled"]
    return work.sort_values(["doi", "index"])[columns].reset_index(drop=True)


def main() -> None:
    sources(extraction=EXTRACTION, judge=VERDICTS)

    frame = cells()
    show(f"the population, {JUDGE} judging {TARGET} on the curated papers",
         pd.crosstab(frame.metric, frame.judge), fmt="{:.0f}")

    disputed = frame[~frame.agree]
    settled = already_decided()
    answered = sum(1 for r in disputed.itertuples() if (r.doi, r.index) in settled)
    show("disagreements", {
        "total": len(disputed),
        "already decided in the rescue review": answered,
        "still to decide": len(disputed) - answered,
    }, fmt="{:.0f}")
    show("what they are about", disputed.dispute.value_counts(), fmt="{:.0f}")

    work = compute()
    summary = work.groupby("stratum").agg(records=("doi", "size"), stands_for=("weight", "first"))
    summary["to decide"] = work[work.prefilled == ""].groupby("stratum").size()
    show("the worklist", summary, fmt="{:.1f}")
    print(f"\n{len(work)} records, {(work.prefilled == '').sum()} of them needing a decision")

    untouched = frame[frame.agree & ~frame.apply(
        lambda r: (r.doi, r["index"]) in settled, axis=1)]
    agreed = len(untouched)
    half = 1.96 * np.sqrt(0.10 * 0.90 / min(AGREEMENTS, agreed))
    print(f"\n  the agreement sample estimates how often a chemist rejects what both graders")
    print(f"  accepted. At a true rate near 10% and n={AGREEMENTS}, that is ±{half*100:.0f} points,")
    print(f"  or ±{half*agreed:.0f} records once weighted back to all {agreed}.")


if __name__ == "__main__":
    main()
