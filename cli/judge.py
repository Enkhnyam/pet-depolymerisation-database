import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # repo root importable
import argparse
import json
from pathlib import Path

from envyaml import EnvYAML

from core.paths import ROOT, ENV_FILE, ARTIFACTS, output_root
from core import judge, tracking


def main():
    parser = argparse.ArgumentParser(prog="judge")
    parser.add_argument("--config", default="judge_configs/judge_mistral_v1.yaml",
                        help="Judge config YAML")
    parser.add_argument("--limit", type=int, default=None, help="Limit papers (debug)")
    parser.add_argument("--split", choices=["dev", "test"], default=None,
                        help="Judge only this half of gold/split.json (one call per paper)")
    args = parser.parse_args()

    env = EnvYAML(str(ROOT / args.config), env_file=str(ENV_FILE))
    run_dir = output_root(env["harness_params"].get("output_dir")) / env["run_name"]

    dois = None
    if args.split:
        dois = set(json.loads((ARTIFACTS / "gold" / "split.json").read_text())[args.split])

    tracking.init_tracing()
    judge.run(env, run_dir, limit=args.limit, dois=dois)


if __name__ == "__main__":
    main()
