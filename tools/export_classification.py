"""The database classified by structure, as a workbook you can sort and filter.

`catalyst_class` as shipped is a regex over the catalyst name. core/catalyst_class.py asks the
same question of the mapped SMILES instead. The two disagree on about one record in four, so this
writes both side by side with the structural facts that produced the second one, and leaves the
adjudication to a chemist.

Four sheets:

  Records        one row per record: both labels, whether they agree, and the five structural
                 flags the label was derived from
  By catalyst    one row per distinct catalyst name. 3,704 records are only a few hundred names,
                 so this is the sheet to actually work through
  Disagreements  the same, filtered to names where the two methods differ, ordered by how many
                 records each name decides. The top 50 names settle roughly four-fifths of them
  Method         the rule behind every class under both methods, and the two distributions as
                 pie charts

The usable subset is the default because it is exactly the set structure can decide: every row in
it either carries a SMILES or is a recorded uncatalysed run.

    export_classification.py              artifacts/release/catalyst_classification.xlsx
    export_classification.py --full       every record, including those with no structure
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.catalyst_class import CLASSES, FLAGS, PHASES, classify, flags, phase, why
from core.paths import ARTIFACTS

HF = ARTIFACTS / "huggingface"
OUT = ARTIFACTS / "release" / "catalyst_classification.xlsx"

HEADER = "1F3B4D"
FILLS = {                       # tints of the classes' chart colours, light enough to read on
    "metal salt":        "D6E4EF",
    "acid or base":      "F6DED7",
    "organic salt / IL": "E6DCEF",
    "none":              "E9E7E1",
    "organocatalyst":    "DCEEED",
    "other":             "F3E7CE",
    "no structure":      "EDEEF0",
}
CHART_COLOURS = {               # the artifact's palette, for the pies
    "metal salt": "3E6E8E", "acid or base": "B0523E", "organic salt / IL": "86689F",
    "ionic liquid": "86689F", "none": "8D8677", "organocatalyst": "6C9E9C",
    "other": "B08A3E", "no structure": "C6CBD1", "deep eutectic": "57896B",
}
WIDTHS = {"record_id": 34, "doi": 26, "catalyst": 34, "catalyst_smiles": 40,
          "catalyst_smiles_tier": 16, "structural_class": 18, "structural_reason": 38,
          "regex_class": 15, "agree": 8, "example_doi": 26, "records": 9, "solvent": 20,
          "judge_verdict": 13, "route": 14}

RECORD_COLUMNS = [
    "record_id", "doi", "catalyst", "catalyst_smiles", "catalyst_smiles_tier",
    "structural_class", "structural_reason", "regex_class", "agree", *FLAGS,
    "phase", "phase_reason",
    "route", "solvent", "temperature_c", "reaction_time_min",
    "catalyst_amount_g", "PET_amount_g",
    "yield_percent", "conversion_percent", "selectivity_percent",
    "corrected_yield_percent", "corrected_conversion_percent",
    "judge_verdict", "judge_drop_record", "citations_resolve",
    "flags_raised", "usable_for_modelling",
]
CATALYST_COLUMNS = [
    "catalyst", "records", "catalyst_smiles", "catalyst_smiles_tier",
    "structural_class", "structural_reason", "regex_class", "agree", *FLAGS,
    "phase", "phase_reason", "example_doi",
]

# The regex cascade, as it actually ships, so the sheet documents rather than paraphrases it.
REGEX_RULES = {
    "none": r"^(none|no catalyst|-|nan|without catalyst)$",
    "deep eutectic": r"\bdes\b|deep eutectic",
    "ionic liquid": r"\[.*\]|imidazol|\bil\b|phosphonium",
    "metal salt": r"\bzn|\bmn|\bco\(|\bfe|\bcu|\bti|\bmg|\bca\(|acetate|carbonate|chloride|oxide",
    "acid or base": r"naoh|koh|hydroxide|h2so4|sulfuric|hcl|nitric|amine|\btbd\b|\bdbu\b",
    "other": "everything the five rules above did not match",
}
STRUCT_RULES = {
    "none": "SMILES tier is 'no catalyst'",
    "organic salt / IL": "a fragment carries net + charge and another net -, and a + fragment "
                         "has carbon but no metal",
    "acid or base": "matches an acid SMARTS (carboxylic, sulfonic, phosphoric, hydrohalic, "
                    "nitric) or a base SMARTS (hydroxide, alkoxide, carbonate, amine, amidine)",
    "metal salt": "any atom outside the non-metal set",
    "organocatalyst": "carbon present, no metal, neither acid nor base",
    "other": "a structure matching none of the above",
    "no structure": "no SMILES mapped -- left undecided rather than guessed",
}


def build(full: bool) -> pd.DataFrame:
    name = "full" if full else "usable"
    frame = pd.read_parquet(HF / name / "records-00000-of-00001.parquet").copy()
    smiles, tier = frame["catalyst_smiles"], frame["catalyst_smiles_tier"]
    frame["structural_class"] = [classify(s, t) for s, t in zip(smiles, tier)]
    frame["structural_reason"] = [why(s, t) for s, t in zip(smiles, tier)]
    frame["regex_class"] = frame["catalyst_class"]
    # the two vocabularies name the same category differently; compare like with like
    equivalent = frame["regex_class"].replace({"ionic liquid": "organic salt / IL"})
    frame["agree"] = (equivalent == frame["structural_class"]).map({True: "yes", False: "NO"})
    for column in FLAGS:
        frame[column] = [bool(f and f.get(column)) for f in (flags(s) for s in smiles)]

    phases = [phase(c, s, t) for c, s, t in zip(frame["catalyst"], smiles, tier)]
    frame["phase"] = [p for p, _ in phases]
    frame["phase_reason"] = [w for _, w in phases]

    add_validity(frame)
    return frame


# Range and identity checks a record must survive to be worth modelling. Each is a fact about
# chemistry, not a guess: a percentage cannot exceed 100, and yield cannot exceed conversion
# because you cannot make more product than you consumed substrate. One percentage point of
# slack absorbs the rounding source papers do.
CHECKS = [
    ("yield > 100%",       lambda f: f.yield_percent > 100),
    ("conversion > 100%",  lambda f: f.conversion_percent > 100),
    ("selectivity > 100%", lambda f: f.selectivity_percent > 100),
    ("negative value",     lambda f: (f[["yield_percent", "conversion_percent",
                                         "selectivity_percent", "temperature_c",
                                         "reaction_time_min"]] < 0).any(axis=1)),
    ("yield > conversion", lambda f: f.yield_percent > f.conversion_percent + 1.0),
    ("judge dropped it",   lambda f: f.judge_drop_record.astype(bool)),
    ("citations unresolved", lambda f: ~f.citations_resolve.astype(bool)),
]


def add_validity(frame: pd.DataFrame) -> None:
    """Per-row QC flags, and one column saying whether the row survives all of them."""
    raised = [[] for _ in range(len(frame))]
    for label, test in CHECKS:
        hit = test(frame).fillna(False).to_numpy()
        for index, flagged in enumerate(hit):
            if flagged:
                raised[index].append(label)
    frame["flags_raised"] = ["; ".join(r) for r in raised]
    modelling = (frame.flags_raised == "") & (frame.phase == "homogeneous")
    frame["usable_for_modelling"] = modelling.map({True: "yes", False: "no"})


def by_catalyst(frame: pd.DataFrame) -> pd.DataFrame:
    first = frame.groupby("catalyst", dropna=False).first(numeric_only=False)
    counts = frame.groupby("catalyst", dropna=False).size().rename("records")
    table = first.join(counts).reset_index()
    table["example_doi"] = table["doi"]
    return table.sort_values("records", ascending=False)[CATALYST_COLUMNS]


def lay_out(sheet, frame, columns):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_fill, head_font = PatternFill("solid", fgColor=HEADER), Font(color="FFFFFF", bold=True)
    fills = {name: PatternFill("solid", fgColor=colour) for name, colour in FILLS.items()}

    sheet.append(list(columns))
    for cell in sheet[1]:
        cell.fill, cell.font = head_fill, head_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    where = {name: i + 1 for i, name in enumerate(columns)}
    for row in frame[list(columns)].itertuples(index=False):
        sheet.append([None if pd.isna(v) else v for v in row])
        written = sheet[sheet.max_row]
        fill = fills.get(written[where["structural_class"] - 1].value)
        if fill:
            written[where["structural_class"] - 1].fill = fill
        if written[where["agree"] - 1].value == "NO":
            written[where["agree"] - 1].font = Font(bold=True, color="A03020")

    for index, name in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = WIDTHS.get(name, 14)
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions


def method_sheet(sheet, frame):
    from openpyxl.chart import PieChart, Reference
    from openpyxl.chart.marker import DataPoint
    from openpyxl.drawing.fill import PatternFillProperties, ColorChoice
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.styles import Alignment, Font

    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 62
    sheet.column_dimensions["C"].width = 62
    sheet["A1"] = "How each class is decided"
    sheet["A1"].font = Font(bold=True, size=14)

    sheet.append([])
    sheet.append(["Class", "Regex rule, matched against the name",
                  "Structural rule, read off the SMILES"])
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)
    order = ["none", "deep eutectic", "ionic liquid", "organic salt / IL", "acid or base",
             "metal salt", "organocatalyst", "other", "no structure"]
    for name in order:
        sheet.append([name, REGEX_RULES.get(name, "no equivalent"),
                      STRUCT_RULES.get(name, "no equivalent")])
        sheet.cell(row=sheet.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        sheet.cell(row=sheet.max_row, column=3).alignment = Alignment(wrap_text=True, vertical="top")

    sheet.append([])
    sheet.append(["What the flags mean"])
    sheet.cell(row=sheet.max_row, column=1).font = Font(bold=True)
    for name, text in [
        ("is_ionic", "at least one fragment has net positive charge and another net negative"),
        ("organic_cation", "a positively charged fragment containing carbon and no metal"),
        ("has_metal", "any atom whose atomic number lies outside the non-metal set"),
        ("is_acid", "matches a Bronsted acid SMARTS"),
        ("is_base", "matches a hydroxide, alkoxide, carbonate, amine or amidine SMARTS")]:
        sheet.append([name, text])

    sheet.append([])
    sheet.append(["Limits of the structural call"])
    sheet.cell(row=sheet.max_row, column=1).font = Font(bold=True)
    for text in [
        "'Ionic liquid' means a salt melting below 100 C. Melting point is not in a SMILES, so "
        "this column says 'organic salt', a superset that includes surfactants such as CTAB.",
        "Whether a metal compound is written charge-separated or covalently is the choice of "
        "whoever entered the SMILES, not a fact about the compound.",
        "A dot in SMILES means both 'counter-ion' and 'separate substance', so a record naming "
        "two catalysts cannot be told from one salt.",
        "Of the structures deciding these labels, most were written by a language model from the "
        "name and are not independently confirmed. Check catalyst_smiles_tier."]:
        sheet.append([None, text])
        sheet.cell(row=sheet.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")

    # chart data, then two pies over it
    start = sheet.max_row + 3
    sheet.cell(row=start - 1, column=1, value="Chart data").font = Font(bold=True)
    row = start
    anchors = []
    for title, series in (("By structure (RDKit on SMILES)", frame.structural_class),
                          ("By name (regex, as shipped)", frame.regex_class)):
        sheet.cell(row=row, column=1, value=title).font = Font(bold=True)
        row += 1
        first = row
        counts = series.value_counts()
        for name, n in counts.items():
            sheet.cell(row=row, column=1, value=name)
            sheet.cell(row=row, column=2, value=int(n))
            row += 1
        anchors.append((title, first, row - 1, list(counts.index)))
        row += 1

    for index, (title, first, last, names) in enumerate(anchors):
        chart = PieChart()
        chart.title = title
        chart.height, chart.width = 9, 13
        chart.add_data(Reference(sheet, min_col=2, min_row=first, max_row=last), titles_from_data=False)
        chart.set_categories(Reference(sheet, min_col=1, min_row=first, max_row=last))
        points = []
        for i, name in enumerate(names):
            colour = CHART_COLOURS.get(name, "999999")
            points.append(DataPoint(idx=i, spPr=GraphicalProperties(solidFill=colour)))
        chart.series[0].data_points = points
        sheet.add_chart(chart, f"E{start + index * 19}")


HOW_TO_CHECK = [
    ("1. Read the two label columns as a disagreement, not an answer",
     "structural_class and regex_class are two methods, both fallible. Where agree is NO, one of "
     "them is wrong and the sheet does not know which. Work the Disagreements sheet, not the "
     "Records sheet: 194 names decide 1,018 records, and the top 50 names settle four fifths."),
    ("2. Check the provenance of the structure before trusting the structural label",
     "catalyst_smiles_tier says where the SMILES came from. `confirmed` means OPSIN derived it "
     "independently. `LLM written` means a model supplied it from the name and no library can "
     "check it -- most rows are this. A structural label built on an LLM-written structure is not "
     "an independent second opinion on a name-derived label; both read the same string."),
    ("3. Separate what the paper said from what the judge proposed",
     "yield_percent is AS EXTRACTED. corrected_yield_percent is the judge's proposal. "
     "judge_verdict describes the as-extracted record. Nothing in the plain columns has been "
     "silently corrected -- decide for yourself which view you want, then use it consistently."),
    ("4. Test the identities, because they cannot be argued with",
     "Yield cannot exceed 100%. Yield cannot exceed conversion. Nothing is negative. "
     "flags_raised lists every such violation for a row. These are the cheapest real errors to "
     "find: no chemistry knowledge is needed, only arithmetic."),
    ("5. Ask whether a flagged number is an extraction error or a source error",
     "They need opposite responses. If the paper prints 457% and we recorded 457%, the "
     "extraction is faithful and the source is the problem -- exclude the paper, do not blame the "
     "pipeline. If the paper prints '1.2 mg/mg' and we recorded 120%, the extraction misread a "
     "unit and the judge can often catch it. Read judge_critique to tell them apart."),
    ("6. Sample records and read them against the paper",
     "Everything above is mechanical and finds only mechanical errors. A record can pass every "
     "range check and still attach the wrong catalyst mass to the wrong run. Pull 20 rows at "
     "random, open the DOI, and check them by hand. That is the only measurement of fidelity "
     "there is, and it is what the adjudication set exists to do at scale."),
    ("7. Sample by stratum, not at random, once you have a rate",
     "Random sampling spends most of its effort confirming records that are already right. "
     "Sample where the graders disagree, where flags are raised, and within each route and "
     "catalyst class separately, so every part of the dataset gets a measured error rate rather "
     "than an assumed one."),
    ("8. Look at distributions, not just rows",
     "Temperature should pile up near 190-200 C where ethylene glycol refluxes. Times should sit "
     "on round numbers. A field that looks smooth where the chemistry is lumpy suggests a model "
     "inventing plausible values. Compare within a paper rather than across the corpus: pooled "
     "correlations here are near zero while within-paper ones are strong."),
]


def how_to_sheet(sheet):
    from openpyxl.styles import Alignment, Font
    sheet.column_dimensions["A"].width = 58
    sheet.column_dimensions["B"].width = 96
    sheet["A1"] = "How to check whether this dataset looks good"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([])
    for head, body in HOW_TO_CHECK:
        sheet.append([head, body])
        row = sheet[sheet.max_row]
        row[0].font = Font(bold=True)
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[sheet.max_row].height = 62


def main() -> None:
    parser = argparse.ArgumentParser(prog="export_classification")
    parser.add_argument("--full", action="store_true",
                        help="every record, including those structure cannot decide")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    from openpyxl import Workbook
    frame = build(args.full)
    catalogue = by_catalyst(frame)
    disputed = catalogue[catalogue.agree == "NO"]

    book = Workbook()
    book.remove(book.active)
    lay_out(book.create_sheet("Records"), frame, RECORD_COLUMNS)
    lay_out(book.create_sheet("By catalyst"), catalogue, CATALYST_COLUMNS)
    lay_out(book.create_sheet("Disagreements"), disputed, CATALYST_COLUMNS)
    flagged = frame[frame.flags_raised != ""]
    lay_out(book.create_sheet("Quality flags"), flagged, RECORD_COLUMNS)
    homogeneous = frame[frame.phase == "homogeneous"]
    lay_out(book.create_sheet("Homogeneous only"), homogeneous, RECORD_COLUMNS)
    how_to_sheet(book.create_sheet("How to check"))
    method_sheet(book.create_sheet("Method"), frame)

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)

    agree = (frame.agree == "yes").sum()
    print(f"{len(frame):,} records   {frame.catalyst.nunique():,} distinct catalysts")
    print(f"  the two methods agree on {agree:,} ({100*agree/len(frame):.1f}%)")
    print(f"  {len(disputed):,} catalyst names in dispute, "
          f"covering {int(disputed.records.sum()):,} records")
    print("\nstructural distribution:")
    for name, n in frame.structural_class.value_counts().items():
        print(f"  {name:20s} {n:5,}  {100*n/len(frame):5.1f}%   {CLASSES[name][:52]}")
    print("\nphase (a second axis -- it cuts across the classes above):")
    for name, n in frame.phase.value_counts().items():
        print(f"  {name:20s} {n:5,}  {100*n/len(frame):5.1f}%")
    print("\nquality flags raised:")
    for label, _ in CHECKS:
        n = int(frame.flags_raised.str.contains(label, regex=False).sum())
        if n:
            print(f"  {label:24s} {n:5,}")
    ok = (frame.usable_for_modelling == "yes").sum()
    print(f"\nhomogeneous and free of every flag: {ok:,} of {len(frame):,}")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
