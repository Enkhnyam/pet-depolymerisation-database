"""The judge x extraction agreement matrix -- the paper's headline table.

Agreement here is between the two graders on the same records. No human labels are involved,
which is the point: this is the only number available on a corpus with no curated table.

Reported two ways. Over every record, the metric marks the surplus wrong without looking at it,
because it can only pair as many records as the answer key holds. Over records it could genuinely
evaluate, the two graders are compared on equal terms.
"""
import glob
from pathlib import Path

import pandas as pd

from _setup import CURATED, RUNS_DIR, judged, scored, show, sources

UNMATCHED = "no curated counterpart"


def find_runs(pattern: str, meta_file: str) -> dict:
    """Map a run's short name to its directory, for every run matching a pattern."""
    found = {}
    for path in glob.glob(str(RUNS_DIR / pattern / "*" / meta_file)):
        run_dir = Path(path).parent
        found[run_dir.parent.name] = run_dir
    return found


def compute() -> pd.DataFrame:
    """One row per judge x extraction cell. The numbers; no output.

    Figures import this so a panel and its printed table can never disagree.
    """
    extractions = {name.replace("extract_", ""): run_dir
                   for name, run_dir in find_runs("extract_*", "run_meta.json").items()}
    judges = {tuple(name.replace("judge_", "").split("_on_")): run_dir
              for name, run_dir in find_runs("judge_*_on_*", "judge_meta.json").items()}

    rows = []
    for (judge_name, target), judge_dir in sorted(judges.items()):
        if target not in extractions:
            continue
        metric = scored(run=extractions[target])[["doi", "index", "metric", "situation"]]
        both = metric.merge(judged(run=judge_dir), on=["doi", "index"])
        evaluable = both.query("situation != @UNMATCHED")

        rows.append({
            "judge": judge_name,
            "extraction": target,
            "records": len(both),
            "agreement": (both.metric == both.judge).mean(),
            "evaluable": len(evaluable),
            "agreement, evaluable": (evaluable.metric == evaluable.judge).mean(),
        })

    return pd.DataFrame(rows)


def main() -> None:
    sources(answer_key=CURATED, extractions=RUNS_DIR / 'extract_*',
            judges=RUNS_DIR / 'judge_*_on_*')
    frame = compute()
    show("per cell", frame.set_index(["judge", "extraction"]))
    show("agreement over every record",
         frame.pivot(index="judge", columns="extraction", values="agreement"))
    show("agreement over records the metric could evaluate",
         frame.pivot(index="judge", columns="extraction", values="agreement, evaluable"))


if __name__ == "__main__":
    main()
