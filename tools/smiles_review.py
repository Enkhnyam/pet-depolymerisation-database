"""Export the SMILES mapping for outside review, and take corrections back.

Two files, for the two different questions a reviewer asks.

  audit     every entry currently in the lookup, with the formula and molecular weight RDKit
            derives from the SMILES. A wrong structure almost always shows up as a wrong formula,
            so a chemist or a second model can check the table without parsing SMILES by eye:
            "zinc acetate" had better read C4H6O4Zn.

  gaps      every name that did not resolve, with how many records it affects and a paper to look
            it up in, and an empty smiles column. Sorted by records affected, so effort goes where
            it buys the most.

A filled-in gaps file comes back through --ingest, which validates every proposed SMILES in RDKit
and refuses the file if any fails, rather than writing a broken entry into the lookup.

    smiles_review.py                     write both files
    smiles_review.py --ingest <file>     merge reviewed rows into the lookup
"""
import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.paths import ARTIFACTS, data_path
from core.smiles import LOOKUP, normalise, resolve

FLAT = ARTIFACTS / "release" / "mass_luna_1shot_flat.csv"
AUDIT = ARTIFACTS / "release" / "smiles_audit.csv"
GAPS = ARTIFACTS / "release" / "smiles_gaps.csv"


def describe(smiles: str) -> tuple[str, float]:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors, rdMolDescriptors
    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "DOES NOT PARSE", float("nan")
    return rdMolDescriptors.CalcMolFormula(mol), round(Descriptors.MolWt(mol), 2)


def write_audit() -> int:
    rows = []
    with data_path(LOOKUP).open(encoding="utf-8") as handle:
        for entry in csv.DictReader(handle):
            formula, weight = describe(entry["smiles"])
            rows.append({"kind": entry["kind"], "name": entry["name"],
                         "smiles": entry["smiles"], "formula": formula,
                         "molecular_weight": weight, "note": entry.get("note", ""),
                         "reviewer_verdict": "", "reviewer_comment": ""})
    pd.DataFrame(rows).to_csv(AUDIT, index=False)
    return len(rows)


def write_gaps() -> int:
    frame = pd.read_csv(FLAT)
    rows = []
    for column, kind in (("catalyst", "catalyst"), ("solvent", "solvent")):
        unresolved = {}
        for value, doi in zip(frame[column], frame["doi"]):
            smiles, source = resolve(value, kind)
            if smiles is not None or source.startswith(("not reported", "unmappable")):
                continue
            key = str(value).strip()
            entry = unresolved.setdefault(key, {"records": 0, "doi": doi, "reason": source})
            entry["records"] += 1
        for name, entry in unresolved.items():
            rows.append({"kind": kind, "name_as_written": name,
                         "normalised": normalise(name), "records_affected": entry["records"],
                         "example_doi": entry["doi"], "why_unresolved": entry["reason"],
                         "smiles": "", "reviewer_comment": ""})

    table = pd.DataFrame(rows).sort_values(["records_affected"], ascending=False)
    table.to_csv(GAPS, index=False)
    return len(table)


def ingest(path: Path) -> None:
    """Merge a filled-in gaps file, after checking every proposed structure parses."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    proposed = [row for row in csv.DictReader(path.open(encoding="utf-8"))
                if (row.get("smiles") or "").strip()]
    bad = [row for row in proposed if Chem.MolFromSmiles(row["smiles"].strip()) is None]
    if bad:
        print(f"{len(bad)} proposed SMILES do not parse; nothing was merged:")
        for row in bad[:10]:
            print(f"   {row.get('name_as_written', '?'):40s} {row['smiles']}")
        raise SystemExit(1)

    existing = data_path(LOOKUP).read_text(encoding="utf-8").rstrip("\n")
    known = {(r["kind"], normalise(r["name"]))
             for r in csv.DictReader(data_path(LOOKUP).open(encoding="utf-8"))}
    added = []
    for row in proposed:
        key = (row["kind"], normalise(row["name_as_written"]))
        if key in known:
            continue
        canonical = Chem.MolToSmiles(Chem.MolFromSmiles(row["smiles"].strip()))
        note = (row.get("reviewer_comment") or "reviewed").replace(",", ";")
        name = row["name_as_written"].strip().lower()
        quoted = f'"{name}"' if "," in name else name
        added.append(f'{row["kind"]},{quoted},{canonical},{note}')
        known.add(key)

    if not added:
        print("nothing new to add")
        return
    data_path(LOOKUP).write_text(existing + "\n" + "\n".join(added) + "\n", encoding="utf-8")
    print(f"added {len(added)} entries to {LOOKUP}")


def cross_check() -> None:
    """Compare the lookup against OPSIN, which derives structures from IUPAC nomenclature.

    OPSIN is an independent authority and needs no network. It cannot read abbreviations, formulas
    or trade names, so it covers only part of the table -- but where it does, a disagreement is
    worth looking at. Differences in bonding convention (ionic vs covalent for a metal salt) are
    not errors and show up as the same molecular formula.
    """
    from py2opsin import py2opsin
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdMolDescriptors
    RDLogger.DisableLog("rdApp.*")

    def canonical(text):
        mol = Chem.MolFromSmiles(text) if text else None
        return (Chem.MolToSmiles(mol), rdMolDescriptors.CalcMolFormula(mol)) if mol else (None, None)

    agree, differ, unparsed = 0, [], 0
    with data_path(LOOKUP).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row["smiles"].strip():
                continue
            derived = py2opsin(row["name"])
            if not derived:
                unparsed += 1
                continue
            mine, mine_formula = canonical(row["smiles"])
            theirs, their_formula = canonical(derived)
            if mine == theirs:
                agree += 1
            else:
                differ.append((row["name"], mine_formula, their_formula, row["smiles"], derived))

    print(f"OPSIN parsed {agree + len(differ)} of the lookup names ({unparsed} it could not read)")
    print(f"  identical structure      {agree}")
    print(f"  different structure      {len(differ)}")
    same = [d for d in differ if d[1] == d[2]]
    print(f"    of those, same formula {len(same)}  (bonding convention, not a different compound)")
    for name, mine, theirs, _, _ in differ:
        flag = "convention" if mine == theirs else "DIFFERENT COMPOUND"
        print(f"      {name[:34]:36s} {mine or '?':12s} vs {theirs or '?':12s} {flag}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="smiles_review")
    parser.add_argument("--cross-check", action="store_true",
                        help="compare the lookup against OPSIN")
    parser.add_argument("--ingest", type=Path)
    args = parser.parse_args()

    if args.cross_check:
        cross_check()
        return
    if args.ingest:
        ingest(args.ingest)
        return

    entries, gaps = write_audit(), write_gaps()
    frame = pd.read_csv(GAPS)
    reach = frame.groupby("kind").records_affected.agg(["size", "sum"])
    print(f"{entries} lookup entries  -> {AUDIT.relative_to(ROOT)}")
    print(f"{gaps} unresolved names  -> {GAPS.relative_to(ROOT)}")
    print()
    print(reach.rename(columns={"size": "distinct names", "sum": "records"}).to_string())
    print(f"\ntop of the gaps file, by records affected:")
    for row in frame.head(8).itertuples():
        print(f"   {row.records_affected:4d}  {row.kind:8s} {row.name_as_written[:46]}")


if __name__ == "__main__":
    main()
