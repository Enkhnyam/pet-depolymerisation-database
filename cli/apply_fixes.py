"""Apply a judge run's recommended fixes to the extraction it judged.

Produces the third of the three datasets the mass extraction needs to report: what the model
extracted, what the judge said about it, and what the extraction becomes once the judge's
corrections are applied. Writes a corrected bundle beside the original and a changelog naming
every field it touched.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import RUNS_DIR
from core import bundle
from core.schema import Experiment, canonical_field

NUMERIC = {f for f, info in Experiment.model_fields.items()
           if "float" in str(info.annotation)}


def coerce(field, value):
    """The rubric asks for numbers as numbers, but models sometimes send '190' or '190 C'."""
    if value is None or field not in NUMERIC:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = "".join(c for c in str(value) if c.isdigit() or c in ".-")
    try:
        return float(cleaned)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-run", required=True,
                    help="e.g. judge_sol_on_sol/judge_sol_on_sol")
    ap.add_argument("--out", help="output bundle name (default: <judge run>_corrected)")
    args = ap.parse_args()

    judge_dir = RUNS_DIR / args.judge_run
    config = bundle.read_json(judge_dir / "config.json")
    extraction_run = config["harness_params"]["extraction_run"]
    ext_dir = RUNS_DIR / extraction_run
    out_dir = RUNS_DIR / (args.out or f"{args.judge_run}_corrected")

    verdicts = {}
    for path in sorted((judge_dir / "verdicts").glob("*.json")):
        paper = bundle.read_json(path)
        verdicts[paper["doi"]] = {v["extracted_index"]: v for v in paper["verdicts"]}

    changelog = []
    kept = dropped = repaired = unparsed = 0

    for path in sorted((ext_dir / "extractions").glob("*.json")):
        paper = bundle.read_json(path)
        doi = paper["doi"]
        judged = verdicts.get(doi, {})
        records = []

        for index, record in enumerate(paper["records"]):
            verdict = judged.get(index)
            if not verdict or not verdict.get("parsed_ok"):
                unparsed += 1
                records.append(record)          # no opinion: leave the record alone
                kept += 1
                continue

            if verdict.get("drop_record"):
                dropped += 1
                changelog.append({"doi": doi, "extracted_index": index, "action": "dropped",
                                  "critique": verdict.get("critique", "")})
                continue

            corrected = dict(record)
            applied = []
            for fix in verdict.get("fixes") or []:
                # canonical_field, not a literal lookup: the judge spells PET_amount_g both ways,
                # and matching on the field name alone discarded the lowercase corrections
                field = canonical_field(fix.get("field"))
                if field is None:
                    continue                     # a fix naming something we do not store
                before = corrected.get(field)
                after = coerce(field, fix.get("value"))
                if before == after:
                    continue
                corrected[field] = after
                applied.append({"field": field, "from": before, "to": after,
                                "evidence": fix.get("evidence", "")})

            if applied:
                repaired += 1
                changelog.append({"doi": doi, "extracted_index": index, "action": "repaired",
                                  "changes": applied, "critique": verdict.get("critique", "")})
            records.append(corrected)
            kept += 1

        bundle.write_json(out_dir / "extractions" / path.name, {"doi": doi, "records": records})

    bundle.write_json(out_dir / "config.json", {
        "derived_from": {"extraction_run": extraction_run, "judge_run": args.judge_run},
        "note": "Extraction with the judge's recommended fixes applied. Not a human-curated set."})
    bundle.write_json(out_dir / "changelog.json", changelog)

    print(f"extraction  {extraction_run}")
    print(f"judge       {args.judge_run}")
    print(f"\nrecords kept     {kept}")
    print(f"  of those repaired {repaired}")
    print(f"records dropped  {dropped}")
    if unparsed:
        print(f"records the judge could not be read for, left untouched: {unparsed}")
    fields = {}
    for entry in changelog:
        for change in entry.get("changes", []):
            fields[change["field"]] = fields.get(change["field"], 0) + 1
    if fields:
        print("\nfields corrected:")
        for field, count in sorted(fields.items(), key=lambda kv: -kv[1]):
            print(f"  {field:22s} {count}")
    print(f"\nwrote {out_dir}")


if __name__ == "__main__":
    main()
