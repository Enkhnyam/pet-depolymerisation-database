"""What the chemists' decisions say about the two graders.

This is the round checks/human/precision.py was sizing. Each of the 115 adjudicated records
carries a human answer, a stratum and a weight, and each grader either flagged it or did not, so
precision and recall follow directly -- with one wrinkle that decides whether the numbers mean
anything.

The wrinkle is the weight. Flagged records are censused, so they stand for themselves; the
records both graders accepted are a sample of a much larger pool and stand for about four records
each. Counting the raw decisions would therefore understate misses by a factor of four and make
both graders look far better at recall than they are. Everything below is weighted.

Precision carries no sampling error, because its denominator is censused. Recall does, and its
interval comes from resampling the accepted stratum -- which is why the interval is wide and why
precision.py argued for a bigger sample before the round was sent.

    adjudicated.py                          the chemists' decisions, as ingested
    adjudicated.py --decisions <path>       a specific file
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta, binomtest

from _setup import ARTIFACTS, show, sources
from human import significance, worklist
from human.significance import power_at

CONFIDENCE = 0.95
POWER_RATES = (0.60, 0.65, 0.70, 0.75, 0.80)
DRAWS = 20_000
SEED = 20260824

DECISIONS_DIR = ARTIFACTS / "gold" / "decisions"
REAL = DECISIONS_DIR / "adjudicated.json"          # written by cli/ingest_adjudications.py

BANNER = "!" * 78


def load(path: Path) -> tuple[pd.DataFrame, bool]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(payload["decisions"])
    # a record the two chemists actively decided differently is left unanswered by the ingest
    frame = frame[frame.human.notna()]
    if "design_stratum" not in frame:
        frame["design_stratum"] = frame.stratum
    return frame, bool(payload.get("simulated"))


def payload_pool(path: Path) -> dict:
    """What the ingest recorded about the pool the accepted stratum was drawn from."""
    return json.loads(path.read_text(encoding="utf-8")).get("pool", {})


def interval(hits: float, total: float) -> tuple[float, float]:
    """Jeffreys interval on a proportion; accepts weighted counts."""
    if total <= 0:
        return float("nan"), float("nan")
    return beta.interval(CONFIDENCE, hits + 0.5, max(total - hits, 0) + 0.5)


def compute(path: Path) -> dict:
    decisions, simulated = load(path)
    # cells() carries its own extracted_index from the curated matching, which is not the record
    # index the worklist and the page key on; "index" is. Take the columns we need and name them
    # ourselves rather than renaming into a collision.
    cells = pd.DataFrame(worklist.cells())
    graders = pd.DataFrame({"doi": cells["doi"], "extracted_index": cells["index"],
                            "metric": cells["metric"], "judge": cells["judge"]})

    merged = decisions.merge(graders, on=["doi", "extracted_index"],
                             how="left", validate="one_to_one")
    merged["wrong"] = merged.human == "incorrect"

    rows = []
    for grader in ("metric", "judge"):
        flagged = merged[grader] == "incorrect"
        weight = merged.weight

        # precision: of what this grader flagged, how much the chemists also called wrong.
        # Flagged records are censused, so weights here are all 1 and the interval is a plain
        # proportion on the number of flags.
        flags = int(flagged.sum())
        right = int((flagged & merged.wrong).sum())
        p_low, p_high = interval(right, flags)

        # recall: of everything the chemists called wrong, how much this grader caught. The
        # denominator reaches into the accepted pool, so it has to be weighted.
        wrong_weight = float((merged.wrong * weight).sum())
        caught_weight = float((merged.wrong & flagged).astype(float).mul(weight).sum())
        recall = caught_weight / wrong_weight if wrong_weight else float("nan")

        precision = right / flags if flags else float("nan")
        f1 = (2 * precision * recall / (precision + recall)
              if precision and recall and precision + recall else float("nan"))

        rows.append({"grader": grader, "flagged": flags, "of those wrong": right,
                     "precision": precision, "prec low": p_low, "prec high": p_high,
                     "recall": recall, "F1": f1})

    # Recall's interval. The censused strata are exact, so all the uncertainty sits in how many
    # wrong records hide in the pool the accepted stratum was drawn from. Resampling around the
    # observed rate would be wrong when that rate is zero: none of 47 being wrong does not mean
    # none of 189 are, only that the rate is under about 6%. So the rate is drawn from its
    # posterior and scaled to the pool. A grader catches nothing here by definition -- "both
    # accepted it" means neither flagged it -- so only the denominator moves.
    rng = np.random.default_rng(SEED)
    accepted = merged[merged.design_stratum == "both accepted it"]
    censused = merged[merged.design_stratum != "both accepted it"]
    spread = {}
    if len(accepted):
        # Sum the weights rather than assuming one: after a benchmark correction two records
        # moved in from a census and carry weight 1, so the stratum holds 4.02-weighted sampled
        # records beside unweighted censused ones and a single multiplier overstates the pool.
        pool = round(float(accepted.weight.sum()))
        seen_wrong = int(accepted.wrong.sum())
        rate = beta.rvs(seen_wrong + 0.5, len(accepted) - seen_wrong + 0.5,
                        size=DRAWS, random_state=rng)
        missed = rate * pool
        censused_wrong = float((censused.wrong * censused.weight).sum())
        for row in rows:
            caught = float((censused.wrong & (censused[row["grader"]] == "incorrect"))
                           .astype(float).mul(censused.weight).sum())
            draws = caught / np.maximum(censused_wrong + missed, 1e-9)
            spread[row["grader"]] = tuple(np.percentile(
                draws, [(1 - CONFIDENCE) / 2 * 100, (1 + CONFIDENCE) / 2 * 100]))

    table = pd.DataFrame(rows).set_index("grader")
    table["recall low"] = [spread.get(g, (np.nan, np.nan))[0] for g in table.index]
    table["recall high"] = [spread.get(g, (np.nan, np.nan))[1] for g in table.index]

    # Cohen's kappa, each grader against the chemists. Weighted, because it is a statement about
    # the whole population and the accepted stratum stands for four records each. The discount is
    # heavy here: most records are correct, so two raters agree often by luck alone.
    kappas = {}
    total = float(merged.weight.sum())
    for grader in ("metric", "judge"):
        flagged = merged[grader] == "incorrect"
        a = float((flagged & merged.wrong).astype(float).mul(merged.weight).sum())
        b = float((flagged & ~merged.wrong).astype(float).mul(merged.weight).sum())
        c = float((~flagged & merged.wrong).astype(float).mul(merged.weight).sum())
        d = total - a - b - c
        observed = (a + d) / total
        chance = ((a + b) / total) * ((a + c) / total) + ((c + d) / total) * ((b + d) / total)
        kappas[grader] = (observed - chance) / (1 - chance) if chance < 1 else float("nan")
    table["kappa"] = [kappas[g] for g in table.index]

    # McNemar. Only records where exactly one grader matched the chemists say anything about which
    # is better; where both agree the record is silent whichever way it was decided. Unweighted and
    # unstratified, because every such record is in a censused stratum by construction: the two
    # graders can only differ where they disagree, and every disagreement was decided.
    right = {g: merged[g].map({"incorrect": True, "correct": False}) == merged.wrong
             for g in ("metric", "judge")}
    judge_only = int((right["judge"] & ~right["metric"]).sum())
    metric_only = int((right["metric"] & ~right["judge"]).sum())
    pairs = judge_only + metric_only
    mcnemar = {"informative pairs": pairs, "favouring the judge": judge_only,
               "favouring the metric": metric_only,
               "p": binomtest(judge_only, pairs).pvalue if pairs else float("nan")}

    # The power the design carried at the number of pairs it actually returned. Reported because
    # the alternative -- quoting a p-value alone -- says nothing about what the round could have
    # detected had it gone the other way.
    power = {rate: power_at(pairs, rate) for rate in POWER_RATES} if pairs else {}

    return {"table": table, "records": merged, "simulated": simulated, "path": path,
            "mcnemar": mcnemar, "power": power, "pool": payload_pool(path),
            "prior_pairs": significance.prior_pairs()}


def main() -> None:
    parser = argparse.ArgumentParser(prog="adjudicated")
    parser.add_argument("--decisions", type=Path, default=None)
    args = parser.parse_args()

    # No silent fallback to a stand-in. Before the chemists answered, this check ran against
    # simulated decisions to prove the analysis worked; now that real answers exist, quietly
    # scoring anything else would be the worst failure this file could have.
    path = args.decisions or REAL
    if not path.exists():
        print(f"no decisions: expected {path.relative_to(ARTIFACTS.parent)}")
        print("run cli/ingest_adjudications.py to build it from the chemists' exports")
        return

    result = compute(path)
    if result["simulated"]:
        print(BANNER)
        print("THESE NUMBERS COME FROM SIMULATED DECISIONS, NOT FROM CHEMISTS.")
        print(f"source: {path.name}")
        print("They exist to prove the analysis runs. None of them may go in the paper.")
        print(BANNER)
        print()

    sources(extraction=worklist.EXTRACTION, judge=worklist.VERDICTS, decisions=path)

    merged = result["records"]
    show("what the chemists decided", merged.groupby("design_stratum").agg(
        records=("human", "size"),
        wrong=("wrong", "sum"),
        stands_for=("weight", lambda s: round(float(s.sum()), 1))))

    show("each grader against the chemists (recall, F1 and kappa are weighted)",
         result["table"].round(3))

    mcnemar = result["mcnemar"]
    show("McNemar -- which grader is better, on the records where exactly one was right",
         {k: v for k, v in mcnemar.items() if k != "p"}, fmt="{:.0f}")
    print(f"\n  p = {mcnemar['p']:.4f}" if mcnemar["informative pairs"] else "\n  no pairs")

    if result["power"]:
        show(f"what the design could have detected, at the {mcnemar['informative pairs']} pairs "
             f"it returned",
             pd.Series({f"judge right {int(r * 100)}% of the time": v
                        for r, v in result["power"].items()}), fmt="{:.2f}")
        print(f"\n  it returned {mcnemar['favouring the judge']} of "
              f"{mcnemar['informative pairs']}, a rate of "
              f"{mcnemar['favouring the judge'] / mcnemar['informative pairs']:.0%}")
        print(f"  the earlier random round produced {result['prior_pairs']} pairs, too few for any "
              f"outcome to reach significance")

    if result["simulated"]:
        print()
        print(BANNER)
        print("SIMULATED. Re-run against the real decisions before quoting anything.")
        print(BANNER)


if __name__ == "__main__":
    main()
