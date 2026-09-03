"""Assemble the homogeneous PET depolymerisation dataset for release.

One workbook. Every experiment whose catalyst dissolves in the reaction liquid, plus the
uncatalysed runs that are the baseline for them, with the structures resolved, the audit
verdict carried through, and the things that are wrong with it written down rather than
quietly filtered out.

What decides inclusion is core.solubility, which classifies each catalyst name and records
which rule decided it and why. Solids, enzymes, and names that resolve to nothing are removed
to the `Excluded` sheet with the reason attached, so the filter can be argued with instead of
taken on trust.

Nothing is silently deleted. A record that fails a range check, or duplicates another, or
names two catalysts in one cell, stays in the data with a flag saying so. Deciding what to do
about it is the reader's call, not ours -- and the flags are what let a modelling user filter
in one line.

Sheets, in the order someone reads them:

  Read me      what this is, how big it is, and what it does not support
  Data         one row per experiment
  Catalysts    every catalyst, its structure, its phase call and the reason for it
  Excluded     what was removed and why
  Charts       the shape of the collection
  Schema       what each column means

    build_release.py                 artifacts/release/pet_homogeneous_release.xlsx
    build_release.py --no-baselines  leave the uncatalysed runs out
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.paths import ARTIFACTS
from core.solubility import classify

SOURCE = ARTIFACTS / "huggingface" / "full" / "records-00000-of-00001.parquet"
BASIS = ARTIFACTS / "data" / "yield_basis.csv"
OUT = ARTIFACTS / "release" / "pet_homogeneous_release.xlsx"
# Bump on any change to the filter or the columns. Frozen for the release.
VERSION = "1.0"

HEADER, RULE = "1F3B4D", "C9D6D3"
PALETTE = ["3E6E8E", "B0523E", "86689F", "8D8677", "6C9E9C", "B08A3E", "57896B",
           "6A8CA8", "C4785F", "A98CC4", "A29A88", "8AC2C0"]

COLUMNS = [
    "record_id", "doi", "title", "journal",
    "catalyst", "catalyst_smiles", "structure_source", "catalyst_class", "phase",
    "route", "product", "solvent", "solvent_smiles",
    "temperature_c", "reaction_time_min", "pressure_atm",
    "catalyst_amount_g", "PET_amount_g", "solvent_amount_g", "catalyst_loading_wt",
    "yield_percent", "yield_basis", "conversion_percent", "selectivity_percent",
    "audit", "single_component", "duplicate_of", "quality_flags",
    "n_citations", "citations_resolve", "source_chunk_ids",
]
WIDTH = {"record_id": 30, "doi": 27, "title": 40, "journal": 22, "catalyst": 28,
         "catalyst_smiles": 34, "solvent_smiles": 22, "structure_source": 14,
         "catalyst_class": 16, "phase": 13, "route": 13, "product": 9, "solvent": 20,
         "yield_basis": 12, "audit": 10, "quality_flags": 26, "duplicate_of": 30,
         "source_chunk_ids": 26, "why": 52, "catalyst_loading_wt": 17}

EXPERIMENT = ["doi", "catalyst", "solvent", "temperature_c", "reaction_time_min",
              "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
              "yield_percent", "conversion_percent"]

SCHEMA = [
    ("What this is", "Experiments in which PET is broken down by a catalyst that dissolves in "
                     "the reaction liquid, extracted automatically from the published "
                     "literature and audited by a second model. Uncatalysed runs are included "
                     "as baselines and marked phase = uncatalysed."),
    ("phase", "Whether the catalyst dissolves. Decided by core/solubility.py, which records "
              "the rule that made each call; see the Catalysts sheet for the reason. Solids, "
              "enzymes and unresolvable names are on the Excluded sheet."),
    ("catalyst", "As the source paper writes it, not normalised. Use catalyst_smiles to group."),
    ("catalyst_smiles", "Canonical SMILES, parseable by RDKit. structure_source says where it "
                        "came from: 'confirmed' means OPSIN derived it independently from the "
                        "name; 'LLM written' means a language model supplied it and nothing "
                        "independent has checked it."),
    ("route / product", "Inferred from the solvent, not stated by the paper. Glycolysis gives "
                        "BHET, methanolysis DMT, hydrolysis TPA. Rows whose solvent matches "
                        "none of the three carry no route and no product."),
    ("yield_basis", "How the source paper defines the word yield, read from its methods "
                    "section for 51 papers. Papers use at least five incompatible "
                    "definitions and a mass-basis paper reports roughly a third less than a "
                    "molar-basis paper for the same chemistry. Blank means unread, not molar."),
    ("catalyst_loading_wt", "catalyst_amount_g / PET_amount_g. Derived, not extracted."),
    ("audit", "An independent model's verdict on the record as extracted. 'flagged' means it "
              "thought something was unsupported, not that it is certainly wrong. It separates "
              "range violations well and almost nothing else; do not filter on it blindly."),
    ("single_component", "FALSE where the catalyst cell names more than one substance. The "
                         "schema has one amount column, so those rows cannot express the "
                         "component ratio. Filter to TRUE for structure-keyed modelling."),
    ("duplicate_of", "The record_id of the first row reporting the identical experiment. "
                     "Blank for the first occurrence. Kept rather than dropped so counts are "
                     "reproducible; de-duplicate on this column."),
    ("quality_flags", "Range and identity violations: a percentage above 100, a negative "
                      "value, a yield above conversion, a temperature above 350 C, or an "
                      "implausible mass. Blank means the row passed every check."),
    ("Blank cells", "A blank means the paper did not report the value, not zero. Yield is "
                    "absent on about half of all rows; selectivity on almost all of them."),
    ("What it does not support", "Pooled yield prediction. Temperature and yield correlate "
                                 "inside a paper and not across papers, because papers define "
                                 "yield differently and because 148 of 206 papers with a "
                                 "usable yield ran every experiment at a single temperature. "
                                 "Split by doi, never at random: a random row split reports "
                                 "R2 = +0.44 where a paper-level split gives -0.27."),
]


def build(with_baselines: bool):
    frame = pd.read_parquet(SOURCE)
    calls = [classify(str(n), str(s or ""), str(t or ""))
             for n, s, t in zip(frame.catalyst, frame.catalyst_smiles,
                                frame.catalyst_smiles_tier)]
    frame["phase"] = [p for p, _, _ in calls]
    frame["phase_why"] = [w for _, w, _ in calls]
    frame["phase_by"] = [b for _, _, b in calls]

    keep = ["homogeneous"] + (["uncatalysed"] if with_baselines else [])
    included = frame[frame.phase.isin(keep)].copy()
    excluded = frame[~frame.phase.isin(keep)].copy()

    included["structure_source"] = included.catalyst_smiles_tier
    included["audit"] = included.judge_verdict.map({"correct": "accepted",
                                                    "incorrect": "flagged"})
    included["catalyst_loading_wt"] = (included.catalyst_amount_g /
                                       included.PET_amount_g.replace(0, np.nan)).round(4)
    basis = pd.read_csv(BASIS).set_index("doi").yield_basis
    included["yield_basis"] = included.doi.map(basis).replace("", np.nan)

    multi = included.catalyst.astype(str).str.contains(r"\s/\s|\s\+\s|,\s|\sand\s", na=False)
    included["single_component"] = ~multi
    # A cell naming two substances was given one dot-disconnected SMILES, which RDKit parses
    # without complaint and describes as a molecule that has never existed: "TBD / zinc acetate"
    # comes back at MW 309, the two catalysts added together. Blank the structure so anything
    # derived from it fails loudly instead of silently. The experiment itself is kept.
    included.loc[multi, ["catalyst_smiles", "catalyst_smiles_tier"]] = np.nan
    included["structure_source"] = included.catalyst_smiles_tier

    first = included.drop_duplicates(subset=EXPERIMENT, keep="first")
    lookup = first.set_index([*EXPERIMENT]).record_id
    index = pd.MultiIndex.from_frame(included[EXPERIMENT])
    included["duplicate_of"] = lookup.reindex(index).values
    included.loc[included.duplicate_of == included.record_id, "duplicate_of"] = np.nan

    included["quality_flags"] = [flags(row) for _, row in included.iterrows()]
    return included, excluded


def flags(row) -> str:
    found = []
    for field in ("yield_percent", "conversion_percent", "selectivity_percent"):
        value = row.get(field)
        if pd.notna(value) and value > 100:
            found.append(f"{field.split('_')[0]} above 100%")
        if pd.notna(value) and value < 0:
            found.append(f"{field.split('_')[0]} negative")
    if pd.notna(row.yield_percent) and pd.notna(row.conversion_percent) \
            and row.yield_percent > row.conversion_percent + 1.0:
        found.append("yield above conversion")
    if pd.notna(row.temperature_c) and row.temperature_c > 350:
        found.append("temperature above 350C -- pyrolysis, not solvolysis")
    if pd.notna(row.PET_amount_g) and row.PET_amount_g > 1000:
        found.append("PET mass beyond bench or pilot scale")
    if pd.notna(row.catalyst_amount_g) and pd.notna(row.PET_amount_g) \
            and row.PET_amount_g > 0 and row.catalyst_amount_g / row.PET_amount_g > 1:
        found.append("more catalyst than PET")
    return "; ".join(found)


# ---------------------------------------------------------------------------------------------
# sheets
# ---------------------------------------------------------------------------------------------

def style_header(sheet, columns):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor=HEADER)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for index, name in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = WIDTH.get(name, 14)


def table_sheet(sheet, frame, columns, freeze="C2", warn_column=None):
    from openpyxl.styles import PatternFill
    warn = PatternFill("solid", fgColor="F6DED7")
    sheet.append(columns)
    at = columns.index(warn_column) if warn_column in columns else None
    for row in frame[columns].itertuples(index=False):
        sheet.append([None if (isinstance(v, float) and pd.isna(v)) or v is pd.NA else v
                      for v in row])
        if at is not None and row[at]:
            for cell in sheet[sheet.max_row]:
                cell.fill = warn
    style_header(sheet, columns)
    sheet.freeze_panes = freeze
    sheet.auto_filter.ref = sheet.dimensions


def readme_sheet(sheet, data, excluded):
    from openpyxl.styles import Alignment, Font
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 96
    sheet["A1"] = "PET depolymerisation — homogeneous catalysis"
    sheet["A1"].font = Font(bold=True, size=15)
    sheet["A2"] = ("Every experiment whose catalyst dissolves in the reaction liquid, "
                   "extracted from the literature and audited.")
    sheet["A2"].font = Font(size=10, color="595959")

    catalysed = data[data.phase == "homogeneous"]
    modelable = data[["yield_percent", "temperature_c", "reaction_time_min",
                      "catalyst_amount_g", "PET_amount_g"]].notna().all(axis=1)
    rows = [
        ("", ""),
        ("Experiments", f"{len(data):,}"),
        ("  with a dissolved catalyst", f"{len(catalysed):,}"),
        ("  uncatalysed baselines", f"{(data.phase == 'uncatalysed').sum():,}"),
        ("Papers", f"{data.doi.nunique():,}"),
        ("Distinct catalysts (as written)", f"{catalysed.catalyst.nunique():,}"),
        ("Distinct structures", f"{catalysed.catalyst_smiles.nunique():,}"),
        ("", ""),
        ("Rows carrying a yield", f"{data.yield_percent.notna().sum():,} "
                                  f"({100 * data.yield_percent.notna().mean():.0f}%)"),
        ("Rows complete enough to model", f"{modelable.sum():,} from "
                                          f"{data[modelable].doi.nunique()} papers"),
        ("  (yield, temperature, time and both masses)", ""),
        ("", ""),
        ("Structures confirmed independently", f"{(data.structure_source == 'confirmed').sum():,} "
                                               f"({100 * (data.structure_source == 'confirmed').mean():.0f}%)"),
        ("Structures written by a model, unverified",
         f"{(data.structure_source == 'LLM written').sum():,} "
         f"({100 * (data.structure_source == 'LLM written').mean():.0f}%)"),
        ("Records the audit flagged", f"{(data.audit == 'flagged').sum():,} "
                                      f"({100 * (data.audit == 'flagged').mean():.0f}%)"),
        ("Records failing a range check", f"{(data.quality_flags != '').sum():,}"),
        ("Records duplicating another", f"{data.duplicate_of.notna().sum():,}"),
        ("Rows naming more than one catalyst", f"{(~data.single_component).sum():,}"),
        ("", ""),
        ("Excluded as solid", f"{(excluded.phase == 'heterogeneous').sum():,} records"),
        ("Excluded as enzymatic", f"{(excluded.phase == 'biocatalytic').sum():,} records"),
        ("Excluded, catalyst unidentifiable", f"{(excluded.phase == 'unknown').sum():,} records"),
        ("", ""),
        ("Read before modelling",
         "Split by doi, never at random. Temperature and yield correlate inside a paper and "
         "not across papers; a random row split reports R2 = +0.44 where a paper-level split "
         "gives -0.27. See the Schema sheet."),
    ]
    for label, value in rows:
        sheet.append([label, value])
        row = sheet[sheet.max_row]
        row[0].font = Font(bold=not label.startswith("  ") and bool(label))
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        if len(str(value)) > 70:
            sheet.row_dimensions[sheet.max_row].height = 46


def catalysts_sheet(sheet, data, frame):
    table = (frame.groupby("catalyst", dropna=False)
             .agg(records=("doi", "size"), papers=("doi", "nunique"),
                  catalyst_smiles=("catalyst_smiles", "first"),
                  structure_source=("catalyst_smiles_tier", "first"),
                  phase=("phase", "first"), why=("phase_why", "first"),
                  decided_by=("phase_by", "first"),
                  median_yield=("yield_percent", "median"),
                  median_temperature=("temperature_c", "median"))
             .reset_index().sort_values("records", ascending=False))
    table["median_yield"] = table.median_yield.round(1)
    columns = ["catalyst", "records", "papers", "phase", "why", "decided_by",
               "catalyst_smiles", "structure_source", "median_yield", "median_temperature"]
    table_sheet(sheet, table, columns, freeze="B2")


def charts_sheet(sheet, data):
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.marker import DataPoint
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.styles import Font

    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 10
    sheet["A1"] = f"What is in the collection ({len(data):,} experiments)"
    sheet["A1"].font = Font(bold=True, size=14)

    def bands(series, edges, labels):
        cut = pd.cut(series.dropna(), bins=edges, labels=labels, include_lowest=True)
        return cut.value_counts().reindex(labels).fillna(0).astype(int)

    def top(series, n):
        counts = series.fillna("(not reported)").value_counts()
        head = counts.head(n)
        rest = int(counts[n:].sum())
        if rest:
            head = pd.concat([head, pd.Series({f"other ({len(counts) - n} more)": rest})])
        return head

    catalysed = data[data.phase == "homogeneous"]
    blocks = [
        ("Reaction route", data.route.fillna("no route").value_counts(), "pie"),
        ("Catalyst class", catalysed.catalyst_class.fillna("unclassified").value_counts(), "pie"),
        ("Where the structure came from", data.structure_source.value_counts(), "pie"),
        ("Audit verdict", data.audit.fillna("no catalyst").value_counts(), "pie"),
        ("Most used catalysts", top(catalysed.catalyst, 8), "pie"),
        ("Most used solvents", top(data.solvent, 8), "pie"),
        ("Reported yield (%)", bands(data.yield_percent, [-0.01, 20, 40, 60, 80, 100, 10 ** 6],
                                     ["0-20", "20-40", "40-60", "60-80", "80-100", ">100"]), "bar"),
        ("Temperature (°C)", bands(data.temperature_c, [-0.01, 100, 150, 180, 200, 250, 10 ** 6],
                                   ["<100", "100-150", "150-180", "180-200", "200-250", ">250"]),
         "bar"),
        ("Experiments per paper", bands(data.groupby("doi").size(), [0, 1, 2, 5, 10, 20, 10 ** 6],
                                        ["1", "2", "3-5", "6-10", "11-20", "21+"]), "bar"),
        ("How often each field is reported (%)",
         (data[["temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
                "solvent_amount_g", "pressure_atm", "yield_percent", "conversion_percent",
                "selectivity_percent"]].notna().mean().mul(100).round(0).astype(int)
          .rename(lambda s: s.replace("_percent", " %").replace("_g", " (g)")
                  .replace("_c", " (°C)").replace("_min", " (min)").replace("_atm", " (atm)")
                  .replace("_", " "))), "bar"),
    ]

    row, anchors = 3, []
    for title, counts, kind in blocks:
        sheet.cell(row=row, column=1, value=title).font = Font(bold=True)
        row += 1
        first = row
        for name, value in counts.items():
            sheet.cell(row=row, column=1, value=str(name))
            sheet.cell(row=row, column=2, value=int(value))
            row += 1
        anchors.append((title, first, row - 1, len(counts), kind))
        row += 2

    grid = ["D", "L", "T"]
    for index, (title, first, last, size, kind) in enumerate(anchors):
        chart = PieChart() if kind == "pie" else BarChart()
        chart.title = title
        chart.height, chart.width = 8.0, 11.5
        chart.add_data(Reference(sheet, min_col=2, min_row=first, max_row=last),
                       titles_from_data=False)
        chart.set_categories(Reference(sheet, min_col=1, min_row=first, max_row=last))
        if kind == "pie":
            chart.dataLabels = DataLabelList()
            chart.dataLabels.showPercent = True
            chart.series[0].data_points = [
                DataPoint(idx=i, spPr=GraphicalProperties(solidFill=PALETTE[i % len(PALETTE)]))
                for i in range(size)]
        else:
            chart.type, chart.legend = "col", None
            chart.y_axis.title = "records"
            chart.series[0].graphicalProperties.solidFill = PALETTE[0]
        sheet.add_chart(chart, f"{grid[index % 3]}{4 + (index // 3) * 17}")


def schema_sheet(sheet):
    from openpyxl.styles import Alignment, Font
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 104
    sheet["A1"] = "What each column means"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([])
    for head, body in SCHEMA:
        sheet.append([head, body])
        row = sheet[sheet.max_row]
        row[0].font = Font(bold=True)
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[sheet.max_row].height = max(30, 13 * (len(body) // 95 + 1) + 17)


def main() -> None:
    parser = argparse.ArgumentParser(prog="build_release")
    parser.add_argument("--no-baselines", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    data, excluded = build(not args.no_baselines)
    for column in COLUMNS:
        if column not in data:
            data[column] = np.nan

    from openpyxl import Workbook
    book = Workbook()
    book.remove(book.active)
    readme_sheet(book.create_sheet("Read me"), data, excluded)
    table_sheet(book.create_sheet("Data"), data, COLUMNS, warn_column="quality_flags")
    catalysts_sheet(book.create_sheet("Catalysts"), data, data)
    excluded_columns = ["record_id", "doi", "catalyst", "catalyst_smiles", "phase",
                        "phase_why", "route", "solvent", "temperature_c", "yield_percent"]
    table_sheet(book.create_sheet("Excluded"),
                excluded.rename(columns={"phase_why": "why"}),
                [c if c != "phase_why" else "why" for c in excluded_columns], freeze="B2")
    charts_sheet(book.create_sheet("Charts"), data)
    schema_sheet(book.create_sheet("Schema"))

    import hashlib
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.out.with_suffix(".csv"), index=False)
    digest = hashlib.sha256(args.out.with_suffix(".csv").read_bytes()).hexdigest()[:12]
    sheet = book["Read me"]
    sheet.append([])
    sheet.append([f"Version {VERSION}", f"content hash {digest}"])
    book.save(args.out)
    (args.out.parent / "VERSION").write_text(f"{VERSION}\n{digest}\n{len(data)} rows\n")

    print(f"{len(data):,} experiments   {data.doi.nunique()} papers   "
          f"{data[data.phase == 'homogeneous'].catalyst_smiles.nunique()} structures")
    print(f"  dissolved catalyst {(data.phase == 'homogeneous').sum():,}   "
          f"uncatalysed baselines {(data.phase == 'uncatalysed').sum():,}")
    print(f"  excluded: {(excluded.phase == 'heterogeneous').sum():,} solid, "
          f"{(excluded.phase == 'biocatalytic').sum():,} enzymatic, "
          f"{(excluded.phase == 'unknown').sum():,} unidentifiable")
    print(f"  flagged: {(data.quality_flags != '').sum():,} range violations, "
          f"{data.duplicate_of.notna().sum():,} duplicates, "
          f"{(~data.single_component).sum():,} multi-catalyst")
    print(f"\nwrote {args.out.relative_to(ROOT)}")
    print(f"wrote {args.out.with_suffix('.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
