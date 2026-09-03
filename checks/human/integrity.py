"""Three things a referee will ask that the paper never answered.

Each is cheap to compute and was sitting in the artefacts already. None flatters the work, which
is the reason to compute them rather than wait to be asked.

  contamination   Are the worked-example papers also benchmark papers? All seven are. A paper is
                  never its own exemplar -- construct_prompt drops the target from the pool -- so
                  no paper is scored against its own answers. But the other twenty-three are
                  scored while up to six of their neighbours sit in the prompt, and half the
                  benchmark also sits inside the mass corpus. Stated, this is a design; unstated,
                  it is a reject.

  annotators      What was the agreement between the two chemists? It cannot be computed. They
                  divided the worklist rather than double-annotating: of 27 records both touched,
                  20 were rescue-review prefills neither revised, six one revised, one the other,
                  and *zero* were decided independently by both. So the kappa of 0.30 for the
                  judge has no human reference point, and the paper has to say so rather than
                  quote an inter-annotator figure it does not have.

  constraints     Does the judge catch records that are impossible on their face? Yield cannot
                  exceed 100%, and yield cannot exceed conversion. Those records are wrong without
                  anyone labelling them, which makes them a free recall estimate on a population
                  where the ground truth is arithmetic rather than opinion.
"""
import glob
import json

import pandas as pd

from _setup import DATABASE, DATABASE_JUDGE, ARTIFACTS, curated, data_path, show, sources
from core.licensing import licensable_dois
from database.chemistry import IDENTITY_SLACK

DECISIONS = ARTIFACTS / "gold" / "decisions"
ANNOTATORS = ["adjudication_karim.json", "adjudication_mohammad.json"]


def contamination() -> dict:
    examples = licensable_dois()
    benchmark = set(curated().doi.str.lower())
    corpus = {path.stem.replace("@", "/").lower()
              for path in data_path("corpus_markdown").glob("*.md")}
    return {"worked-example pool": len(examples),
            "benchmark papers": len(benchmark),
            "examples that are also benchmark papers": len({d.lower() for d in examples} & benchmark),
            "benchmark papers inside the mass corpus": len(benchmark & corpus)}


def annotators() -> dict:
    seen = {}
    for name in ANNOTATORS:
        path = DECISIONS / name
        if not path.exists():
            continue
        seen[name] = {(row["doi"], row["extracted_index"]): row
                      for row in json.loads(path.read_text())["decisions"]}
    if len(seen) < 2:
        return {"overlap": 0, "both decided independently": 0}
    first, second = seen.values()
    shared = set(first) & set(second)
    independent = [key for key in shared
                   if not first[key].get("carried_over") and not second[key].get("carried_over")]
    agree = sum(1 for key in shared if first[key].get("human") == second[key].get("human"))
    return {"records adjudicated in total": len(set(first) | set(second)),
            "records both annotators touched": len(shared),
            "of those, a prefill neither revised": sum(
                1 for key in shared
                if first[key].get("carried_over") and second[key].get("carried_over")),
            "both decided independently": len(independent),
            "raw agreement where they overlap": agree / len(shared) if shared else float("nan")}


def constraints() -> pd.DataFrame:
    """Records that are wrong on arithmetic alone, and whether the judge said so."""
    verdicts = {}
    for path in glob.glob(str(DATABASE_JUDGE / "verdicts/*.json")):
        payload = json.loads(open(path, encoding="utf-8").read())
        for verdict in payload["verdicts"]:
            verdicts[(payload["doi"], verdict["extracted_index"])] = verdict

    rows = []
    for path in glob.glob(str(DATABASE / "extractions/*.json")):
        payload = json.loads(open(path, encoding="utf-8").read())
        for index, record in enumerate(payload["records"]):
            produced, converted = record.get("yield_percent"), record.get("conversion_percent")
            if produced is None:
                continue
            if produced > 100:
                kind = "yield above 100%"
            elif converted is not None and produced > converted + IDENTITY_SLACK:
                kind = "yield above conversion"
            else:
                continue
            verdict = verdicts.get((payload["doi"], index)) or {}
            rows.append({"violation": kind,
                         "flagged": verdict.get("verdict", "correct") != "correct"})

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    table = frame.groupby("violation").agg(records=("flagged", "size"),
                                           flagged=("flagged", "sum"))
    table["judge caught"] = (table.flagged / table.records).round(3)
    return table


def compute() -> dict:
    return {"contamination": contamination(), "annotators": annotators(),
            "constraints": constraints()}


def main() -> None:
    sources(extraction=DATABASE, judge=DATABASE_JUDGE, decisions=DECISIONS)
    result = compute()

    show("overlap between the worked examples, the benchmark and the corpus",
         result["contamination"], fmt="{:.0f}")
    print("\nA paper is never its own exemplar: construct_prompt drops the target from the pool.")
    print("The exposure is that a paper is scored while its neighbours sit in the prompt.")

    show("what the two chemists' answers can support", result["annotators"])
    print("\nNo inter-annotator agreement is computable: the worklist was divided, not")
    print("double-annotated, and no record was decided independently by both.")

    table = result["constraints"]
    show("records wrong on arithmetic alone, and whether the judge flagged them", table)
    if not table.empty:
        caught = table.flagged.sum() / table.records.sum()
        print(f"\nThe judge flags {caught:.0%} of records that violate a hard constraint. This needs")
        print("no human labelling: the ground truth is arithmetic.")


if __name__ == "__main__":
    main()
