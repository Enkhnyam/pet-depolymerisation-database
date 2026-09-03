"""Add the records the chemists confirmed into the curated answer key.

The rescue review asks one question about each record the metric rejected for having no
counterpart: is this a real experiment the table missed? Records answered "real" belong in the
table; "notreal" and "unsure" do not, and are kept in the decision file as evidence rather than
discarded.

Two safeguards, both learned the hard way:

Records are verified by content before being added. The decisions reference records by position
within an extraction run, and a position is not an identity -- a previous round of this project
silently attached a chemist's verdict to a different experiment that way. Any decision whose
catalyst and temperature no longer match the record at that index is refused, not merged.

A rescue that already exists in the table is refused. One of the fifty-eight confirmed records
was an exact duplicate of a curated row on every field that identifies an experiment; adding it
would have double-counted a single measurement in the answer key everything else is scored
against.

The `product` field is dropped. It left the schema because the route determines it, and adding it
back through this door would give the answer key a column nothing else has.

Solvent names are written out in full. A rescue is a record copied from the extraction, and the
extraction writes whatever the paper's table said -- "EG" as often as "ethylene glycol". Six of
those went in verbatim and then scored as a different solvent from every hand-curated row.

    merge_rescues.py --decisions artifacts/gold/decisions/rescue_decisions_full.json --dry-run
    merge_rescues.py --decisions ... --apply
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from core.paths import data_path
from core.schema import canonical_solvent
from core.utils import doi_to_filename

SOURCE_RUN = "extract_luna/extract_luna_n4_r1"
CURATED = "curated_table_final.json"
DROP_FIELDS = {"product"}


def records_of(run: Path, doi: str) -> list | None:
    """A paper's extracted records, tolerating the case of the doi in the filename."""
    for candidate in (doi, doi.lower()):
        path = run / "extractions" / doi_to_filename(candidate, "json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["records"]
    return None


def identity(record: dict) -> tuple:
    """The fields that decide whether two rows describe the same experiment."""
    def number(value):
        return round(float(value), 3) if isinstance(value, (int, float)) else value
    return tuple(number(record.get(field)) for field in
                 ("catalyst", "temperature_c", "reaction_time_min", "yield_percent",
                  "conversion_percent", "catalyst_amount_g"))


def same_record(record: dict, decision: dict) -> bool:
    """Whether the record at that index is still the one the chemist judged."""
    if str(record.get("catalyst")) != str(decision["catalyst"]):
        return False
    for field in ("temperature_c", "reaction_time_min"):
        left, right = record.get(field), decision.get(field)
        if (left is None) != (right is None):
            return False
        if left is not None and float(left) != float(right):
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="merge_rescues")
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--run", default=SOURCE_RUN, help="extraction the decisions refer to")
    parser.add_argument("--apply", action="store_true", help="write; otherwise report only")
    args = parser.parse_args()

    payload = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    decisions = payload["decisions"]
    run = ROOT / "artifacts" / "runs" / args.run

    accepted, refused, skipped = [], [], []
    for decision in decisions:
        if decision["answer"] != "real":
            skipped.append(decision)
            continue
        records = records_of(run, decision["doi"])
        if records is None or decision["index"] >= len(records):
            refused.append((decision["key"], "no record at that index"))
            continue
        record = records[decision["index"]]
        if not same_record(record, decision):
            refused.append((decision["key"], "record at that index is a different experiment"))
            continue
        row = {k: v for k, v in record.items() if k not in DROP_FIELDS}
        # the answer key writes solvents out in full; a rescue copied verbatim once put six "EG"
        # rows into it, which then scored as a different solvent from the other 289
        row["solvent"] = canonical_solvent(row.get("solvent")) or row.get("solvent")
        accepted.append((decision, row))

    print(f"decisions            {len(decisions)}")
    print(f"  answered real      {len(accepted) + len(refused)}")
    print(f"    verified         {len(accepted)}")
    print(f"    refused          {len(refused)}")
    print(f"  not added          {len(skipped)}  (notreal or unsure, kept as evidence)")
    for key, why in refused:
        print(f"    REFUSED {key}: {why}")

    table = json.loads(data_path(CURATED).read_text(encoding="utf-8"))
    by_doi = {paper["doi"]: paper for paper in table}
    before = sum(len(p["extracted_experiments"]) for p in table)

    added = 0
    duplicates = []
    for decision, record in accepted:
        paper = by_doi.get(decision["doi"])
        if paper is None:
            refused.append((decision["key"], "paper not in the curated table"))
            continue
        existing = {identity(entry["experiment_data"]) for entry in paper["extracted_experiments"]}
        if identity(record) in existing:
            duplicates.append(decision["key"])
            continue
        paper["extracted_experiments"].append({
            "experiment_data": record,
            "provenance": {"added_by": "rescue review",
                           "decided": payload.get("generated", "")[:10],
                           "from_run": args.run, "source_index": decision["index"]},
        })
        added += 1

    after = sum(len(p["extracted_experiments"]) for p in table)
    print(f"\ncurated experiments  {before} -> {after}  (+{added})")
    if duplicates:
        print(f"  {len(duplicates)} confirmed record(s) already present, not added again:")
        for key in duplicates:
            print(f"    {key}")

    notes = payload.get("notes") or {}
    if notes:
        print(f"\n{len(notes)} paper-level note(s) from the chemists, NOT applied automatically:")
        for doi, note in notes.items():
            print(f"  {doi}\n    {' '.join(note.split())[:300]}")
        print("  These describe corrections to specific values. Applying them by pattern-matching"
              "\n  prose would be guesswork, so they are left for a deliberate edit.")

    if not args.apply:
        print("\nnothing written; pass --apply to write")
        return

    target = data_path(CURATED)
    backup = target.with_name(f"{target.stem}.before-rescues-{date.today()}.json")
    shutil.copy2(target, backup)
    target.write_text(json.dumps(table, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {target}\nprevious version kept at {backup.name}")


if __name__ == "__main__":
    main()
