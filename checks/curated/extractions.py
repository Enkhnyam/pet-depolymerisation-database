"""Every benchmark extraction scored against the curated answer key.

This is the table the model choice was made from. Scoring one arbitrary run says nothing; the
comparison is the point.
"""
import glob
from pathlib import Path

import pandas as pd

from _setup import CURATED, RUNS_DIR, curated, records, show, sources, totals


def main() -> None:
    sources(answer_key=CURATED, extractions=RUNS_DIR / 'extract_*')
    rows = []
    for path in sorted(glob.glob(str(RUNS_DIR / "extract_*/*/run_meta.json"))):
        run_dir = Path(path).parent
        result = totals(run=run_dir)
        rows.append({
            "model": run_dir.parent.name.replace("extract_", ""),
            "records": len(records(run_dir)),
            "precision": result["precision"],
            "recall": result["recall"],
            "f1": result["f1"],
            "correct": result["tp"],
            "false alarms": result["fp"],
            "missed": result["fn"],
        })

    print(f"\nscored against {len(curated())} curated experiments from "
          f"{curated().doi.nunique()} papers")
    show("benchmark extractions", pd.DataFrame(rows).set_index("model"))


if __name__ == "__main__":
    main()
