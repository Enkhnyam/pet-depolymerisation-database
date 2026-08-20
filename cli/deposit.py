import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo root importable
import argparse
import json
import shutil

from core.paths import ROOT, ARTIFACTS, RUNS_DIR
from core import deposit

README = """# Reproducibility deposit

Recompute the paper's extraction-evaluation numbers with no API keys and no network.

## Layout
- `runs/<path>/` — one bundle per experimental run (grouped by experiment):
  - `config.json` — exact configuration (content-hashed)
  - `extractions/` — model-extracted records (facts)
  - `eval.json` — the reported precision / recall / F1
  - `labels.json` — per-record TP/FP/FN verdicts
  - `raw/` — full prompt + model response, included **only** for the openly-licensed
    papers (see `CREDITS.md`)
- `curated_data_public.json` — ground-truth records; full text kept only for licensable papers
- `core/` + `eval_bundle.py` — the evaluation code
- `CREDITS.md` — source papers and their licenses

## Reproduce a run's numbers
```
pip install -r requirements.txt
python eval_bundle.py runs/<path>
```
Prints the recomputed P/R/F1 next to the published values and reports MATCH.

## Licensing
Redistributed paper content is under CC-BY / CC-BY-NC-SA with attribution
(`CREDITS.md`); the combined dataset is therefore CC-BY-NC-SA (non-commercial,
share-alike).
"""


def find_runs(names: list[str]) -> list:
    """The run bundles to publish, given as paths relative to runs/."""
    return [RUNS_DIR / n for n in names]


def main():
    parser = argparse.ArgumentParser(prog="deposit")
    parser.add_argument("--out", default="deposit", help="Output directory")
    parser.add_argument("--runs", nargs="+", required=True,
                        help="Run paths relative to runs/, e.g. prompt_v2/run_n4_r1")
    args = parser.parse_args()

    run_dirs = [d for d in find_runs(args.runs) if (d / "config.json").exists()]
    if not run_dirs:
        print(f"no run bundles found under {RUNS_DIR}")
        return

    out = ARTIFACTS / args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for run_dir in run_dirs:
        rel = run_dir.relative_to(RUNS_DIR)                  # e.g. prompt_v2/run_n4_r1
        kept, dropped = deposit.sanitize_run(run_dir, out / "runs" / rel)
        print(f"{rel}: raw kept={kept} dropped={dropped}")

    config_data = json.loads((run_dirs[0] / "config.json").read_text(encoding="utf-8"))
    curated_path = config_data["harness_params"].get("curated_data_path", "curated_data_json_by_doi.json")
    deposit.sanitize_curated(curated_path, out / "curated_data_public.json")
    deposit.write_credits(out / "CREDITS.md")

    (out / "core").mkdir()
    for f in (ROOT / "core").glob("*.py"):
        shutil.copy2(f, out / "core" / f.name)              # f is already the full path
    shutil.copy2(ROOT / "cli" / "eval_bundle.py", out / "eval_bundle.py")
    shutil.copy2(ROOT / "pyproject.toml", out / "pyproject.toml")     # full deps for re-running the pipeline
    (out / "requirements.txt").write_text("numpy\nscipy\npydantic\n")  # minimal deps for eval_bundle.py
    (out / "README.md").write_text(README)
    print(f"\ndeposit -> {out}")


if __name__ == "__main__":
    main()
