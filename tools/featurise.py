"""Turn the catalyst and solvent SMILES into numbers a model can use.

A SMILES is a string. `CC(=O)[O-].CC(=O)[O-].[Zn+2]` tells a gradient-boosted tree nothing,
and encoding it as a category is worse than nothing: 78% of the structures in this corpus
appear in exactly one paper, so a categorical code is a near-unique label for the study rather
than a description of the chemistry. Descriptors fix that -- a zinc carboxylate the model has
never seen still looks like the zinc carboxylates it has.

Three groups of features come out, and they answer different questions:

  whole-molecule    what the catalyst is as written: weight, lipophilicity, polar surface,
                    ring count, charge. Computed on the full SMILES including counter-ions.

  fragment          SMILES separates unbonded parts with '.', so a salt arrives as its ions.
                    Describing the largest cation and the largest anion separately is what
                    distinguishes [Bmim]Br from [Bmim][OAc], which differ only in the anion
                    and behave differently. Whole-molecule descriptors average that away.

  fingerprint       a folded Morgan (ECFP4) bit vector: which substructures are present.
                    Off by default. With 180 distinct catalysts over ~3,300 rows a 2048-bit
                    vector invites the model to memorise; --bits 128 is a defensible ceiling.

Uncatalysed runs are not missing data. They are an experimental result -- the paper ran the
reaction with no catalyst -- so they get `has_catalyst = 0` and zeros throughout rather than
NaN, which a tree would otherwise treat as "unknown" instead of "none".

Solvent is featurised the same way, resolved through the curated lookup in
artifacts/data/smiles_lookup.csv. It matters more than the catalyst for the three routes.

    featurise.py                              artifacts/release/features.parquet and .csv
    featurise.py --bits 128                   add a 128-bit Morgan fingerprint
    featurise.py --with-masses                merge the mass columns back from the mass run
    featurise.py --input <xlsx> --sheet <s>
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.paths import ARTIFACTS

# The release itself, not a side-export of it. The default used to be a filtered xlsx holding
# 3,353 of the release's 3,951 rows and 525 of its 561 papers, so features.csv described a
# dataset nobody ships and no check validates.
DEFAULT_IN = ARTIFACTS / "release" / "pet_homogeneous_release.csv"
DEFAULT_SHEET = "Filtered Dataset"
DEFAULT_SKIP = 3
MASS_SOURCE = ARTIFACTS / "release" / "mass_luna_1shot_flat.csv"
OUT = ARTIFACTS / "release" / "features"

# Descriptors chosen because each says something a chemist would recognise, and because every
# one is defined for a bare ion. Anything needing a valid valence model on [Zn+2] is excluded.
DESCRIPTORS = {
    "mw": "MolWt",
    "logp": "MolLogP",
    "tpsa": "TPSA",
    "hbd": "NumHDonors",
    "hba": "NumHAcceptors",
    "rotatable": "NumRotatableBonds",
    "heavy_atoms": "HeavyAtomCount",
    "rings": "RingCount",
    "aromatic_rings": "NumAromaticRings",
    "fraction_sp3": "FractionCSP3",
    "heteroatoms": "NumHeteroatoms",
    "valence_electrons": "NumValenceElectrons",
}

NONMETAL = {1, 2, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 18,
            32, 33, 34, 35, 36, 51, 52, 53, 54, 85, 86}


def _descriptor_functions():
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    source = {}
    for name in DESCRIPTORS.values():
        for module in (Descriptors, Lipinski, Crippen, rdMolDescriptors):
            if hasattr(module, name):
                source[name] = getattr(module, name)
                break
    missing = set(DESCRIPTORS.values()) - set(source)
    if missing:
        raise RuntimeError(f"RDKit is missing descriptors: {sorted(missing)}")
    return source


def describe(mol, prefix, functions):
    """The whole-molecule block for one RDKit mol."""
    from rdkit import Chem
    out = {}
    for key, name in DESCRIPTORS.items():
        try:
            out[f"{prefix}_{key}"] = float(functions[name](mol))
        except Exception:
            out[f"{prefix}_{key}"] = np.nan
    out[f"{prefix}_charge"] = float(Chem.GetFormalCharge(mol))
    out[f"{prefix}_n_fragments"] = float(len(Chem.GetMolFrags(mol)))

    metals = [a for a in mol.GetAtoms() if a.GetAtomicNum() not in NONMETAL]
    out[f"{prefix}_has_metal"] = float(bool(metals))
    out[f"{prefix}_n_metal_atoms"] = float(len(metals))
    # the heaviest metal present -- a stand-in for which metal it is that a tree can split on
    out[f"{prefix}_metal_z"] = float(max((a.GetAtomicNum() for a in metals), default=0))
    return out


def fragments(mol, prefix, functions):
    """The largest cation and the largest anion, described separately.

    This is what separates [Bmim]Br from [Bmim][OAc]. Neutral single-fragment molecules put
    the whole molecule in the cation slot and leave the anion slot at zero, which keeps the
    columns defined for every row.
    """
    from rdkit import Chem
    parts = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    cation = anion = None
    for part in parts:
        charge = Chem.GetFormalCharge(part)
        size = part.GetNumHeavyAtoms()
        if charge > 0 and (cation is None or size > cation.GetNumHeavyAtoms()):
            cation = part
        elif charge < 0 and (anion is None or size > anion.GetNumHeavyAtoms()):
            anion = part
    if cation is None and anion is None and parts:
        cation = max(parts, key=lambda p: p.GetNumHeavyAtoms())

    out = {}
    for slot, part in (("cation", cation), ("anion", anion)):
        if part is None:
            out.update({f"{prefix}_{slot}_{key}": 0.0 for key in DESCRIPTORS})
            out[f"{prefix}_{slot}_charge"] = 0.0
            out[f"{prefix}_{slot}_has_metal"] = 0.0
            out[f"{prefix}_{slot}_present"] = 0.0
            continue
        block = describe(part, f"{prefix}_{slot}", functions)
        out.update({k: v for k, v in block.items()
                    if not k.endswith(("_n_fragments", "_n_metal_atoms", "_metal_z"))})
        out[f"{prefix}_{slot}_present"] = 1.0
    return out


def morgan(mol, prefix, bits):
    from rdkit.Chem import rdFingerprintGenerator
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=bits)
    vector = generator.GetFingerprintAsNumPy(mol)
    return {f"{prefix}_fp{i}": float(v) for i, v in enumerate(vector)}


def featurise_smiles(values, prefix, bits):
    """One feature row per distinct SMILES, then broadcast. RDKit is slow; the corpus is not."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    functions = _descriptor_functions()

    distinct = sorted({v for v in values.dropna().unique() if str(v).strip()})
    table, unreadable = {}, []
    for smiles in distinct:
        mol = Chem.MolFromSmiles(smiles, sanitize=True)
        if mol is None:                       # bare metal ions can fail full sanitisation
            mol = Chem.MolFromSmiles(smiles, sanitize=False)
            if mol is not None:
                try:
                    Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_FINDRADICALS |
                                     Chem.SanitizeFlags.SANITIZE_SETAROMATICITY |
                                     Chem.SanitizeFlags.SANITIZE_ADJUSTHS)
                except Exception:
                    pass
        if mol is None:
            unreadable.append(smiles)
            continue
        row = describe(mol, prefix, functions)
        row.update(fragments(mol, prefix, functions))
        if bits:
            row.update(morgan(mol, prefix, bits))
        table[smiles] = row

    columns = sorted({k for row in table.values() for k in row})
    frame = pd.DataFrame([table.get(v, {}) for v in values], columns=columns, index=values.index)
    # A blank SMILES means "no catalyst was used", which is a result, not a gap. Zero, not NaN.
    present = values.notna() & values.astype(str).str.strip().ne("")
    frame[f"{prefix}_present"] = present.astype(float)
    frame.loc[~present, columns] = 0.0
    return frame, unreadable


def solvent_smiles(names):
    """Resolve solvent names through the curated lookup."""
    from core.smiles import resolve
    cache = {}
    out = []
    for name in names:
        key = str(name).strip() if pd.notna(name) else ""
        if key not in cache:
            cache[key] = resolve(key, "solvent")[0] if key else None
        out.append(cache[key])
    return pd.Series(out, index=names.index)


def main() -> None:
    parser = argparse.ArgumentParser(prog="featurise")
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--sheet", default=DEFAULT_SHEET)
    parser.add_argument("--skiprows", type=int, default=DEFAULT_SKIP)
    parser.add_argument("--bits", type=int, default=0,
                        help="Morgan fingerprint length; 0 disables it")
    parser.add_argument("--with-masses", action="store_true",
                        help="merge catalyst/PET/solvent masses back from the mass run")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    frame = (pd.read_excel(args.input, sheet_name=args.sheet, skiprows=args.skiprows)
             if args.input.suffix == ".xlsx" else pd.read_csv(args.input))
    print(f"{args.input.name}: {len(frame):,} rows, {frame.doi.nunique()} papers")

    have_masses = {"catalyst_amount_g", "PET_amount_g"} <= set(frame.columns)
    if args.with_masses and have_masses:
        print("  masses already present; nothing to merge")
    elif args.with_masses:
        masses = pd.read_csv(MASS_SOURCE, usecols=["record_id", "catalyst_amount_g",
                                                   "PET_amount_g", "solvent_amount_g",
                                                   "pressure_atm"])
        before = frame.columns.size
        frame = frame.merge(masses, on="record_id", how="left")
        found = frame.catalyst_amount_g.notna().sum()
        print(f"  merged masses back: {found:,} rows have a catalyst mass "
              f"({frame.columns.size - before} columns added)")
    if have_masses or args.with_masses:
        frame["loading"] = frame.catalyst_amount_g / frame.PET_amount_g
        frame["solvent_ratio"] = frame.solvent_amount_g / frame.PET_amount_g

    catalyst, bad_catalyst = featurise_smiles(frame.catalyst_smiles, "cat", args.bits)
    print(f"  catalyst: {frame.catalyst_smiles.nunique()} distinct structures -> "
          f"{catalyst.shape[1]} columns"
          + (f"; {len(bad_catalyst)} unreadable" if bad_catalyst else ""))

    # The release already carries a resolved solvent_smiles, built with more than the name to go
    # on. Re-deriving from the name alone silently lost 112 rows -- 63 of them ordinary
    # single-component solvents like chlorobenzene. Keep what the release resolved; only fill the
    # gaps by name.
    derived = solvent_smiles(frame.solvent)
    if "solvent_smiles" in frame:
        frame["solvent_smiles"] = frame.solvent_smiles.where(frame.solvent_smiles.notna(), derived)
    else:
        frame["solvent_smiles"] = derived
    resolved = frame.solvent_smiles.notna().sum()
    solvent, bad_solvent = featurise_smiles(frame.solvent_smiles, "sol", args.bits)
    print(f"  solvent:  {resolved:,}/{len(frame):,} rows resolved to a structure "
          f"({frame.solvent_smiles.nunique()} distinct) -> {solvent.shape[1]} columns"
          + (f"; {len(bad_solvent)} unreadable" if bad_solvent else ""))

    out = pd.concat([frame, catalyst, solvent], axis=1)
    out = out.loc[:, ~out.columns.duplicated()]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out.with_suffix(".parquet"), index=False)
    out.to_csv(args.out.with_suffix(".csv"), index=False)
    print(f"\n{len(out):,} rows x {out.shape[1]} columns")
    print(f"  wrote {args.out.with_suffix('.parquet').relative_to(ROOT)}")
    print(f"  wrote {args.out.with_suffix('.csv').relative_to(ROOT)}")

    target = out.yield_percent.notna()
    print(f"\nmodelling view: {target.sum():,} rows carry a yield, "
          f"{out[target].doi.nunique()} papers")
    print("  split by doi, never at random -- a random split leaks and reports R2 ~ +0.44 "
          "where a grouped split gives ~ -0.27")


if __name__ == "__main__":
    main()
