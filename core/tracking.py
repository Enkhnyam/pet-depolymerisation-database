from __future__ import annotations

from pathlib import Path

import weave

try:
    import wandb
except ImportError:  # tracking is optional; the pipeline runs without it
    wandb = None

from . import bundle

PROJECT = "llm-as-a-judge-for-evaluating-document-extraction-capabilities-of-llms"


def init_tracing(project: str = PROJECT) -> None:
    """Turn on Weave call-tracing for the whole process (traces run_llm etc.).

    Tracing is optional, so a missing or unreachable W&B endpoint must not stop a run.
    """
    try:
        weave.init(project)
    except Exception as exc:  # offline, no credentials, endpoint down
        print(f"tracing disabled ({type(exc).__name__}); the run continues")


def log_bundle(run_dir: Path, stage: str, project: str = PROJECT) -> None:
    """Log the metrics a stage just wrote into `run_dir` to a W&B run.

    Reads config.json (always) plus run_meta.json (extract) / eval.json (eval).
    Idempotent across invocations via resume-by-content-hash.
    """
    if wandb is None:
        return
    try:
        config = bundle.read_json(run_dir / "config.json")
        run = wandb.init(
            project=project,
            id=config["content_hash"][:16],   # stable across extract/eval processes
            resume="allow",
            name=config.get("run_name"),
            group=config.get("run_name"),
            tags=[stage, config.get("run_name", "")],
            config=config,                     # nested llm/harness params -> grouped in UI
        )
        if stage == "extract" and (run_dir / "run_meta.json").exists():
            m = bundle.read_json(run_dir / "run_meta.json")
            run.log({f"extract/{k}": m[k]
                     for k in ("n_papers", "prompt_tokens", "completion_tokens", "cost_usd")
                     if k in m})
        if stage == "eval" and (run_dir / "eval.json").exists():
            e = bundle.read_json(run_dir / "eval.json")
            run.log({f"eval/{k}": e[k]
                     for k in ("precision", "recall", "f1", "tp", "fp", "fn")
                     if k in e})
            run.log({f"eval/field_error/{f}": c
                     for f, c in e.get("field_error_counts", {}).items()})
        run.finish()
    except Exception as exc:  # never let tracking break the run
        print(f"[tracking] W&B logging skipped: {exc}")
