import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import litellm
from tqdm import tqdm

from pydantic import ValidationError

from .schema import ExtractionResponse, ExtractionResponseNoSource
from .utils import filename_to_doi, doi_to_filename
from . import bundle
from .paths import prompt_path, data_path
from .licensing import licensable_dois

RATE_LIMIT_RETRIES = 14   # ~15 min of patience; the endpoint's concurrency cap can stay hot a while


def _cost(resp) -> float:
    try:
        return float(litellm.completion_cost(completion_response=resp) or 0.0)
    except Exception:
        return float((getattr(resp, "_hidden_params", {}) or {}).get("response_cost") or 0.0)

REQUEST_TIMEOUT = 600     # seconds; slower than this is stuck, not working


def run_llm(llm_params: dict, messages, response_model=ExtractionResponse, **kwargs):
    """Call the model and parse its JSON into records"""
    # The RWTH endpoint caps *concurrent* requests (429 too_many_concurrent_requests) rather than
    # total volume, so with several workers a burst is normal and transient. Back off and retry
    # instead of failing the whole run — this lets the pool self-throttle to whatever the endpoint
    # allows. Single-worker runs effectively never reach this path.
    for attempt in range(RATE_LIMIT_RETRIES):
        try:
            resp = litellm.completion(
                messages=messages,
                response_format=response_model,
                num_retries=5,
                # Without this a stalled connection hangs forever: an ablation sweep sat for
                # fifteen hours on one call, asleep on an open socket, and the study stopped
                # without ever failing.
                timeout=REQUEST_TIMEOUT,
                **llm_params, **kwargs,
            )
            break
        except litellm.AuthenticationError as e:
            raise RuntimeError(f"Authentication error: {e}. Check your API key.")
        except litellm.RateLimitError as e:
            if attempt == RATE_LIMIT_RETRIES - 1:
                raise RuntimeError(f"Rate limit error after {RATE_LIMIT_RETRIES} attempts: {e}. "
                                   f"Lower --workers.")
            time.sleep(min(2 ** attempt, 90) + random.uniform(0, 5))
        except litellm.APIError as e:
            raise RuntimeError(f"API error: {e}. LLM service issue.")

    content = resp.choices[0].message.content
    try:
        records = response_model.model_validate_json(content)
        return records.experiments, resp, True
    except ValidationError:
        pass
    # Fallback only: this endpoint sometimes wraps the JSON in a ```json ... ``` fence. Clean
    # responses never reach here, so previously-parsed runs are unaffected.
    stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content or "", flags=re.IGNORECASE)
    try:
        return response_model.model_validate_json(stripped).experiments, resp, True
    except ValidationError:
        return [], resp, False


def read_prompt(harness_params: dict) -> str:
    return prompt_path(harness_params.get("prompt_file", "prompt.txt")).read_text(encoding="utf-8")

def construct_prompt(harness_params: dict, target_doi: str) -> list[dict]:
    n_shots = harness_params["n_shots"]
    prompt = read_prompt(harness_params)
    rng = random.Random(harness_params["seed"])

    curated_json = data_path(harness_params.get("curated_data_path", "curated_data_json_by_doi.json"))
    data = json.loads(curated_json.read_text(encoding="utf-8"))
    target_paper = next((x for x in data if x["doi"] == target_doi), None)
    if target_paper is None:
        # A paper we have never curated — the mass-extraction case. Its text comes from the
        # markdown directory being extracted, which is the only place it exists.
        md_dir = data_path(harness_params.get("curated_data_markdown_dir",
                                              "curated_data_markdown_by_doi"))
        text = (md_dir / doi_to_filename(target_doi, "md")).read_text(encoding="utf-8")
        first_line = next((l for l in text.splitlines()
                           if l.strip() and not l.startswith("ID: ")), "")
        target_paper = {"doi": target_doi, "title": first_line.strip(), "full_text": text}
    # Few-shot exemplars must be redistributable: draw only from the licensable papers
    # (this is why n_shots caps at 6 — 7 licensable papers minus the held-out target).
    allowed = licensable_dois()
    example_papers = [x for x in data if x["doi"] != target_doi and x["doi"] in allowed]

    drop_src = harness_params.get("drop_source_chunks", False)

    def user_msg(paper):
        return {"role": "user",
                "content": f"Paper DOI: {paper['doi']}\nTitle: {paper['title']}\n"
                           f"Full Text:\n{paper['full_text']}\n\n{prompt}"}

    messages: list[dict] = []
    for paper in rng.sample(example_papers, min(n_shots, len(example_papers))):
        demo = [exp["experiment_data"] for exp in paper["extracted_experiments"]]
        if drop_src:   # OFF arm: demos must not teach provenance either
            demo = [{k: v for k, v in d.items() if k != "source_chunk_ids"} for d in demo]
        messages.append(user_msg(paper))
        messages.append({"role": "assistant",
                         "content": json.dumps({"experiments": demo}, indent=2)})
    messages.append(user_msg(target_paper))
    return messages

def run(env: dict, run_dir: Path, limit: int | None = None) -> None:
    md_dir = data_path(env["harness_params"].get("curated_data_markdown_dir", "curated_data_markdown_by_doi"))
    md_files = sorted(md_dir.glob("*.md")) 
    if limit:
        md_files = md_files[:limit]

    # Papers already extracted into this run are skipped, so enlarging the corpus costs only the
    # new papers. Set resume: false in harness_params to re-extract everything.
    if env["harness_params"].get("resume", True):
        already = {path.name for path in (run_dir / "extractions").glob("*.json")}
        pending = [md for md in md_files
                   if doi_to_filename(filename_to_doi(md.name), "json") not in already]
        if already:
            print(f"resuming: {len(already)} already extracted, {len(pending)} to do", flush=True)
        md_files = pending

    if not md_files:
        print("nothing to extract; every paper in the corpus already has a result")
        return

    response_model = (ExtractionResponseNoSource
                      if env["harness_params"].get("drop_source_chunks") else ExtractionResponse)
    config = bundle.unpack_config(env)
    config["harness_params"]["prompt"] = read_prompt(env["harness_params"])  # embed actual text
    bundle.write_json(run_dir / "config.json",
                      {"content_hash": bundle.content_hash(config), **config})

    # A resumed run must not forget what the earlier pass cost.
    before = {}
    if (run_dir / "run_meta.json").exists():
        before = json.loads((run_dir / "run_meta.json").read_text())
    meta = {
        "seed":              env["harness_params"]["seed"],
        "model":             env["llm_params"]["model"],
        "git_commit":        bundle.git_commit(),
        "started_at":        bundle.now_iso(),
        "n_papers":          before.get("n_papers", 0),   # += the papers that land, below
        "prompt_tokens":     before.get("prompt_tokens", 0),
        "completion_tokens": before.get("completion_tokens", 0),
        "cost_usd":          before.get("cost_usd", 0.0),
        "parse_failed_papers": before.get("parse_failed_papers", 0)
    }

    def extract_one(md):
        doi = filename_to_doi(md.name)
        messages = construct_prompt(env["harness_params"], doi)
        records, resp, parsed_ok = run_llm(env["llm_params"], messages, response_model=response_model)
        return md.name, doi, messages, records, resp, parsed_ok

    def save(result) -> None:
        """Write one paper the moment it lands.

        A three-hour run that keeps everything in memory and writes at the end loses all of it to
        one failure in the last minute -- which is exactly what happened to mass_luna_1shot at
        1026/1027. Writing per paper also makes `resume` mean what it says: an interrupted run
        keeps what it finished, so restarting bills only the remainder.
        """
        _, doi, messages, records, resp, _ = result
        fn = doi_to_filename(doi, filetype="json")
        bundle.write_json(run_dir / "extractions" / fn,
                          {"doi": doi, "records": [r.model_dump(by_alias=True) for r in records]})
        bundle.write_json(run_dir / "raw" / fn,
                          {"doi": doi, "messages": messages,
                           "response_content": resp.choices[0].message.content})

    # Papers are independent I/O-bound calls, so fan them out. max_workers defaults to 1, which
    # keeps the original sequential path byte-for-byte; the ablation configs raise it.
    #
    # A paper that raises -- a rate limit that outlasts its retries, a malformed response -- is
    # recorded and stepped over rather than allowed to abort the run, because the alternative is
    # throwing away every paper that already succeeded. The totals are still accumulated from the
    # sorted results, so they do not depend on finish order.
    workers = int(env["harness_params"].get("max_workers", 1) or 1)
    results, failures = [], []

    def collect(name, produce):
        try:
            result = produce()
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {str(exc)[:120]}"))
            return
        save(result)
        results.append(result)

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(extract_one, md): md for md in md_files}
            for future in tqdm(as_completed(futures), total=len(futures),
                               desc=f"extract x{workers}"):
                collect(futures[future].name, future.result)
    else:
        for md in tqdm(md_files, desc="extract"):
            collect(md.name, lambda md=md: extract_one(md))

    for _, doi, messages, records, resp, parsed_ok in sorted(results, key=lambda r: r[0]):
        if not parsed_ok:
            meta["parse_failed_papers"] += 1
        usage = resp.usage
        meta["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        meta["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
        meta["cost_usd"] += _cost(resp)

    meta["n_papers"] += len(results)
    meta["finished_at"] = bundle.now_iso()
    bundle.write_json(run_dir / "run_meta.json", meta)
    print(f"extraction bundle -> {run_dir}  (${meta['cost_usd']:.4f})")
    if failures:
        print(f"  {len(failures)} paper(s) failed and were skipped; rerun to retry just those:")
        for name, why in failures[:10]:
            print(f"    {name}: {why}")
    if meta["parse_failed_papers"]:
        print(f"  note: {meta['parse_failed_papers']}/{meta['n_papers']} papers returned "
              f"unparseable output (0 records); see raw/*.json 'response_content'.")
