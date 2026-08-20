"""Run the checks. `run.py` alone runs all of them; pass paths to run a subset.

Scripts are not importable on their own -- they do `from _setup import *`, and this is what
puts checks/ on the path.
"""
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "ground_truth/dataset.py",
    "ground_truth/curation_quality.py",
    "ground_truth/outcome_identity.py",

    "metric/scores.py",
    "metric/penalties.py",
    "metric/threshold_sensitivity.py",
    "metric/error_taxonomy.py",
    "metric/matching_quality.py",
    "metric/catalyst_gate.py",
    "metric/catalyst_names.py",
    "metric/cost.py",

    "golden_set/composition.py",
    "golden_set/growth.py",
    "golden_set/disagreements.py",

    "judge/scorecard.py",
    "judge/significance.py",
    "judge/rescues.py",
    "judge/field_types.py",
    "judge/matrix.py",
    "judge/power.py",

    "database/corpus.py",
    "database/verdicts.py",
    "database/provenance.py",
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
