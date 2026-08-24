"""Assemble the released database from an extraction and the judge run over it.

Three files, because the honest thing is to ship all three rather than only the tidied one:

    records.csv / .json          what the model extracted, unaltered
    records_corrected.csv/.json  the same with the judge's corrections applied and its
                                 outright rejections removed
    changelog.json               every field the judge changed, its value before and after,
                                 and the evidence it cited

Every record carries the DOI it came from and the identifiers of the chunks it was read from, so
any number can be traced to a sentence. Citations that resolve to nothing are marked rather than
dropped: 6% of them do not resolve, and hiding that would misrepresent the data.

    release.py --extraction mass_luna --judge mass_oss/mass_oss
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.paths import ARTIFACTS, RUNS_DIR, data_path
from core.schema import canonical_field
from core.utils import doi_to_filename

FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

COLUMNS = ["record_id", "doi", *FIELDS, "source_chunk_ids", "citations_resolve"]
CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)


def chunk_ids(markdown_dir: Path, doi: str) -> set:
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    return set(CHUNK_PATTERN.findall(path.read_text(encoding="utf-8"))) if path.exists() else set()


def collect(extraction: Path, judge: Path, markdown_dir: Path) -> tuple[list, list, list]:
    """The extracted records, the corrected records, and the changelog between them."""
    verdicts_by_doi = {}
    for path in (judge / "verdicts").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        verdicts_by_doi[payload["doi"]] = {v["extracted_index"]: v for v in payload["verdicts"]}

    raw, corrected, changelog = [], [], []
    for path in sorted((extraction / "extractions").glob("*.json")):
        paper = json.loads(path.read_text(encoding="utf-8"))
        doi = paper["doi"]
        known = chunk_ids(markdown_dir, doi)
        verdicts = verdicts_by_doi.get(doi, {})

        for index, record in enumerate(paper["records"]):
            cited = record.get("source_chunk_ids") or []
            row = {"record_id": f"{doi}#{index}", "doi": doi,
                   **{field: record.get(field) for field in FIELDS},
                   "source_chunk_ids": ";".join(cited),
                   "citations_resolve": bool(cited) and all(c in known for c in cited)}
            raw.append(row)

            verdict = verdicts.get(index, {})
            if verdict.get("drop_record"):
                changelog.append({"record_id": row["record_id"], "action": "dropped",
                                  "reason": verdict.get("critique", "")})
                continue

            fixed = dict(row)
            for fix in verdict.get("fixes") or []:
                # through canonical_field, because the judge names PET_amount_g both ways and a
                # literal lookup dropped every correction that used the lowercase spelling
                field = canonical_field(fix.get("field"))
                if field is None or field not in FIELDS:
                    continue
                changelog.append({"record_id": row["record_id"], "action": "corrected",
                                  "field": field, "from": row[field], "to": fix["value"],
                                  "evidence": fix.get("evidence", "")})
                fixed[field] = fix["value"]
            corrected.append(fixed)

    return raw, corrected, changelog


def write(rows: list, stem: Path) -> None:
    stem.with_suffix(".json").write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


README = """# PET depolymerisation database

Reaction conditions and outcomes for PET depolymerisation, extracted automatically from the
published literature and checked by a second model. {papers} papers, {records} records.

## Files

| file | what it is |
|---|---|
| `records.csv` / `.json` | what the extraction model produced, unaltered |
| `records_corrected.csv` / `.json` | the same, with the judge's corrections applied and the {dropped} records it rejected outright removed |
| `changelog.json` | every change between the two, with the evidence cited for it |

Both versions are shipped because neither is the truth. The raw version is what a model produced;
the corrected version is what a second model thought it should have produced. Neither has been
checked by a chemist at scale.

## Columns

`record_id` is `doi#index`, the index being the record's position within its paper.
`source_chunk_ids` lists the identifiers of the text chunks the record was read from, separated by
semicolons. `citations_resolve` is false where a cited chunk is not present in the paper it claims
to come from -- about 6% of records, which may still be correct but cannot be traced
automatically.

Masses are grams, temperature degrees Celsius, time minutes, pressure atmospheres, and yield,
selectivity and conversion are percentages. A blank means the paper did not report it, not zero.

## How far this can be trusted

{pass_rate} of records were accepted by the judge without change. On a curated set of 24 papers a
judge and a metric grader that compares against hand-curated values agree on roughly nine of every
ten records the metric can evaluate, which is what licenses reading the judge's verdicts as a
quality estimate here. Two chemists adjudicated 48 records; that set is too small to say which
grader is better, and we say so rather than claiming it.

Everything needed to reproduce this is in the repository: the corpus, the prompts, the configs,
and the checks that derive every number quoted above.
"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="release")
    parser.add_argument("--extraction", required=True)
    parser.add_argument("--judge", required=True)
    parser.add_argument("--corpus", default="corpus_markdown")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    extraction = RUNS_DIR / args.extraction
    judge = RUNS_DIR / args.judge
    out = Path(args.out) if args.out else ARTIFACTS / "release"
    out.mkdir(parents=True, exist_ok=True)

    raw, corrected, changelog = collect(extraction, judge, data_path(args.corpus))
    write(raw, out / "records")
    write(corrected, out / "records_corrected")
    (out / "changelog.json").write_text(json.dumps(changelog, indent=2, ensure_ascii=False),
                                        encoding="utf-8")

    dropped = sum(1 for entry in changelog if entry["action"] == "dropped")
    accepted = len(raw) - len({e["record_id"] for e in changelog})
    (out / "README.md").write_text(README.format(
        papers=len({row["doi"] for row in raw}), records=len(raw), dropped=dropped,
        pass_rate=f"{accepted / len(raw):.1%}"), encoding="utf-8")

    unresolved = sum(1 for row in raw if not row["citations_resolve"])
    print(f"records                {len(raw)}")
    print(f"  corrected            {sum(1 for e in changelog if e['action'] == 'corrected')}")
    print(f"  dropped              {dropped}")
    print(f"  citations unresolved {unresolved}")
    print(f"corrected database     {len(corrected)} records")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
