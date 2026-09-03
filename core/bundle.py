from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def unpack_config(env) -> dict:
    """Plain, secret-free config dict suitable for hashing and snapshotting.

    NOTE: api_key is deliberately dropped so it never lands in a bundle.
    """
    llm_params = {k: v for k, v in dict(env["llm_params"]).items() if k != "api_key"}
    # prompt_file stays in. It used to be stripped alongside api_key, which meant a run bundle
    # recorded every setting except which prompt produced it -- and the prompt version files in
    # prompts/ were the only remaining record of that, kept by hand beside a git repository.
    # A different prompt is a different run, so it belongs in the hash.
    harness_params = dict(env["harness_params"])
    return {
        "run_name": env["run_name"],
        "llm_params": llm_params,
        "harness_params": harness_params,
    }


def content_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
