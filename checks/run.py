"""Run the checks. `run.py` alone runs all of them; pass paths to run a subset.

Scripts are not importable on their own -- they do `from _setup import *`, and this is what
puts checks/ on the path.
"""
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    # the 24-paper benchmark: the answer key, the graders on it, and the settings we chose
    "curated/answer_key.py",
    "curated/extractions.py",
    "curated/metric.py",
    "curated/matrix.py",
    "curated/judged_runs.py",
    "curated/field_types.py",
    "curated/thresholds.py",
    "curated/shots.py",
    "curated/source_tracking.py",

    # the database
    "database/corpus.py",
    "database/chemistry.py",
    "database/verdicts.py",
    "database/withinpaper.py",
    "database/formats.py",
    "database/provenance.py",

    # the 48 records two chemists adjudicated, and what a second round would need
    "human/growth.py",
    "human/worklist.py",
    "human/adjudicated.py",
    "human/integrity.py",

    "cost.py",
]

if __name__ == "__main__":
    here = Path(__file__).parent
    chosen = sys.argv[1:] or SCRIPTS
    failed = []

    for rel in chosen:
        print(f"\n\033[1m{'─' * 78}\n{rel}\n{'─' * 78}\033[0m")
        # PYTHONPATH is what makes `from _setup import *` resolve; a script run on its own
        # only gets its own directory on the path, not checks/. Output is captured rather than
        # inherited so it stays in order when the whole suite is piped to a file.
        result = subprocess.run([sys.executable, str(here / rel)], cwd=here, text=True,
                                capture_output=True,
                                env={**os.environ, "PYTHONPATH": str(here)})
        print(result.stdout.rstrip())
        if result.returncode:
            print(result.stderr.rstrip())
            failed.append(rel)

    print(f"\n{'─' * 78}\n{len(chosen) - len(failed)}/{len(chosen)} ran")
    for rel in failed:
        print(f"  FAILED {rel}")
    sys.exit(1 if failed else 0)
