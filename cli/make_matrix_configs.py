"""Write one extraction config and one judge config per model, for the model x model matrix.

Every combination shares the same prompt, rubric, seed, shot count and thresholds, so the model is
the only thing that varies between cells.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RWTH = {"api_key": "${openai_key}", "api_base": "https://chat.kiconnect.nrw/api/v1/"}
AZURE = {"api_key": "${azure_key}", "api_base": "https://karim-api-resource.openai.azure.com",
         "api_version": '"2024-12-01-preview"'}

# Every deployment on the Azure resource (listed via api-version=2022-12-01, the only version whose
# /openai/deployments still answers) plus the RWTH models worth using.
#
# gpt-5.5 is deliberately absent: the RWTH endpoint caps it at 20 messages an hour and 50 a day,
# which cannot carry a 24-paper run, let alone the mass extraction.
MODELS = {
    "sol":     {"model": "azure/gpt-5.6-sol",                "host": AZURE, "max_tokens": 16000, "unmetered": False},
    "luna":    {"model": "azure/gpt-5.6-luna",               "host": AZURE, "max_tokens": 16000, "unmetered": False},
    "terra":   {"model": "azure/gpt-5.6-terra",              "host": AZURE, "max_tokens": 16000, "unmetered": False},
    "mini":    {"model": "azure/gpt-5.4-mini",               "host": AZURE, "max_tokens": 16000, "unmetered": False},
    "mlarge":  {"model": "azure/Mistral-Large-3",            "host": AZURE, "max_tokens": 8192,  "unmetered": False},
    "oss":     {"model": "openai/gpt-oss-120b",              "host": RWTH,  "max_tokens": 8192,  "unmetered": True},
    "mistral": {"model": "openai/mistral-small-4-119b-2603", "host": RWTH,  "max_tokens": 8192,  "unmetered": True},
}

EXTRACT = """run_name: extract_{key}

# Matrix cell: extraction by {model}. Prompt, shots, seed and eval settings are identical across
# every model in the matrix, so the extractor is the only variable.
llm_params:
  model: {model}
{host}  max_tokens: {max_tokens}

harness_params:
  prompt_file: extraction_prompt.txt
  output_dir: extract_{key}
  curated_data_path: curated_data_json_by_doi.json
  curated_data_markdown_dir: curated_data_markdown_by_doi
  max_workers: {workers}
  n_shots: 4
  shot_selection: random
  seed: 123
  evaluation:
    curated_data_path: curated_table_final.json
    tp_threshold: 0.3
    catalyst_threshold: 0.6
    numeric_tolerance: 0.2
"""

JUDGE = """run_name: judge_{judge}_on_{target}

# Matrix cell: {jmodel} judging the {target} extraction, rubric v5 (critique, verdict, bad fields
# and the fixes it would apply).
llm_params:
  model: {jmodel}
{host}  max_tokens: {max_tokens}

harness_params:
  rubric_file: judge_rubric.txt
  extraction_run: extract_{target}/extract_{target}_n4_r1
  curated_data_markdown_dir: curated_data_markdown_by_doi
  output_dir: judge_{judge}_on_{target}
"""


def host_block(host):
    return "".join(f"  {k}: {v}\n" for k, v in host.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-unmetered", action="store_true",
                    help="skip the Azure models on both axes")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    chosen = {k: v for k, v in MODELS.items() if v["unmetered"] or not args.only_unmetered}
    ext_dir = ROOT / "configs" / "extract"
    judge_dir = ROOT / "configs" / "judge"
    written = []

    for key, spec in chosen.items():
        path = ext_dir / f"extract_{key}.yaml"
        path.write_text(EXTRACT.format(
            key=key, model=spec["model"], host=host_block(spec["host"]),
            max_tokens=spec["max_tokens"],
            workers=args.workers if spec["unmetered"] else 2))
        written.append(path)

    for judge, jspec in chosen.items():
        for target in chosen:
            path = judge_dir / f"judge_{judge}_on_{target}.yaml"
            path.write_text(JUDGE.format(
                judge=judge, target=target, jmodel=jspec["model"],
                host=host_block(jspec["host"]), max_tokens=jspec["max_tokens"]))
            written.append(path)

    print(f"models in the matrix : {', '.join(chosen)}")
    print(f"extraction configs   : {len(chosen)}")
    print(f"judge configs        : {len(chosen) ** 2}  ({len(chosen)} judges x {len(chosen)} extractions)")
    print(f"written              : {len(written)} files")


if __name__ == "__main__":
    main()
