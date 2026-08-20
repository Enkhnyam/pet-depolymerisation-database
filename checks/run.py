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

    "golden_set/provenance.py",
    "golden_set/categories.py",
    "golden_set/composition.py",
    "golden_set/disagreements.py",

    "judge/scorecard.py",
    "judge/kappa.py",
    "judge/mcnemar.py",
    "judge/rescues.py",
    "judge/field_types.py",

    "studies/shots_ablation.py",
    "studies/source_tracking.py",
]

if __name__ == "__main__":
    HERE = Path(__file__).parent
    chosen = sys.argv[1:] or SCRIPTS
    failed = []

    for rel in chosen:
        print(f"\n\033[1m{'─' * 78}\n{rel}\n{'─' * 78}\033[0m")
        r = subprocess.run([sys.executable, str(HERE / rel)], cwd=HERE, text=True,
                           capture_output=True, env={**__import__("os").environ, "PYTHONPATH": str(HERE)})
        print(r.stdout.rstrip())
        if r.returncode:
            print(r.stderr.rstrip())
            failed.append(rel)

    print(f"\n{'─' * 78}")
    print(f"{len(chosen) - len(failed)}/{len(chosen)} ran" + (f"; failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)
