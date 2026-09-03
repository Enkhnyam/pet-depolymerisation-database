"""Split the release into the three files a reader actually wants.

artifacts/release/features.csv holds 155 columns: every extracted field, the same field again
after the judge's corrections, the judge's own reasoning, four classifier internals, and 96 RDKit
descriptors. That is the right shape for reproducing the study and the wrong shape for using the
data. Nobody opening a spreadsheet wants to discover that `catalyst` and `corrected_catalyst` are
different columns.

So it becomes three files with one join key:

    pet_depolymerisation.csv              one row per experiment, the columns a chemist reads
    pet_depolymerisation_audit.csv        what the judge said, and every value it proposed changing
    pet_depolymerisation_descriptors.csv  the RDKit descriptors, for modelling

The data table carries the values as extracted, never the corrected ones. A corrected value is a
second model's opinion, and silently substituting it would make the released numbers unattributable
to any single source. `audit` says whether the judge accepted the row, and the audit file holds
what it would have changed, so a user can apply the corrections, ignore them, or judge each.

    build_simple_release.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.paths import ARTIFACTS

SOURCE = ARTIFACTS / "release" / "features.csv"
OUT = ARTIFACTS / "release"

# One row per experiment. Ordered as a chemist reads it: what was run, how, what came out.
DATA = [
    ("record_id",           "record_id",            "unique id; join key for the other two files"),
    ("doi",                 "doi",                  "source article"),
    ("title",               "title",                "article title"),
    ("journal",             "journal",              "journal"),
    ("route",               "route",                "glycolysis, methanolysis or hydrolysis, inferred from the solvent"),
    ("catalyst",            "catalyst",             "catalyst as named in the paper"),
    ("catalyst_smiles",     "catalyst_smiles",      "SMILES, where the name could be resolved"),
    ("catalyst_class",      "catalyst_class",       "broad family, e.g. metal salt, ionic liquid, organocatalyst"),
    ("solvent",             "solvent",              "depolymerising reagent or solvent"),
    ("product",             "product",              "monomer, fixed by the route"),
    ("temperature_c",       "temperature_c",        "reaction temperature, degrees Celsius"),
    ("reaction_time_min",   "reaction_time_min",    "reaction time, minutes"),
    ("pressure_atm",        "pressure_atm",         "pressure, atmospheres; blank means not stated"),
    ("catalyst_g",          "catalyst_amount_g",    "catalyst charge, grams"),
    ("pet_g",               "PET_amount_g",         "PET charge, grams"),
    ("solvent_g",           "solvent_amount_g",     "solvent charge, grams"),
    ("catalyst_loading_wt", "catalyst_loading_wt",  "catalyst as a mass fraction of PET, where both are given"),
    ("yield_percent",       "yield_percent",        "monomer yield"),
    ("yield_basis",         "yield_basis",          "molar or mass, where the paper says"),
    ("conversion_percent",  "conversion_percent",   "PET conversion"),
    ("selectivity_percent", "selectivity_percent",  "selectivity to the monomer"),
    ("audit",               "audit",                "accepted or flagged by the independent LLM judge"),
    ("corrections",         "judge_n_fixes",        "number of fields the judge proposed changing"),
    ("drop_recommended",    "judge_drop_record",    "true if the judge thought the record should not exist at all"),
    ("traceable",           "citations_resolve",    "true if the cited source text was found in this article"),
    ("duplicate_of",        "duplicate_of",         "record_id of an earlier identical experiment, if any"),
    ("quality_flags",       "quality_flags",        "automatic warnings, e.g. more catalyst than PET"),
]

AUDIT = [("record_id", "record_id"), ("doi", "doi"), ("verdict", "judge_verdict"),
         ("drop_recommended", "judge_drop_record"), ("fields_disputed", "judge_bad_fields"),
         ("proposed_values", "judge_fixes"), ("reasoning", "judge_critique"),
         ("source_chunk_ids", "source_chunk_ids"), ("n_citations", "n_citations"),
         ("catalyst_structure_source", "structure_source"), ("phase", "phase"),
         ("phase_reason", "phase_why")]


def main() -> None:
    src = pd.read_csv(SOURCE, low_memory=False)
    print(f"{SOURCE.name}: {src.shape[0]:,} rows x {src.shape[1]} columns\n")

    data = pd.DataFrame({new: src[old] for new, old, _ in DATA})
    data.to_csv(OUT / "pet_depolymerisation.csv", index=False)

    audit = pd.DataFrame({new: src[old] for new, old in AUDIT if old in src})
    audit.to_csv(OUT / "pet_depolymerisation_audit.csv", index=False)

    desc_cols = [c for c in src.columns if c.startswith(("cat_", "sol_"))]
    desc = pd.concat([src[["record_id"]], src[desc_cols]], axis=1)
    desc.to_csv(OUT / "pet_depolymerisation_descriptors.csv", index=False)

    for name, frame in (("pet_depolymerisation.csv", data),
                        ("pet_depolymerisation_audit.csv", audit),
                        ("pet_depolymerisation_descriptors.csv", desc)):
        print(f"  {name:38s} {frame.shape[0]:,} rows x {frame.shape[1]:>3} columns")

    lines = ["# PET depolymerisation database", "",
             f"{len(data):,} experiments from {data.doi.nunique():,} articles, extracted from the "
             "primary literature and audited against it.", "",
             "## Files", "",
             "| file | rows | columns | what it is |", "|---|---|---|---|",
             f"| `pet_depolymerisation.csv` | {len(data):,} | {data.shape[1]} | one row per experiment "
             "— start here |",
             f"| `pet_depolymerisation_audit.csv` | {len(audit):,} | {audit.shape[1]} | what the judge "
             "said about each record and what it would change |",
             f"| `pet_depolymerisation_descriptors.csv` | {len(desc):,} | {desc.shape[1]} | RDKit "
             "descriptors of the catalyst and solvent, for modelling |", "",
             "Join on `record_id`.", "",
             "## Values are as extracted, not as corrected", "",
             "The data table holds what the extraction model read from the paper. An independent LLM "
             "judge then re-read every paper and flagged records it thought unsupported; `audit` "
             "records its verdict and `corrections` how many fields it disputed. The values it "
             "proposed instead are in the audit file, not substituted into the data. Applying them "
             "is a decision for the user, not one we made silently.", "",
             "## Columns", "", "| column | meaning |", "|---|---|"]
    lines += [f"| `{new}` | {why} |" for new, _, why in DATA]
    lines += ["", "## Blank cells", "",
              "A blank means the paper did not report the quantity, not zero and not a failed "
              "extraction. Reporting rates vary widely: temperature is present in 86% of records, "
              "yield in 48%, selectivity in 3%. This bounds what any dataset built from these "
              "articles could contain.", "",
              "## Known limits", "",
              f"- {int(src.quality_flags.notna().sum()):,} records carry an automatic quality warning "
              "(`quality_flags`).",
              f"- {int(src.duplicate_of.notna().sum()):,} records repeat an earlier experiment in the "
              "same article; `duplicate_of` names it.",
              f"- {int((~src.citations_resolve.astype(bool)).sum()):,} records cite source text that "
              "could not be located in their own article; `traceable` is false for these.",
              "- Catalyst structures marked `LLM written` in the audit file were generated by a "
              "language model and not independently verified."]
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  {'README.md':38s} data dictionary for all {data.shape[1]} columns")

    # An xlsx as well: this is opened in Excel far more often than in pandas, and a workbook with
    # the dictionary on its own sheet answers most questions without anyone reading a README.
    book = OUT / "pet_depolymerisation.xlsx"
    with pd.ExcelWriter(book, engine="xlsxwriter") as writer:
        data.to_excel(writer, sheet_name="Data", index=False)
        pd.DataFrame(
            [{"column": new, "meaning": why,
              "populated": f"{data[new].notna().mean()*100:.0f}%"} for new, _, why in DATA]
        ).to_excel(writer, sheet_name="Columns", index=False)
        audit.to_excel(writer, sheet_name="Audit", index=False)
        wb = writer.book
        head = wb.add_format({"bold": True, "bg_color": "#1F3B4D", "font_color": "white",
                              "border": 1, "border_color": "#1F3B4D"})
        for sheet, frame, widths in (("Data", data, {"doi": 30, "title": 46, "catalyst": 26,
                                                     "catalyst_smiles": 34, "solvent": 22,
                                                     "record_id": 34, "journal": 28,
                                                     "duplicate_of": 30, "quality_flags": 26}),
                                     ("Columns", None, {"column": 24, "meaning": 74, "populated": 11}),
                                     ("Audit", audit, {"record_id": 34, "doi": 30, "reasoning": 60,
                                                       "proposed_values": 46, "source_chunk_ids": 40})):
            ws = writer.sheets[sheet]
            cols = list(frame.columns) if frame is not None else ["column", "meaning", "populated"]
            for i, c in enumerate(cols):
                ws.write(0, i, c, head)
                ws.set_column(i, i, widths.get(c, 15))
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, (len(frame) if frame is not None else len(DATA)), len(cols) - 1)
    print(f"  {'pet_depolymerisation.xlsx':38s} Data / Columns / Audit sheets, filterable")


if __name__ == "__main__":
    main()
