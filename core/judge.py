"""LLM-as-judge: pointwise, reference-free faithfulness verdicts, batched per paper.

Reads an extraction bundle and judges its records against each paper's full text. One
API call per paper (rubric + paper text + all its records -> a verdict per record), so a
full run costs one call per paper, not one per record. Writes a judge bundle:
config.json (content-hashed), verdicts/<doi>.json, judge_meta.json. The judge never sees
the curated data or the metric's verdicts."""
import json
from pathlib import Path
from typing import Literal

import weave
import litellm
from tqdm import tqdm

from pydantic import BaseModel, Field, ValidationError

from .utils import filename_to_doi, doi_to_filename
from . import bundle, tracking
from .paths import prompt_path, data_path, RUNS_DIR


class FieldFix(BaseModel):
    """One field the judge would change, and what it would change it to."""
    field: str = Field(description="Name of the field to correct")
    value: str | float | None = Field(
        None, description="The corrected value, or null if the field should be emptied")
    evidence: str = Field("", description="Where in the paper the corrected value comes from")


class RecordVerdict(BaseModel):
    extracted_index: int
    # critique first: reason before committing to a verdict (structured "think step by step").
    critique: str = Field(description="2-5 sentences citing the specific evidence")
    bad_fields: list[str] = Field(default_factory=list,
                                  description="Names of fields judged wrong/unsupported/missing")
    verdict: Literal["correct", "incorrect"]
    # Applying these to the extracted record is what turns a judged mass extraction into a
    # corrected one, so a fix is required for every bad field the judge can actually repair.
    fixes: list[FieldFix] = Field(
        default_factory=list,
        description="Corrections for the bad fields, where the paper supports a specific value")
    drop_record: bool = Field(
        False, description="True when the record should be removed rather than corrected")


class BatchVerdict(BaseModel):
    verdicts: list[RecordVerdict]


OUTPUT_SPEC = (
    'Return ONLY a JSON object with one entry per record, matching extracted_index:\n'
    '{"verdicts": [{"extracted_index": <int>, "critique": "...", "bad_fields": [...], '
    '"verdict": "correct" | "incorrect", '
    '"fixes": [{"field": "...", "value": <number|string|null>, "evidence": "..."}], '
    '"drop_record": true | false}, ...]}')


def read_rubric(harness_params: dict) -> str:
    return prompt_path(harness_params["rubric_file"]).read_text(encoding="utf-8")


def construct_messages(rubric: str, full_text: str, records: list[dict]) -> list[dict]:
    numbered = "\n\n".join(f"RECORD {i}:\n{json.dumps(r, indent=2)}"
                           for i, r in enumerate(records))
    return [{"role": "system", "content": rubric + "\n\n" + OUTPUT_SPEC},
            {"role": "user",
             "content": f"PAPER TEXT:\n{full_text}\n\nJudge each of the {len(records)} "
                        f"extracted records below.\n\n{numbered}"}]


@weave.op(postprocess_output=lambda out: {"n": len(out[0].verdicts) if out and out[0] else 0})
def cost(resp) -> float:
    try:
        return float(litellm.completion_cost(completion_response=resp) or 0.0)
    except Exception:
        return float((getattr(resp, "_hidden_params", {}) or {}).get("response_cost") or 0.0)


def run_llm(llm_params: dict, messages, **kwargs):
    try:
        resp = litellm.completion(messages=messages, response_format=BatchVerdict,
                                  num_retries=5, **llm_params, **kwargs)
    except litellm.AuthenticationError as e:
        raise RuntimeError(f"Authentication error: {e}. Check your API key.")
    except litellm.RateLimitError as e:
        raise RuntimeError(f"Rate limit / quota error: {e}. Try again later or switch judge model.")
    except litellm.APIError as e:
        raise RuntimeError(f"API error: {e}. LLM service issue.")
    content = resp.choices[0].message.content
    # Some models ignore response_format (prose/fenced JSON): salvage the outermost {...}.
    for candidate in (content, content[content.find("{"): content.rfind("}") + 1]):
        try:
            return BatchVerdict.model_validate_json(candidate), resp, True
        except (ValidationError, ValueError):
            continue
    return None, resp, False


def run(env: dict, run_dir: Path, limit: int | None = None,
        dois: set[str] | None = None) -> None:
    hp = env["harness_params"]
    rubric = read_rubric(hp)
    ext_dir = RUNS_DIR / hp["extraction_run"]
    md_dir = data_path(hp.get("curated_data_markdown_dir", "curated_data_markdown_by_doi"))

    config = bundle.unpack_config(env)
    config["harness_params"]["rubric"] = rubric              # embed actual text, like prompts
    bundle.write_json(run_dir / "config.json",
                      {"content_hash": bundle.content_hash(config), **config})

    ext_files = sorted((ext_dir / "extractions").glob("*.json"))
    if dois is not None:
        ext_files = [f for f in ext_files if filename_to_doi(f.name) in dois]
    if limit:
        ext_files = ext_files[:limit]

    meta = {"model": env["llm_params"]["model"], "extraction_run": hp["extraction_run"],
            "git_commit": bundle.git_commit(), "started_at": bundle.now_iso(),
            "n_papers": len(ext_files), "n_records": 0, "parse_failed_records": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}

    for f in tqdm(ext_files, desc="judge"):
        if (run_dir / "verdicts" / f.name).exists():         # resume: never re-spend a call
            continue
        d = bundle.read_json(f)
        doi, records = d["doi"], d["records"]
        full_text = (md_dir / doi_to_filename(doi, "md")).read_text(encoding="utf-8")

        batch, resp, parsed_ok = run_llm(env["llm_params"],
                                         construct_messages(rubric, full_text, records))
        by_index = {v.extracted_index: v for v in batch.verdicts} if batch else {}
        if not parsed_ok:                                    # whole-paper failure: keep the raw text
            bundle.write_json(run_dir / "raw" / f.name,
                              {"doi": doi, "response_content": resp.choices[0].message.content})

        verdicts = []
        for i in range(len(records)):
            v = by_index.get(i)
            if v is None:
                meta["parse_failed_records"] += 1
            verdicts.append({"extracted_index": i, "parsed_ok": v is not None,
                             **(v.model_dump() if v else {})})
        meta["n_records"] += len(records)
        usage = resp.usage
        meta["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        meta["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
        meta["cost_usd"] += cost(resp)
        bundle.write_json(run_dir / "verdicts" / f.name, {"doi": doi, "verdicts": verdicts})

    meta["finished_at"] = bundle.now_iso()
    bundle.write_json(run_dir / "judge_meta.json", meta)
    print(f"judge bundle -> {run_dir}  ({meta['n_papers']} papers, {meta['n_records']} records, "
          f"{meta['parse_failed_records']} unparseable, ${meta['cost_usd']:.4f})")
    tracking.log_bundle(run_dir, stage="judge")
