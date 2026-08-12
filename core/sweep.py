import shutil

from envyaml import EnvYAML

from . import extraction, evaluation
from .paths import ENV_FILE


def load_config(config_path) -> dict:
    """Load a config YAML into a plain, mutable dict (resolves ${env} vars).

    EnvYAML objects don't support item assignment or deepcopy, so callers that
    need to override run_name / n_shots / etc. must go through this first.
    """
    env = EnvYAML(str(config_path), env_file=str(ENV_FILE))
    if not env:
        raise ValueError(f"Invalid or empty config file: {config_path}")
    hp = dict(env["harness_params"])
    hp["evaluation"] = dict(env["harness_params"]["evaluation"])
    cfg = {
        "run_name": env["run_name"],
        "success_callback": env["success_callback"] if "success_callback" in env else [],
        "llm_params": dict(env["llm_params"]),
        "harness_params": hp,
    }
    if "repeats" in env:                     # optional per-model repeat count (benchmark)
        cfg["repeats"] = env["repeats"]
    if "output_dir" in env:                  # optional per-config output folder (default runs/)
        cfg["output_dir"] = env["output_dir"]
    return cfg


def run_condition(env, run_dir, limit=None, force=False):
    config_exists   = (run_dir / "config.json").exists()     # extraction STARTED
    extraction_done = (run_dir / "run_meta.json").exists()   # extraction FINISHED
    evaluation_done = (run_dir / "eval.json").exists()       # eval FINISHED

    if evaluation_done and not force:
        print(f"skip {env['run_name']} (already complete)")
        return

    if extraction_done and not force:                        # extraction ok, only eval missing
        print(f"eval-only {env['run_name']} (reusing extractions)")
        evaluation.run(env, run_dir)                         # cheap, no re-extract
        return

    if config_exists:                                        # partial/crashed extraction
        print(f"re-running {env['run_name']} (removing incomplete {run_dir.name})")
        shutil.rmtree(run_dir)

    extraction.run(env, run_dir, limit)
    evaluation.run(env, run_dir)
