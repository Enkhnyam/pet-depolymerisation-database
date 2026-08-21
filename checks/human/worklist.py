"""Which records a second adjudication round should use.

The existing 48 cannot settle which grader is better: they were drawn on disagreements under a
judge rubric that was then rewritten, and only four disagreements survived. A new round has to
avoid both faults -- draw on the pair actually shipped, and change nothing about that pair
afterwards.

Two kinds of disagreement exist and they are not equally informative:

  matched, names differ   the graders disagree about chemistry, which is the question
  no curated counterpart  the metric auto-rejects because the answer key has no row; the judge
                          may well be right, but this mostly re-measures a limitation we already
                          know about

Both count for McNemar. A round drawn only from the first is the stronger evidence, and there may
not be enough of them -- which this reports rather than papering over.
"""
import pandas as pd

from _setup import RUNS_DIR, judged, scored, show, sources

JUDGE, TARGET = "oss", "luna"          # the pair the database ships
NEEDED = 30                            # pairs for 80% power at the rate observed so far


def compute() -> pd.DataFrame:
    """Every record the shipped graders disagree about, with what makes it informative."""
    extraction = RUNS_DIR / f"extract_{TARGET}/extract_{TARGET}_n4_r1"
    verdicts = RUNS_DIR / f"judge_{JUDGE}_on_{TARGET}/judge_{JUDGE}_on_{TARGET}"

    both = scored(run=extraction).merge(judged(run=verdicts), on=["doi", "index"])
    disputed = both[both.metric != both.judge].copy()
    disputed["informative"] = disputed.situation != "no curated counterpart"
    return disputed[["doi", "index", "situation", "metric", "judge", "informative"]]


def main() -> None:
    sources(shipped_extraction=RUNS_DIR / f"extract_{TARGET}/extract_{TARGET}_n4_r1",
            shipped_judge=RUNS_DIR / f"judge_{JUDGE}_on_{TARGET}/judge_{JUDGE}_on_{TARGET}")

    disputed = compute()
    strong = disputed[disputed.informative]

    show(f"disagreements available, {JUDGE} judging {TARGET}", {
        "total": len(disputed),
        "about chemistry (the metric could evaluate)": len(strong),
        "because the answer key had no row": len(disputed) - len(strong),
        "papers they span": disputed.doi.nunique(),
    }, fmt="{:.0f}")

    show("what each side claims", pd.crosstab(disputed.situation, disputed.judge), fmt="{:.0f}")

    print(f"\n{NEEDED} pairs are needed for 80% power at the rate observed so far.")
    if len(strong) >= NEEDED:
        print(f"  the {len(strong)} chemistry disagreements alone are enough")
    else:
        short = NEEDED - len(strong)
        print(f"  the {len(strong)} chemistry disagreements are {short} short, so a round must")
        print(f"  either take {short} from the {len(disputed) - len(strong)} answer-key cases,")
        print(f"  or curate more papers so that fewer records lack a counterpart")

    show("how they spread across papers",
         disputed.groupby("doi").size().describe()[["count", "mean", "max"]], fmt="{:.1f}")


if __name__ == "__main__":
    main()
