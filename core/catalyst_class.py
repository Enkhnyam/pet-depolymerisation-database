"""Classify a catalyst from its structure rather than from the spelling of its name.

The shipped `catalyst_class` comes from a regex cascade over the free-text catalyst name
(checks/database/chemistry.py). That cascade is unreliable in both directions: its ionic-liquid
rule fires on any name containing square brackets, so `[Zn(CH3COO)2·2H2O]` is called an ionic
liquid, while `EMIM Cl` -- the same cation without brackets -- is not. Its metal rule carries no
alkali metals, so Na2CO3 and KOMe fall through to `other`, and it spells `sulfuric` where the
corpus writes `sulphuric`.

Now that catalysts resolve to SMILES, the same question can be asked of the structure. Three
signals carry the whole classification:

  fragments        SMILES separates unbonded parts with '.', so Chem.GetMolFrags splits a salt
                   into its ions
  formal charge    the net charge of each fragment says which is the cation
  substructure     SMARTS patterns find acid and base groups

What this is good for, and what it is not:

  it is a better instrument than the regex -- it does not read spelling, so it is immune to
  sulphuric/sulfuric, to bracket conventions and to abbreviation

  it is not an oracle. "Ionic liquid" means a salt melting below 100 C, and melting point is not
  in a SMILES string; the strongest claim available here is `organic salt`, a superset that
  includes surfactants like CTAB. Whether a metal compound is written charge-separated
  (`CC(=O)[O-].[Zn+2]`) or covalently (`O=[Ti]=O`) is a choice made by whoever entered the string,
  not a fact about the compound. And the dot means both "counter-ion" and "separate substance", so
  a record naming two catalysts is indistinguishable from one salt.

  it decides nothing without a structure. Roughly a third of records have no mapped SMILES and are
  returned as `no structure` rather than guessed at.

The rules are an ordered cascade and the order is a judgement. `acid or base` is tested before
`metal salt` on purpose: NaOH contains a metal but is used as a base, and testing metal first sent
all 467 NaOH and KOH records to `metal salt`.
"""
from __future__ import annotations

from functools import lru_cache

# Everything that is not a metal. Any other atomic number is one.
NONMETAL = {1, 2, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 18,
            32, 33, 34, 35, 36, 51, 52, 53, 54, 85, 86}

ACID_SMARTS = [
    ("carboxylic acid", "[CX3](=O)[OX2H1]"),
    ("sulfonic or sulfuric", "[SX4](=O)(=O)[OX2H1]"),
    ("phosphoric", "[PX4](=O)[OX2H1]"),
    ("hydrohalic", "[Cl,Br,I;H1]"),
    ("nitric", "[OX2H1][NX3](=O)=O"),
]

BASE_SMARTS = [
    ("hydroxide", "[OX1H1-]"),
    ("alkoxide", "[OX1-][CX4]"),
    ("carbonate", "[O-]C(=O)[O-]"),
    ("bicarbonate", "[O-]C(=O)[OX2H1]"),
    ("amine", "[NX3;H2,H1,H0;!$(N-[C,S,P]=[O,S]);!$([N+])]"),
    ("amidine or guanidine", "[NX2]=[CX3]"),
]

CLASSES = {
    "none": "the paper reports an uncatalysed run -- an observation, not a gap",
    "organic salt / IL": "an organic cation with a counter-anion. A superset of ionic liquids: "
                         "melting point is not in a SMILES, so surfactants land here too",
    "acid or base": "carries a Bronsted acid group, or a hydroxide, alkoxide, carbonate, "
                    "amine or amidine",
    "metal salt": "contains a metal atom. Covers salts, oxides and coordination complexes alike",
    "organocatalyst": "carbon-bearing, no metal, neither acidic nor basic",
    "other": "a structure that is none of the above",
    "no structure": "no SMILES was mapped, so structure decides nothing",
}

FLAGS = ["is_ionic", "organic_cation", "has_metal", "is_acid", "is_base"]


@lru_cache(maxsize=1)
def _patterns():
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    return ([Chem.MolFromSmarts(s) for _, s in ACID_SMARTS],
            [Chem.MolFromSmarts(s) for _, s in BASE_SMARTS])


def flags(smiles) -> dict | None:
    """The structural facts a class is derived from, or None if there is no readable structure."""
    from rdkit import Chem
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    acids, bases = _patterns()

    found = {"has_metal": False, "organic_cation": False, "cation": False, "anion": False,
             "is_acid": any(mol.HasSubstructMatch(p) for p in acids),
             "is_base": any(mol.HasSubstructMatch(p) for p in bases),
             "has_carbon": any(a.GetAtomicNum() == 6 for a in mol.GetAtoms())}
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() not in NONMETAL:
            found["has_metal"] = True
    for fragment in Chem.GetMolFrags(mol, asMols=True):
        charge = Chem.GetFormalCharge(fragment)
        carbon = any(a.GetAtomicNum() == 6 for a in fragment.GetAtoms())
        metal = any(a.GetAtomicNum() not in NONMETAL for a in fragment.GetAtoms())
        if charge > 0:
            found["cation"] = True
            # a metal-containing cation is not an organic one, however much carbon hangs off it
            if carbon and not metal:
                found["organic_cation"] = True
        elif charge < 0:
            found["anion"] = True
    found["is_ionic"] = found["cation"] and found["anion"]
    return found


def classify(smiles, tier: str = "") -> str:
    """The class, from the structure. `tier` supplies the one answer structure cannot give."""
    if tier == "no catalyst":
        return "none"
    found = flags(smiles)
    if found is None:
        return "no structure"
    if found["is_ionic"] and found["organic_cation"]:
        return "organic salt / IL"
    if found["is_acid"] or found["is_base"]:
        return "acid or base"          # before metal: NaOH is a base that happens to hold sodium
    if found["has_metal"]:
        return "metal salt"
    if found["has_carbon"]:
        return "organocatalyst"
    return "other"


def why(smiles, tier: str = "") -> str:
    """A short reason for the label, so a reader can check the call without reading SMILES."""
    if tier == "no catalyst":
        return "the paper reports no catalyst"
    found = flags(smiles)
    if found is None:
        return "no structure mapped"
    if found["is_ionic"] and found["organic_cation"]:
        return "organic cation with a counter-anion"
    if found["is_acid"]:
        return "carries a Bronsted acid group"
    if found["is_base"]:
        return "carries a hydroxide, alkoxide, carbonate or amine"
    if found["has_metal"]:
        return "contains a metal atom"
    if found["has_carbon"]:
        return "organic, no metal, neither acid nor base"
    return "no rule matched"


# --------------------------------------------------------------------------------------------
# Phase: a second axis, orthogonal to the classes above.
#
# The classes say what a catalyst IS. Phase says whether it DISSOLVES. They cut across each
# other: zinc acetate and ZnO are both metal salts, and only the first is homogeneous. Filtering
# to homogeneous catalysis therefore removes part of a class rather than a whole one.
#
# It matters for modelling rather than for tidiness. A heterogeneous rate depends on surface
# area, particle size, calcination temperature and dispersion, none of which the schema records.
# Two papers reporting "ZnO" at the same mass and temperature can differ tenfold for reasons no
# column here can express, so those rows are unpredictable from our features by construction.
# A homogeneous rate depends on catalyst identity, amount, temperature and time -- exactly what
# the schema does hold.
#
# Solubility is no more present in a SMILES string than melting point is, so this is a reading of
# the name plus the one structural fact we curated deliberately: metal oxides carry their own
# `kind` in the lookup. A heterogeneous catalyst whose name does not advertise itself will pass
# through as homogeneous. Treat `homogeneous` as "nothing says otherwise", not as a measurement.
# --------------------------------------------------------------------------------------------

import re

# Named solid materials, and forms that only exist as a solid phase.
SOLID = re.compile(
    r"zeolite|\bldh\b|layered double hydroxide|hydrotalcite|\bmof\b|\bzif|amberlyst|\bresin\b|"
    r"dowex|nafion|dolomite|biochar|molecular sieve|hydroxyapatite|\bhap-|perovskite|spinel|"
    r"montmorillonite|\bmmt\b|silicalite|\bnano|magnetic|@|calcined|supported|\bwt\.? ?%|"
    r"immobili[sz]ed|\bheterogeneous", re.I)

PHASES = {
    "homogeneous": "dissolves into the reaction liquid -- one phase, and the schema's fields "
                   "(identity, amount, temperature, time) are the ones that set the rate",
    "heterogeneous": "a solid suspended in the liquid. Rate depends on surface area, particle "
                     "size and calcination, none of which this schema records",
    "uncatalysed": "no catalyst was used. Single-phase by default, and a valid baseline",
    "unknown": "no structure and no name evidence either way",
}


@lru_cache(maxsize=1)
def _oxides():
    """Metal oxides, which carry their own kind in the SMILES lookup."""
    import csv
    from core.paths import data_path
    from core.smiles import LOOKUP, normalise
    names, smiles = set(), set()
    with data_path(LOOKUP).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "oxide":
                names.add(normalise(row["name"]))
                if row["smiles"].strip():
                    smiles.add(row["smiles"].strip())
    return names, smiles


def phase(name, smiles=None, tier: str = "") -> tuple[str, str]:
    """Whether the catalyst dissolves, and why we say so."""
    from core.smiles import normalise
    if tier == "no catalyst":
        return "uncatalysed", "the paper reports no catalyst"
    text = str(name or "")
    if not text.strip():
        return "unknown", "no catalyst named"
    oxide_names, oxide_smiles = _oxides()
    if normalise(text) in oxide_names or (isinstance(smiles, str) and smiles in oxide_smiles):
        return "heterogeneous", "a metal oxide -- an insoluble ionic solid"
    if SOLID.search(text):
        return "heterogeneous", "named as a solid material, support, or nano/calcined form"
    return "homogeneous", "nothing in the name or structure marks it as a separate solid phase"
