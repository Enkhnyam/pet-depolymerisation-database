"""Rebuild an extraction bundle from its Weave traces, for a run that died before writing.

core/extraction.py holds every result in memory and writes the bundle only after the last paper
returns, so a single failure anywhere in a long run destroys all of it. That happened to
mass_luna_1shot: it reached 1026/1027, one paper exhausted its rate-limit retries, and the write
loop never ran -- three hours and $8.38 of completed work with nothing on disk.

The work was not actually lost. run_llm is a @weave.op whose postprocess keeps the parsed records,
and the target DOI is the first line of the last traced message, so both halves of an
extractions/*.json can be read back out of the trace. Weave stores the records under the schema's
aliases (PET_amount_g), the same form model_dump(by_alias=True) writes, and every value is put
back through Experiment before it is written -- so this reconstructs the bundle rather than
approximating it, and a record that would not validate is dropped loudly instead of silently
landing in the corpus.

Token and cost totals come from the litellm.completion calls underneath, which count retries the
way the billing does.

    recover_from_weave.py --run mass_luna_1shot --since 2026-08-23T13:15 \
                          --log logs/mass_luna_1shot.log
    recover_from_weave.py --run mass_luna_1shot --since ... --dry-run
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import weave

from core import bundle
from core.paths import RUNS_DIR
from core.schema import Experiment
from core.utils import doi_to_filename

PROJECT = "llm-as-a-judge-for-evaluating-document-extraction-capabilities-of-llms"
DOI_PREFIX = "Paper DOI: "
SCAN = 8000


def as_record(raw) -> dict | None:
    """A traced record back into the exact dict the bundle would have held.

    Weave hands these back as WeaveObjects, not dicts, so the fields are read off by name and
    handed to Experiment, which both normalises them and rejects anything malformed.
    """
    values = {}
    for name, field in Experiment.model_fields.items():
        key = field.alias or name
        value = getattr(raw, key, None)
        if value is None and field.alias:
            value = getattr(raw, name, None)
        if hasattr(value, "unwrap"):        # WeaveList of source_chunk_ids
            value = value.unwrap()
        elif isinstance(value, list):
            value = list(value)
        values[key] = value
    try:
        return Experiment.model_validate(values).model_dump(by_alias=True)
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(prog="recover_from_weave")
    ap.add_argument("--run", required=True, help="run directory under artifacts/runs/")
    ap.add_argument("--since", required=True,
                    help="ISO time (UTC) the run started, to exclude earlier runs' traces")
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--scan", type=int, default=SCAN, help="how many recent calls to walk")
    ap.add_argument("--log", type=Path,
                    help="the run's log, to total the 'Cost:' lines litellm reported; without it "
                         "cost_usd is recorded as 0 rather than guessed")
    ap.add_argument("--dry-run", action="store_true", help="report what it found, write nothing")
    args = ap.parse_args()

    run_dir = RUNS_DIR / args.run
    if not run_dir.exists():
        sys.exit(f"no such run directory: {run_dir}")
    since = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)

    client = weave.init(args.project)
    found: dict[str, list] = {}
    dropped = 0
    tokens = {"prompt": 0, "completion": 0}

    # litellm's success callback printed the billed cost of every call as it happened; that log is
    # the only surviving record of what the run actually cost, so it is totalled rather than
    # recomputed from a price table that does not know this deployment.
    cost = 0.0
    if args.log and args.log.exists():
        for line in args.log.read_text(errors="replace").splitlines():
            if line.startswith("Cost:"):
                try:
                    cost += float(line.split(":", 1)[1])
                except ValueError:
                    pass

    for call in client.get_calls(sort_by=[{"field": "started_at", "direction": "desc"}],
                                 limit=args.scan):
        started = call.started_at
        if started and started.replace(tzinfo=dt.timezone.utc) < since:
            continue
        op = str(call.op_name)

        if "/op/litellm.completion" in op:
            usage = (call.output or {}).get("usage") or {}
            tokens["prompt"] += usage.get("prompt_tokens") or 0
            tokens["completion"] += usage.get("completion_tokens") or 0
            continue

        if "/op/run_llm" not in op:
            continue
        messages = (call.inputs or {}).get("messages")
        records = (call.output or {}).get("records") if call.output else None
        if not messages or records is None:
            continue
        first = messages[-1]["content"].splitlines()[0]
        if not first.startswith(DOI_PREFIX):
            continue
        doi = first[len(DOI_PREFIX):].strip()
        if doi in found:                    # sorted newest first, so keep the newest attempt
            continue
        rebuilt = []
        for raw in records:
            one = as_record(raw)
            if one is None:
                dropped += 1
            else:
                rebuilt.append(one)
        found[doi] = rebuilt

    total = sum(len(v) for v in found.values())
    print(f"papers recovered   {len(found)}")
    print(f"records recovered  {total}")
    print(f"records rejected   {dropped}")
    print(f"tokens             {tokens['prompt']:,} prompt / {tokens['completion']:,} completion")
    print(f"cost from the log  ${cost:,.2f}")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    for doi, records in sorted(found.items()):
        bundle.write_json(run_dir / "extractions" / doi_to_filename(doi, "json"),
                          {"doi": doi, "records": records})

    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    config = json.loads((run_dir / "config.json").read_text())
    harness = config.get("harness_params", {})
    meta.update({
        "seed": harness.get("seed"),
        "model": config.get("llm_params", {}).get("model"),
        "git_commit": bundle.git_commit(),
        "started_at": since.isoformat(),
        "n_papers": len(found),
        "prompt_tokens": tokens["prompt"],
        "completion_tokens": tokens["completion"],
        "cost_usd": cost,
        "parse_failed_papers": meta.get("parse_failed_papers", 0),
        "finished_at": bundle.now_iso(),
        "recovered_from_weave": True,   # this bundle was rebuilt from traces, not written by the run
    })
    bundle.write_json(meta_path, meta)
    print(f"\nwrote {run_dir}/extractions ({len(found)} files) and run_meta.json")


if __name__ == "__main__":
    main()
