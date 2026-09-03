"""The database as one Excel workbook, with the SMILES columns colour-coded by how they got there.

The point of the colour is to make the gaps skimmable. Scrolling the catalyst column, a reader
should be able to see without reading a single cell how much of the structure information is
solid, how much is missing but obtainable, and how much never will be.

    no fill    a direct mapping: the name matched the lookup, or every component of a mixture did
    yellow     unclear -- either not in the lookup yet, or resolved to an ionic solid whose SMILES
               is a formula rather than a molecule
    grey       no single structure exists (a supported catalyst, a zeolite, a resin), or there was
               nothing to map (no catalyst used, field not reported)

The SMILES column sits immediately left of the name it was derived from, so the two read together.

    export_excel.py                 write artifacts/release/pet_depolymerisation.xlsx
    export_excel.py --out <path>
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.paths import ARTIFACTS
from core.smiles import TIERS, cleaned, canonical, product_for, substrate, tier_of

FLAT = ARTIFACTS / "release" / "mass_luna_1shot_flat.csv"
OUT = ARTIFACTS / "release" / "pet_depolymerisation.xlsx"

HEADER = "1F4E5F"

# One colour per tier, and only three of them carry a fill: a confirmed value is the normal case
# and gets none, so the eye goes straight to what needs attention.
FILLS = {"LLM written": "DDEBF7",    # blue: usable, but only one source stands behind it
         "unclear":     "FFF2CC",    # yellow: someone could fix this
         "impossible":  "D9D9D9",    # grey: nobody can
         "not reported": "F2F2F2"}   # faint grey: the paper is silent
# "no catalyst" gets no fill, like "confirmed": both are complete answers, not gaps.

# The first sheet is the chemistry: what was reacted, under what conditions, to what effect.
# Everything about how the record was obtained and audited lives on the second sheet, because it
# answers a different question and there is a lot of it.
ESSENTIALS = ["record_id", "doi", "route",
              "catalyst_smiles", "catalyst_smiles_tier", "catalyst", "catalyst_amount_g",
              "solvent_smiles", "solvent_smiles_tier", "solvent", "solvent_amount_g",
              "PET_amount_g", "temperature_c", "reaction_time_min", "pressure_atm",
              "yield_percent", "conversion_percent", "selectivity_percent",
              "product", "product_smiles", "judge_verdict"]

# How wide each column opens. Anything unlisted gets a default; the long prose columns are capped
# so the sheet is navigable rather than one screen of critique.
WIDTHS = {"record_id": 34, "doi": 26, "title": 46, "journal": 22,
          "catalyst": 26, "catalyst_smiles": 34, "catalyst_smiles_tier": 12,
          "solvent_smiles_tier": 12, "solvent": 22, "solvent_smiles": 24,
          "judge_critique": 60, "judge_fixes": 40, "source_chunk_ids": 26,
          "product_smiles": 30, "substrate_smiles": 30}


# The tiers that leave a row usable for cheminformatics. "no catalyst" belongs here: an
# uncatalysed reaction is a complete observation, and its empty SMILES is the right value.
USABLE = ("confirmed", "LLM written", "no catalyst")


def build() -> tuple[pd.DataFrame, dict]:
    """The flat table with SMILES columns inserted, and the tier of every SMILES cell.

    OPSIN is asked once for the whole vocabulary rather than once per record: it starts a JVM per
    call, and 5,563 calls take longer than the rest of this tool put together.
    """
    from py2opsin import py2opsin

    frame = pd.read_csv(FLAT)
    states = {}

    for column, kind in (("catalyst", "catalyst"), ("solvent", "solvent")):
        names = sorted({str(v).strip() for v in frame[column].dropna() if str(v).strip()})
        derived = dict(zip(names, py2opsin(names)))
        needs_tidying = [n for n in names if not derived[n]]
        for name, result in zip(needs_tidying, py2opsin([cleaned(n) for n in needs_tidying])):
            derived[name] = result

        answer = {n: tier_of(n, kind, canonical(derived[n]) if derived[n] else None) for n in names}
        key = frame[column].astype(str).str.strip()
        smiles = key.map({n: a[0] for n, a in answer.items()})
        tiers = key.map({n: a[1] for n, a in answer.items()}).fillna("impossible")

        frame.insert(frame.columns.get_loc(column), f"{column}_smiles", smiles)
        frame.insert(frame.columns.get_loc(column) + 1, f"{column}_smiles_tier", tiers)
        states[f"{column}_smiles"] = list(tiers)

    products = [product_for(route) for route in frame["route"]]
    frame["product"] = [n for n, _ in products]
    frame["product_smiles"] = [s for _, s in products]
    states["product_smiles"] = ["confirmed" if s else "not reported" for _, s in products]
    frame["substrate_smiles"] = substrate()
    states["substrate_smiles"] = ["confirmed"] * len(frame)
    return frame, states


def write(frame: pd.DataFrame, states: dict, out: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    book = Workbook()
    header_fill = PatternFill("solid", fgColor=HEADER)
    header_font = Font(color="FFFFFF", bold=True)
    fills = {tier: PatternFill("solid", fgColor=colour) for tier, colour in FILLS.items()}

    def lay_out(sheet, columns):
        sheet.append(columns)
        for cell in sheet[1]:
            cell.fill, cell.font = header_fill, header_font
            cell.alignment = Alignment(vertical="center", wrap_text=False)
        for record in frame[columns].itertuples(index=False):
            sheet.append(["" if pd.isna(v) else v for v in record])
        for name, marks in states.items():
            if name not in columns:
                continue
            letter = get_column_letter(columns.index(name) + 1)
            for row, mark in enumerate(marks, start=2):
                if mark in fills:
                    sheet[f"{letter}{row}"].fill = fills[mark]
        for index, name in enumerate(columns, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = WIDTHS.get(name, 15)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    first = book.active
    first.title = "reactions"
    lay_out(first, [c for c in ESSENTIALS if c in frame.columns])
    lay_out(book.create_sheet("full record"), list(frame.columns))

    legend = book.create_sheet("legend")
    for row in [
        ["PET depolymerisation database"],
        [f"{len(frame):,} records from {frame['doi'].nunique():,} papers"],
        [],
        ["Sheets"],
        ["", "reactions", "what was reacted, under what conditions, to what effect"],
        ["", "full record", "the same rows with provenance, the judge's verdict and its proposed changes"],
        [],
        ["How much stands behind each SMILES"],
        ["", "confirmed", TIERS["confirmed"]],
        ["", "LLM written", TIERS["LLM written"]],
        ["", "no catalyst", TIERS["no catalyst"]],
        ["", "unclear", TIERS["unclear"]],
        ["", "impossible", TIERS["impossible"]],
        ["", "not reported", TIERS["not reported"]],
        [],
        ["Coverage"],
    ]:
        legend.append(row)
    for column in ("catalyst_smiles", "solvent_smiles", "product_smiles"):
        counts = pd.Series(states[column]).value_counts()
        legend.append(["", column,
                       "   ".join(f"{tier} {counts.get(tier, 0):,}" for tier in TIERS)])
    legend.append([])
    legend.append(["Every non-empty SMILES parses in RDKit and is written in its canonical form."])
    legend.append(["The name-to-SMILES table is artifacts/data/smiles_lookup.csv, a CSV meant to be"])
    legend.append(["read and corrected. tools/smiles_review.py exports it for review with formula"])
    legend.append(["and molecular weight, and ingests corrections after validating them."])
    legend.column_dimensions["B"].width = 20
    legend.column_dimensions["C"].width = 92
    # the section headers and the colour swatches, located by their text rather than by a row
    # number that shifts whenever a line is added above them
    legend["A1"].font = Font(bold=True, size=14)
    for row in legend.iter_rows(min_col=1, max_col=1):
        if row[0].value in ("Sheets", "How much stands behind each SMILES", "Coverage"):
            row[0].font = Font(bold=True)
    for row in legend.iter_rows(min_col=2, max_col=2):
        swatch = fills.get(row[0].value)
        if swatch:
            row[0].fill = swatch

    add_charts(book, legend, frame, states)

    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)


# Slice colours. The tier pies reuse the sheet's own fills so a slice and a cell mean the same
# thing, except that "confirmed" gets a visible teal here -- an unfilled slice would read as a
# hole in the pie rather than as the normal case.
TIER_COLOURS = {"confirmed": "2E7D6B", "LLM written": "5B9BD5", "no catalyst": "7FB8A4",
                "unclear": "E8C15F", "impossible": "BFBFBF", "not reported": "E8E8E8"}
VERDICT_COLOURS = {"accepted as written": "2E7D6B",
                   "rejected, correction proposed": "E8A33D",
                   "rejected outright": "C0504D"}
ROUTE_COLOURS = {"glycolysis": "0E7C6B", "hydrolysis": "C4527A",
                 "methanolysis": "9A6510", "other/unclear": "4A6B8A"}


def add_charts(book, legend, frame: pd.DataFrame, states: dict) -> None:
    """Native Excel pies on the legend sheet, driven by cells so they stay live in the workbook.

    The source counts are written into a block on the same sheet rather than hard-coded into the
    chart, so a reader can see the numbers the slices came from and Excel can redraw them.
    """
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.marker import DataPoint
    from openpyxl.styles import Font
    from openpyxl.chart.shapes import GraphicalProperties

    start = legend.max_row + 3
    legend.cell(row=start - 1, column=1, value="Chart data").font = Font(bold=True)
    row = start

    def block(title, pairs, colours):
        """Write a labelled count block, return (first_row, last_row) of its data."""
        nonlocal row
        legend.cell(row=row, column=1, value=title).font = Font(bold=True)
        row += 1
        first = row
        for label, count in pairs:
            legend.cell(row=row, column=1, value=label)
            legend.cell(row=row, column=2, value=int(count))
            row += 1
        last = row - 1
        row += 1
        return first, last, colours

    def pie(title, first, last, colours, anchor):
        chart = PieChart()
        chart.title = title
        chart.height, chart.width = 7.5, 11
        labels = Reference(legend, min_col=1, min_row=first, max_row=last)
        data = Reference(legend, min_col=2, min_row=first, max_row=last)
        chart.add_data(data, titles_from_data=False)
        chart.set_categories(labels)
        series = chart.series[0]
        series.data_points = [
            DataPoint(idx=i, spPr=GraphicalProperties(
                solidFill=colours[legend.cell(row=first + i, column=1).value]))
            for i in range(last - first + 1)]
        chart.dataLabels = None
        legend.add_chart(chart, anchor)

    order = list(TIERS)
    for column, anchor, title in (("catalyst_smiles", "E2", "Catalyst structures"),
                                  ("solvent_smiles", "M2", "Solvent structures")):
        counts = pd.Series(states[column]).value_counts()
        first, last, colours = block(title, [(t, counts.get(t, 0)) for t in order], TIER_COLOURS)
        pie(f"{title}: how much stands behind them", first, last, colours, anchor)

    dropped = int(frame["judge_drop_record"].fillna(False).astype(bool).sum())
    accepted = int((frame["judge_verdict"] == "correct").sum())
    verdicts = [("accepted as written", accepted),
                ("rejected, correction proposed", len(frame) - accepted - dropped),
                ("rejected outright", dropped)]
    first, last, colours = block("Judge verdicts", verdicts, VERDICT_COLOURS)
    pie("What the audit made of the records", first, last, colours, "E17")

    routes = frame["route"].value_counts()
    first, last, colours = block(
        "Depolymerisation route", [(r, routes.get(r, 0)) for r in ROUTE_COLOURS], ROUTE_COLOURS)
    pie("Records by route", first, last, colours, "M17")

    # Completeness is not parts of a whole -- each field is its own reported/not-reported split --
    # so it gets a bar chart. A pie of nine fields would sum to nothing meaningful.
    fields = ["reaction_time_min", "temperature_c", "PET_amount_g", "yield_percent",
              "catalyst_amount_g", "conversion_percent", "solvent_amount_g",
              "pressure_atm", "selectivity_percent"]
    legend.cell(row=row, column=1, value="Field completeness (% of records)").font = Font(bold=True)
    row += 1
    first = row
    for name in fields:
        legend.cell(row=row, column=1, value=name.replace("_", " "))
        legend.cell(row=row, column=2, value=round(100 * frame[name].notna().mean(), 1))
        row += 1
    bars = BarChart()
    bars.type, bars.title = "bar", "How often each field is reported"
    bars.height, bars.width = 8.5, 11
    bars.add_data(Reference(legend, min_col=2, min_row=first, max_row=row - 1), titles_from_data=False)
    bars.set_categories(Reference(legend, min_col=1, min_row=first, max_row=row - 1))
    bars.legend = None
    bars.y_axis.title = "% of records"
    bars.series[0].graphicalProperties = GraphicalProperties(solidFill="2E7D6B")
    legend.add_chart(bars, "E32")


def keep_usable(frame: pd.DataFrame, states: dict, both: bool) -> tuple[pd.DataFrame, dict]:
    """Drop rows whose structure information is missing rather than merely absent."""
    mask = frame["catalyst_smiles_tier"].isin(USABLE)
    if both:
        mask &= frame["solvent_smiles_tier"].isin(USABLE)
    kept = mask.to_numpy()
    trimmed = {name: [m for m, k in zip(marks, kept) if k] for name, marks in states.items()}
    return frame[mask].reset_index(drop=True), trimmed


def main() -> None:
    parser = argparse.ArgumentParser(prog="export_excel")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--usable-only", action="store_true",
                        help="keep only rows whose catalyst SMILES is confirmed, LLM-written or "
                             "genuinely absent")
    parser.add_argument("--both", action="store_true",
                        help="with --usable-only, require the solvent to be usable too")
    args = parser.parse_args()

    frame, states = build()
    if args.usable_only:
        whole = len(frame)
        frame, states = keep_usable(frame, states, args.both)
        print(f"kept {len(frame):,} of {whole:,} rows "
              f"({100 * len(frame) / whole:.0f}%) on catalyst"
              f"{' and solvent' if args.both else ''} tier\n")
    write(frame, states, args.out)

    print(f"rows {len(frame):,}   columns {len(frame.columns)}")
    for column in ("catalyst_smiles", "solvent_smiles", "product_smiles"):
        counts = pd.Series(states[column]).value_counts()
        print(f"  {column}")
        for tier in TIERS:
            n = counts.get(tier, 0)
            print(f"      {tier:12s} {n:5,} ({100 * n / len(frame):5.1f}%)")
    shown = args.out.resolve()
    shown = shown.relative_to(ROOT) if ROOT in shown.parents else shown
    print(f"\nwrote {shown}  ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
