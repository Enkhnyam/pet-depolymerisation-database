"""Will the new round support precision, recall and F1 with usable error bars?

Precision asks: of the records a grader flagged, how many were really wrong? That question is
answered entirely by flagged records, and the worklist censuses every one of them -- all 53
disagreements and the dozen both graders flagged -- so precision carries no sampling error. Its
width is only the width of a proportion measured on however many records that grader flagged,
which is why the judge (15 flags) is estimated far less sharply than the metric (62).

Recall asks: of the records that were really wrong, how many did the grader flag? Its denominator
includes the records *neither* grader flagged, and the only way to know how many of those are
wrong is to ask a chemist about a sample of them. So recall inherits the sample's error, and this
check exists to say how large that is before the round is sent rather than after.

F1 is the harmonic mean of the two, so it is as wide as recall.
"""
import numpy as np
import pandas as pd
from scipy.stats import beta

from _setup import show, sources
from human import worklist

CONFIDENCE = 0.95
DRAWS = 20_000
SEED = 20260824
RATES = [0.03, 0.05, 0.10]      # plausible rates at which a chemist rejects an accepted record


def wilson(hits: int, n: int) -> float:
    """Half-width of the interval around a proportion, in percentage points."""
    low, high = beta.interval(CONFIDENCE, hits + 0.5, n - hits + 0.5)
    return (high - low) / 2 * 100


def recall_range(flagged: int, correct_rate: float, pool: int, take: int, miss_rate: float,
                 generator) -> tuple[float, float, float]:
    """Recall and the interval around it, from a sample of `take` out of a `pool` of `pool`.

    The true positives are censused, so all the noise is in the estimated misses: a count seen in
    the sample, scaled back up to the whole pool. The sample is drawn without replacement from a
    pool of a couple of hundred, so the draws are hypergeometric -- a binomial would ignore that
    the error falls to nothing as the sample approaches the pool.
    """
    found = flagged * correct_rate
    wrong = round(pool * miss_rate)
    seen = generator.hypergeometric(wrong, pool - wrong, take, DRAWS)
    missed = seen / take * pool
    draws = found / (found + missed)
    low, high = np.percentile(draws, [(1 - CONFIDENCE) / 2 * 100, (1 + CONFIDENCE) / 2 * 100])
    return found / (found + wrong), low, high


def main() -> None:
    sources(extraction=worklist.EXTRACTION, judge=worklist.VERDICTS,
            decisions=worklist.DECIDED)
    frame = worklist.cells()
    settled = worklist.already_decided()
    untouched = frame[frame.agree & ~frame.apply(
        lambda r: (r.doi, r["index"]) in settled, axis=1)]

    both_flagged = int((untouched.judge == "incorrect").sum())
    pool = int((untouched.judge == "correct").sum())
    judge_flags = int((frame.judge == "incorrect").sum())
    metric_flags = int((frame.metric == "incorrect").sum())

    show("what each grader flagged, all of it decided in this round", {
        "the judge flagged": judge_flags,
        "  the judge alone": judge_flags - both_flagged,
        "the metric flagged": metric_flags,
        "  the metric alone": metric_flags - both_flagged,
        "both flagged": both_flagged,
        "neither flagged, never reviewed": pool,
    }, fmt="{:.0f}")

    rows = []
    for name, flags in [("judge", judge_flags), ("metric", metric_flags)]:
        for correct in (0.6, 0.7, 0.8):
            rows.append({"grader": name, "if it was right this often": correct,
                         "records flagged": flags,
                         "precision +/- pt": wilson(round(flags * correct), flags)})
    show("precision, from a census of the flagged records -- no sampling error",
         pd.DataFrame(rows).set_index(["grader", "if it was right this often"]), fmt="{:.1f}")

    generator = np.random.default_rng(SEED)
    rows = []
    for take in (20, 50, 100, pool):
        for rate in RATES:
            recall, low, high = recall_range(judge_flags, 0.7, pool, take, rate, generator)
            rows.append({"agreements sampled": take,
                         "if chemists reject this share of them": rate,
                         f"records missed, of {pool}": round(pool * rate),
                         "judge recall": recall, "as low as": low, "as high as": high})
    show("recall, which the sample drives -- judge, assuming 70% of its flags stand",
         pd.DataFrame(rows).set_index(["agreements sampled",
                                       "if chemists reject this share of them"]), fmt="{:.2f}")

    print("\n  Precision is settled either way: the round decides every flagged record, so the")
    print(f"  metric lands within a few points and the judge within roughly "
          f"{wilson(round(judge_flags * 0.7), judge_flags):.0f} -- the judge is")
    print("  wider only because it flags fewer records, and nothing but flagging more would fix it.")
    print("\n  Recall is the weak number, and no sample of this size rescues it. The missed")
    print(f"  records are counted in the sample and scaled up to all {pool}, so at 20 records one")
    print("  extra rejection moves the estimate by a third of the answer. Fifty helps and is still")
    print("  wide. Recall becomes exact only by deciding all of them, which is a different round.")
    print("  Report precision as the headline, and recall and F1 with their intervals attached.")


if __name__ == "__main__":
    main()
