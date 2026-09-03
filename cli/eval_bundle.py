"""Recompute a run bundle's eval metrics from its extractions + the public
curated facts, and compare to the bundle's own eval.json.

    python eval_bundle.py runs/<run_name>

No API keys, no network. Requires only: numpy, scipy, pydantic.
This is the reproducibility path — a reviewer runs this against the deposited
data and confirms the numbers match the paper.
"""
import json
import sys
import argparse
from pathlib import Path

from core.schema import Experiment, load_curated
from core.evaluation import evaluate

HERE = Path(__file__).resolve().parent               # the deposit dir this script lives in
CURATED = HERE / "curated_data_public.json"

def check_if_run_matches(run_dir: Path) -> tuple[bool, str]:
    ev = json.loads((run_dir / "config.json").read_text())["harness_params"]["evaluation"]
    curated = load_curated(CURATED)

    extracted_by_doi = {}
    for f in sorted((run_dir / "extractions").glob("*.json")):
        d = json.loads(f.read_text())
        extracted_by_doi[d["doi"]] = [Experiment.model_validate(r) for r in d["records"]]

    result, _ = evaluate(
        curated, extracted_by_doi,
        tp_threshold=ev["tp_threshold"],
        catalyst_threshold=ev["catalyst_threshold"],
        numeric_tolerance=ev["numeric_tolerance"],
    )
    published = json.loads((run_dir / "eval.json").read_text())

    ok = all(abs(result[k] - published[k]) < 1e-9 for k in ("precision", "recall", "f1"))
    return ok, f"recomputed: P={result['precision']:.3f} R={result['recall']:.3f} F1={result['f1']:.3f}, published: P={published['precision']:.3f} R={published['recall']:.3f} F1={published['f1']:.3f}"

def main():
    parser = argparse.ArgumentParser(prog="eval_bundle", description=__doc__)
    parser.add_argument("run_dir", nargs="?", default=None, help="Run directory (e.g. runs/<run_name>)")
    args = parser.parse_args()

    all_matched = True

    if args.run_dir is None:
        all_runs = [d for d in sorted((HERE / "runs").glob("*")) if d.is_dir()]
    else:
        run_dir = Path(args.run_dir)
        all_runs = [run_dir if run_dir.is_absolute() else HERE / run_dir]

    for run_dir in all_runs:
        ok, msg = check_if_run_matches(run_dir)
        print(f"{'Match' if ok else 'Mismatch'}-{run_dir.name}: {msg}")
        if not ok:
            all_matched = False

    sys.exit(0 if all_matched else 1)


if __name__ == "__main__":
    main()
