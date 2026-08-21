"""What each judge said about each extraction, on the curated papers.

Table~1 asks whether the two graders agree. This asks something different: how good is each
extraction according to the judge, and does the judge's verdict track what the curated table says?
If a judge's pass rate rises and falls with F1 across models, its pass rate is readable as a
quality estimate -- which is the assumption the whole database rests on.

Precision is the useful column. A judge that accepts everything has a pass rate near one and tells
you nothing; precision against the metric's verdict shows whether it is discriminating.
"""
import glob
from pathlib import Path

import pandas as pd

from _setup import CURATED, RUNS_DIR, judged, scored, show, sources, totals


def compute() -> pd.DataFrame:
    """One row per judge x extraction cell: the judge's pass rate beside the measured F1."""
    extractions = {}
    for path in glob.glob(str(RUNS_DIR / "extract_*/*/run_meta.json")):
        run_dir = Path(path).parent
        extractions[run_dir.parent.name.replace("extract_", "")] = run_dir

    rows = []
    for path in glob.glob(str(RUNS_DIR / "judge_*_on_*/*/judge_meta.json")):
        run_dir = Path(path).parent
        judge_name, target = run_dir.parent.name.replace("judge_", "").split("_on_")
        if target not in extractions:
            continue

        verdicts = judged(run=run_dir)
        metric = scored(run=extractions[target])[["doi", "index", "metric"]]
        both = metric.merge(verdicts, on=["doi", "index"])

        accepted = both.judge == "correct"
        rows.append({
            "judge": judge_name,
            "extraction": target,
            "measured f1": totals(run=extractions[target])["f1"],
            "judge pass rate": accepted.mean(),
            # of the records this judge accepted, how many the curated table also accepts
            "precision": (both.metric[accepted] == "correct").mean(),
            "records": len(both),
        })
    return pd.DataFrame(rows).sort_values(["judge", "extraction"])


def main() -> None:
    sources(answer_key=CURATED, extractions=RUNS_DIR / "extract_*",
            judges=RUNS_DIR / "judge_*_on_*")

    frame = compute()
    show("each judge on each extraction", frame.set_index(["judge", "extraction"]))

    print("\ndoes a judge's pass rate track the measured quality?")
    for judge_name, group in frame.groupby("judge"):
        if len(group) > 2:
            rho = group["judge pass rate"].corr(group["measured f1"], method="spearman")
            print(f"  {judge_name:6s} Spearman {rho:+.2f} across {len(group)} extractions")


if __name__ == "__main__":
    main()
