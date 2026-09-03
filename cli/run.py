import argparse

import litellm
from envyaml import EnvYAML

from core.paths import ROOT, ENV_FILE, output_root
from core import extraction, evaluation, parse, tracking


def track_cost(kwargs, completion_response, start_time, end_time):
    print("Cost:", kwargs.get("response_cost", 0))


def run_config(config_path: str, stage: str, limit: int | None) -> None:
    env = EnvYAML(str(ROOT / config_path), env_file=str(ENV_FILE))
    litellm.success_callback = [track_cost, *env.get("success_callback", [])]
    out = env["output_dir"] if "output_dir" in env else None
    run_dir = output_root(out) / env["run_name"]

    if stage in ("extract", "all"):
        extraction.run(env, run_dir, limit)
    if stage in ("eval", "all"):
        evaluation.run(env, run_dir)


def main():
    parser = argparse.ArgumentParser(prog="run")
    parser.add_argument("stage", choices=["extract", "eval", "parse", "all"], default="all")
    parser.add_argument("--config", type=str, default="rwth_bundle_config.yaml",
                        help="Single bundle config YAML")
    parser.add_argument("--configs", type=str, nargs="+", default=None,
                        help="Multiple config YAMLs to run in sequence (overrides --config)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of papers")
    parser.add_argument("--src", type=str, default=None, help="PDF source dir (parse stage)")
    parser.add_argument("--dest", type=str, default=None, help="Markdown dest dir (parse stage)")
    args = parser.parse_args()

    if args.stage == "parse":
        parse.run(args.src, args.dest)
        return

    tracking.init_tracing()   # Weave call-tracing on for the whole process
    for config_path in (args.configs or [args.config]):
        run_config(config_path, args.stage, args.limit)


if __name__ == "__main__":
    main()
