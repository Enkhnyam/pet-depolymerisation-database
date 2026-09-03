"""The homogeneous-catalysis subset, simplified, with the shape of it drawn out in charts.

catalyst_classification.xlsx is for investigating what is wrong. This is the other thing: a
short, readable view of what the dataset actually contains, for deciding whether it looks
right at all.

Homogeneous means the catalyst dissolves into the reaction liquid, so the schema's fields --
identity, amount, temperature, time -- are the ones that set the rate. Metal oxides and supported
catalysts are excluded because their rates turn on surface area, particle size and calcination,
which this schema does not record. See core/catalyst_class.phase.

  Charts     the composition of the subset, one pie per question, plus completeness and the
             yield distribution as bars where a pie would mislead
  Data       one row per experiment, the columns worth reading
  Catalysts  what is actually in it, by frequency
  Notes      what each column means and what the subset excludes

    export_homogeneous.py                  artifacts/release/pet_homogeneous.xlsx
    export_homogeneous.py --with-baselines include the uncatalysed runs as baselines
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.catalyst_class import classify, phase
from core.paths import ARTIFACTS

HF = ARTIFACTS / "huggingface" / "usable" / "records-00000-of-00001.parquet"
OUT = ARTIFACTS / "release" / "pet_homogeneous.xlsx"

HEADER = "1F3B4D"
PALETTE = ["3E6E8E", "B0523E", "86689F", "8D8677", "6C9E9C", "B08A3E", "57896B",
           "6A8CA8", "C4785F", "A98CC4", "A29A88", "8AC2C0", "D0A85A", "C6CBD1"]

COLUMNS = ["doi", "catalyst", "catalyst_smiles", "catalyst_class", "route", "solvent",
           "temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
           "solvent_amount_g", "yield_percent", "conversion_percent", "selectivity_percent",
           "structure_source", "audit", "quality"]
WIDTHS = {"doi": 27, "catalyst": 30, "catalyst_smiles": 36, "catalyst_class": 17,
          "route": 13, "solvent": 20, "structure_source": 14, "audit": 12, "quality": 22,
          "records": 9, "share": 8}

NOTES = [
    ("What this subset is",
     "Experiments where the catalyst dissolves into the reaction liquid -- one phase. "
     "Metal oxides (ZnO, TiO2, CaO, Sb2O3 ...) and supported or nano catalysts are excluded: "
     "their rate depends on surface area, particle size and calcination, none of which this "
     "schema records, so no model built on these columns could predict them."),
    ("catalyst", "As the source paper writes it. Not normalised."),
    ("catalyst_smiles", "Canonical SMILES, parseable by RDKit."),
    ("structure_source",
     "How the SMILES was obtained. 'confirmed' means OPSIN derived it independently from the "
     "name. 'LLM written' means a language model supplied it and no library can read the name to "
     "check it -- it may well be right, but nothing independent confirms it."),
    ("catalyst_class",
     "Derived from the structure: an organic cation with a counter-anion is an organic salt or "
     "ionic liquid; a Bronsted acid or a hydroxide, alkoxide, carbonate or amine is an acid or "
     "base; anything else holding a metal is a metal salt."),
    ("route", "Inferred from the solvent, not stated by the paper. Glycolysis gives BHET, "
              "methanolysis DMT, hydrolysis TPA."),
    ("yield / conversion / selectivity",
     "As extracted from the paper. The judge's proposed corrections are NOT applied here; see "
     "catalyst_classification.xlsx for both views side by side."),
    ("audit", "An independent language model's verdict on the as-extracted record. 'flagged' "
              "means it thought something was unsupported, not that it is certainly wrong."),
    ("quality", "Range and identity violations: a percentage above 100, a negative number, or a "
                "yield exceeding conversion. Blank means the row survived every check."),
    ("Blank cells", "A blank means the paper did not report the value, not that extraction "
                    "missed it. Selectivity is blank almost everywhere because papers rarely "
                    "report it."),
]


def build(with_baselines: bool) -> pd.DataFrame:
    d = pd.read_parquet(HF).copy()
    d["catalyst_class"] = [classify(s, t) for s, t in
                           zip(d.catalyst_smiles, d.catalyst_smiles_tier)]
    d["phase"] = [phase(c, s, t)[0] for c, s, t in
                  zip(d.catalyst, d.catalyst_smiles, d.catalyst_smiles_tier)]
    keep = ["homogeneous", "uncatalysed"] if with_baselines else ["homogeneous"]
    d = d[d.phase.isin(keep)].reset_index(drop=True)

    d["structure_source"] = d.catalyst_smiles_tier
    d["audit"] = d.judge_verdict.map({"correct": "accepted", "incorrect": "flagged"})

    problems = []
    for _, row in d.iterrows():
        found = []
        for field in ("yield_percent", "conversion_percent", "selectivity_percent"):
            if pd.notna(row[field]) and row[field] > 100:
                found.append(f"{field.split('_')[0]} > 100%")
            if pd.notna(row[field]) and row[field] < 0:
                found.append(f"{field.split('_')[0]} negative")
        if pd.notna(row.yield_percent) and pd.notna(row.conversion_percent) \
                and row.yield_percent > row.conversion_percent + 1.0:
            found.append("yield > conversion")
        problems.append("; ".join(found))
    d["quality"] = problems
    return d


def bands(series, edges, labels):
    cut = pd.cut(series.dropna(), bins=edges, labels=labels, include_lowest=True)
    return cut.value_counts().reindex(labels).fillna(0).astype(int)


def top_with_other(series, n):
    counts = series.fillna("(not reported)").value_counts()
    head = counts.head(n)
    rest = int(counts[n:].sum())
    if rest:
        head = pd.concat([head, pd.Series({f"other ({len(counts) - n} more)": rest})])
    return head


def charts_sheet(sheet, d):
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.marker import DataPoint
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.styles import Font

    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 10
    sheet["A1"] = f"PET depolymerisation — homogeneous catalysis ({len(d):,} experiments)"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = (f"{d.doi.nunique():,} papers · {d.catalyst.nunique():,} distinct catalysts · "
                   f"{d.catalyst_smiles.nunique():,} distinct structures")
    sheet["A2"].font = Font(size=10, color="595959")

    blocks = [
        ("Reaction route", d.route.value_counts(), "pie"),
        ("Catalyst class (from structure)", d.catalyst_class.value_counts(), "pie"),
        ("Where the structure came from", d.structure_source.value_counts(), "pie"),
        ("Audit verdict", d.audit.value_counts(), "pie"),
        ("Most used catalysts", top_with_other(d.catalyst, 8), "pie"),
        ("Most used solvents", top_with_other(d.solvent, 8), "pie"),
        ("Source document format", d.source_format.fillna("unknown").value_counts(), "pie"),
        ("Records per paper", bands(d.groupby("doi").size(),
                                    [0, 1, 2, 5, 10, 20, 10**6],
                                    ["1", "2", "3-5", "6-10", "11-20", "21+"]), "pie"),
        ("Reported yield (%)", bands(d.yield_percent, [-0.01, 20, 40, 60, 80, 100, 10**6],
                                     ["0-20", "20-40", "40-60", "60-80", "80-100", ">100"]), "bar"),
        ("Temperature (°C)", bands(d.temperature_c, [-0.01, 100, 150, 180, 200, 250, 10**6],
                                   ["<100", "100-150", "150-180", "180-200", "200-250", ">250"]),
         "bar"),
        ("Field completeness (% of records)",
         (d[["temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
             "solvent_amount_g", "yield_percent", "conversion_percent", "selectivity_percent"]]
          .notna().mean().mul(100).round(0).astype(int)
          .rename(lambda s: s.replace("_percent", " %").replace("_g", " (g)")
                  .replace("_c", " (°C)").replace("_min", " (min)").replace("_", " "))), "bar"),
    ]

    row = 5
    anchors = []
    for title, counts, kind in blocks:
        sheet.cell(row=row, column=1, value=title).font = Font(bold=True)
        row += 1
        first = row
        for name, n in counts.items():
            sheet.cell(row=row, column=1, value=str(name))
            sheet.cell(row=row, column=2, value=int(n))
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
        column = grid[index % 3]
        anchor_row = 4 + (index // 3) * 17
        sheet.add_chart(chart, f"{column}{anchor_row}")


def data_sheet(sheet, d):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    head_fill, head_font = PatternFill("solid", fgColor=HEADER), Font(color="FFFFFF", bold=True)
    warn = PatternFill("solid", fgColor="F6DED7")

    sheet.append(COLUMNS)
    for cell in sheet[1]:
        cell.fill, cell.font = head_fill, head_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    quality_at = COLUMNS.index("quality")
    for row in d[COLUMNS].itertuples(index=False):
        sheet.append([None if pd.isna(v) else v for v in row])
        if row[quality_at]:
            for cell in sheet[sheet.max_row]:
                cell.fill = warn
    for index, name in enumerate(COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = WIDTHS.get(name, 14)
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions


def catalysts_sheet(sheet, d):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    table = (d.groupby("catalyst", dropna=False)
             .agg(records=("doi", "size"), papers=("doi", "nunique"),
                  catalyst_smiles=("catalyst_smiles", "first"),
                  catalyst_class=("catalyst_class", "first"),
                  structure_source=("structure_source", "first"),
                  median_yield=("yield_percent", "median"),
                  median_temperature=("temperature_c", "median"))
             .reset_index().sort_values("records", ascending=False))
    table["share"] = (100 * table.records / len(d)).round(1)
    columns = ["catalyst", "records", "share", "papers", "catalyst_class", "structure_source",
               "median_yield", "median_temperature", "catalyst_smiles"]
    sheet.append(columns)
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor=HEADER)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in table[columns].itertuples(index=False):
        sheet.append([None if pd.isna(v) else (round(v, 1) if isinstance(v, float) else v)
                      for v in row])
    for index, name in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = WIDTHS.get(name, 16)
    sheet.freeze_panes = "B2"
    sheet.auto_filter.ref = sheet.dimensions


def notes_sheet(sheet):
    from openpyxl.styles import Alignment, Font
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["B"].width = 104
    sheet["A1"] = "What is in this file"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([])
    for head, body in NOTES:
        sheet.append([head, body])
        row = sheet[sheet.max_row]
        row[0].font = Font(bold=True)
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[sheet.max_row].height = 46


def main() -> None:
    parser = argparse.ArgumentParser(prog="export_homogeneous")
    parser.add_argument("--with-baselines", action="store_true",
                        help="include uncatalysed runs")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    from openpyxl import Workbook
    d = build(args.with_baselines)

    book = Workbook()
    book.remove(book.active)
    charts_sheet(book.create_sheet("Charts"), d)
    data_sheet(book.create_sheet("Data"), d)
    catalysts_sheet(book.create_sheet("Catalysts"), d)
    notes_sheet(book.create_sheet("Notes"))

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)

    print(f"{len(d):,} homogeneous experiments   {d.doi.nunique():,} papers   "
          f"{d.catalyst.nunique():,} catalysts")
    print("\nroute:      " + ", ".join(f"{k} {v:,}" for k, v in d.route.value_counts().items()))
    print("class:      " + ", ".join(f"{k} {v:,}" for k, v in d.catalyst_class.value_counts().items()))
    print("structures: " + ", ".join(f"{k} {v:,}" for k, v in d.structure_source.value_counts().items()))
    flagged = (d.quality != "").sum()
    print(f"\nrows failing a range or identity check: {flagged}")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
