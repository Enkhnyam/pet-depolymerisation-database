"""Every extracted record, with its paper, its verdict and the judge's suggestions, in one CSV.

cli/release.py ships the database as three files on purpose -- what was extracted, what it becomes
corrected, and a changelog between them -- because that separation is what lets a reader see the
corrections rather than only their result. This is the other thing people want: one row per
record, wide enough to filter and pivot in a spreadsheet without joining anything.

Each row carries the record as extracted, the same record with the judge's corrections applied,
and the judge's own words. Both versions are present rather than only the corrected one, because
the corrections are a second model's opinion and a row that hid the original would be asserting
they are right.

The judge's suggestions appear twice, at two levels of detail: judge_fixes as JSON, which loses
nothing, and corrected_* columns, which are what a spreadsheet can actually sort on.

    export_flat.py                                  the current database run
    export_flat.py --extraction mass_luna --judge mass_oss/mass_oss --out old.csv
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))

from core.paths import ARTIFACTS, RUNS_DIR, data_path
from core.schema import canonical_field
from core.utils import doi_to_filename
from database.chemistry import CATALYST_CLASSES, ROUTE_FROM_SOLVENT, classify

FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

COLUMNS = (["record_id", "doi", "title", "journal", "record_index",
            "source_format", "route", "catalyst_class"]
           + FIELDS
           + ["source_chunk_ids", "n_citations", "citations_resolve",
              "judge_verdict", "judge_parsed_ok", "judge_drop_record",
              "judge_n_fixes", "judge_bad_fields", "judge_critique", "judge_fixes"]
           + [f"corrected_{field}" for field in FIELDS]
           + ["corrected_fields", "record_survives"])

CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)
NUMERIC = {"temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
           "solvent_amount_g", "yield_percent", "selectivity_percent", "conversion_percent",
           "pressure_atm"}


def coerce(field: str, value):
    """The rubric asks for numbers as numbers; models sometimes send '190' or '190 C'."""
    if value is None or field not in NUMERIC:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = "".join(c for c in str(value) if c.isdigit() or c in ".-")
    try:
        return float(cleaned)
    except ValueError:
        return None


def paper_metadata() -> dict:
    """doi -> title and journal, from the candidate list the corpus was drawn from."""
    found = {}
    with data_path("corpus_candidates.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            found[row["doi"].lower()] = {"title": row.get("title", ""),
                                         "journal": row.get("journal", "")}
    return found


def source_formats() -> dict:
    path = data_path("source_format.csv")
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return {row["doi"].lower(): row["format"] for row in csv.DictReader(handle)}


def known_chunks(markdown_dir: Path, doi: str) -> set:
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    return set(CHUNK_PATTERN.findall(path.read_text(encoding="utf-8"))) if path.exists() else set()


def rows_for(extraction: Path, judge: Path, markdown_dir: Path) -> list:
    meta, formats = paper_metadata(), source_formats()

    verdicts_by_doi = {}
    for path in (judge / "verdicts").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        verdicts_by_doi[payload["doi"]] = {v["extracted_index"]: v for v in payload["verdicts"]}

    rows = []
    for path in sorted((extraction / "extractions").glob("*.json")):
        paper = json.loads(path.read_text(encoding="utf-8"))
        doi = paper["doi"]
        about = meta.get(doi.lower(), {})
        chunks = known_chunks(markdown_dir, doi)
        verdicts = verdicts_by_doi.get(doi, {})

        for index, record in enumerate(paper["records"]):
            cited = record.get("source_chunk_ids") or []
            verdict = verdicts.get(index, {})
            fixes = verdict.get("fixes") or []

            row = {
                "record_id": f"{doi}#{index}",
                "doi": doi,
                "title": about.get("title", ""),
                "journal": about.get("journal", ""),
                "record_index": index,
                "source_format": formats.get(doi.lower(), ""),
                "route": classify(record.get("solvent"), ROUTE_FROM_SOLVENT, "other/unclear"),
                "catalyst_class": classify(record.get("catalyst"), CATALYST_CLASSES, "other"),
                **{field: record.get(field) for field in FIELDS},
                "source_chunk_ids": ";".join(cited),
                "n_citations": len(cited),
                # a citation that resolves to nothing is marked, not dropped
                "citations_resolve": bool(cited) and all(c in chunks for c in cited),
                "judge_verdict": verdict.get("verdict", ""),
                "judge_parsed_ok": verdict.get("parsed_ok", ""),
                "judge_drop_record": bool(verdict.get("drop_record")),
                "judge_n_fixes": len(fixes),
                "judge_bad_fields": ";".join(verdict.get("bad_fields") or []),
                "judge_critique": (verdict.get("critique") or "").replace("\n", " ").strip(),
                "judge_fixes": json.dumps(fixes, ensure_ascii=False) if fixes else "",
            }

            corrected = {field: record.get(field) for field in FIELDS}
            changed = []
            for fix in fixes:
                field = canonical_field(fix.get("field"))
                if field is None or field not in FIELDS:
                    continue
                after = coerce(field, fix.get("value"))
                if corrected[field] != after:
                    corrected[field] = after
                    changed.append(field)
            row.update({f"corrected_{field}": corrected[field] for field in FIELDS})
            row["corrected_fields"] = ";".join(changed)
            # what the corrected database would keep: the judge's outright rejections leave
            row["record_survives"] = not bool(verdict.get("drop_record"))
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(prog="export_flat")
    parser.add_argument("--extraction", default="mass_luna_1shot")
    parser.add_argument("--judge", default="mass_oss_1shot/mass_oss_1shot")
    parser.add_argument("--corpus", default="corpus_markdown")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows = rows_for(RUNS_DIR / args.extraction, RUNS_DIR / args.judge, data_path(args.corpus))
    out = Path(args.out) if args.out else ARTIFACTS / "release" / f"{args.extraction}_flat.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    papers = len({row["doi"] for row in rows})
    dropped = sum(1 for row in rows if row["judge_drop_record"])
    proposed = sum(1 for row in rows if row["judge_n_fixes"])
    changed = sum(1 for row in rows if row["corrected_fields"])
    unresolved = sum(1 for row in rows if row["n_citations"] and not row["citations_resolve"])
    print(f"rows (records)             {len(rows)}")
    print(f"papers with records        {papers}")
    print(f"columns                    {len(COLUMNS)}")
    print(f"records the judge fixed    {proposed}  (judge_n_fixes > 0)")
    print(f"  of those, value changed  {changed}  (corrected_fields non-empty)")
    print(f"records the judge dropped  {dropped}")
    print(f"citations that resolve     {len(rows) - unresolved}/{len(rows)}")
    print("\nA fix that proposes the value already there is counted in the first line and not")
    print("the second, which is why this disagrees with the changelog cli/release.py writes:")
    print("that logs every fix proposed, this logs the ones that move a number.")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
