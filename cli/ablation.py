import argparse
import copy

import litellm

from core.paths import ABLATION_CONFIGS_DIR, output_root
from core import tracking, sweep


def main():
    parser = argparse.ArgumentParser(prog="ablation")
    parser.add_argument("--config", default="openai_oss_120b.yaml", help="Config YAML in configs/extract/")
    parser.add_argument("--shots", type=int, nargs="*", default=[0, 1, 2, 3, 4, 5, 6],
                        help="n_shots values to sweep; pass one value to hold shots fixed")
    parser.add_argument("--repeats", type=int, default=5, help="Repeats per n_shots value")
    parser.add_argument("--limit", type=int, default=None, help="Limit papers (debug/dry-run)")
    parser.add_argument("--prefix", default=None, help="run_name prefix (default: base name up to _n)")
    parser.add_argument("--force", action="store_true", help="Re-run conditions even if already complete")
    parser.add_argument("--workers", type=int, default=None, help="Concurrent papers per run")
    args = parser.parse_args()

    base = sweep.load_config(ABLATION_CONFIGS_DIR / args.config)
    prefix = args.prefix or base["run_name"]
    litellm.success_callback = base["success_callback"]
    tracking.init_tracing()

    conditions = [(n, r) for n in args.shots for r in range(1, args.repeats + 1)]
    # With a single --shots value the sweep is over repeats alone, which is how the
    # source-tracking arms are run: two configs differing in one flag, repeated.
    sweeping = "shots" if len(args.shots) > 1 else "repeats"
    print(f"ablation: {len(conditions)} conditions over {sweeping} "
          f"(shots={args.shots} x {args.repeats} repeats), prefix={prefix!r}")

    for n, r in conditions:
        env = copy.deepcopy(base)
        # For ablation we set n_shots manually regardless of what is in the config file
        env["harness_params"]["n_shots"] = n
        if args.workers:
            env["harness_params"]["max_workers"] = args.workers
        env["run_name"] = f"{prefix}_n{n}_r{r}"
        run_dir = output_root(base["harness_params"].get("output_dir")) / env["run_name"]

        sweep.run_condition(env, run_dir, limit=args.limit, force=args.force)
        print(f"=== {env['run_name']} (n_shots={n}, repeat={r}) ===\n")

if __name__ == "__main__":
    main()
