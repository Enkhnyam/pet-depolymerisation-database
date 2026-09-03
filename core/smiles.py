"""Resolve the free-text chemical names in the database to SMILES, or say why not.

The extraction records catalysts and solvents as the paper writes them, which is the right thing
for provenance and the wrong thing for cheminformatics: "EG", "ethylene glycol" and "mono ethylene
glycol" are one substance under three strings, and "rGO/[TESPMI]2CoCl4" is not a substance a single
SMILES can express at all.

This maps what can be mapped and refuses the rest. Three things matter about the refusals:

  they are explicit    every row gets a *_smiles_source telling you how the value was obtained,
                       or which of the reasons below prevented it
  they are honest      a supported catalyst, a mixed oxide or a deep eutectic mixture has no single
                       SMILES; inventing one for coverage would put a false structure in a
                       chemistry database
  they are auditable   the mapping is a CSV a chemist can read and correct, not code

Mixtures are resolved component-wise and joined with '.', which is what SMILES already means by a
dot and what RDKit reads as separate fragments. "EtOH:H2O" becomes "CCO.O".

Products are not extracted at all; they follow from the route, which is itself inferred from the
solvent. Glycolysis gives BHET, methanolysis DMT, hydrolysis TPA. Records with no route get no
product, which is a fifth of the database.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from core.paths import data_path

LOOKUP = "smiles_lookup.csv"

# Route -> the monomer that route yields, keyed to the product rows of the lookup.
ROUTE_PRODUCT = {"glycolysis": "bhet", "methanolysis": "dmt", "hydrolysis": "tpa"}

# Separators that mean "and" in a solvent field: EtOH:H2O, EG/ACN, methanol and ethylene glycol.
MIXTURE = re.compile(r"\s*(?:/|:|\+|,|\band\b|\bwith\b)\s*")

# Water of crystallisation: ZnSO4·7H2O and ZnSO4 are the same catalyst for our purposes, and the
# hydrate suffix is written half a dozen ways across the corpus.
HYDRATE = re.compile(r"\s*[.\u00b7\u2027*]\s*\d*\s*h2o\b|\s*\b(?:mono|di|tri|tetra|penta|hexa|hepta)?hydrate\b", re.I)

# Ratios, concentrations and states that qualify a name without changing the substance.
NOISE = re.compile(
    r"\(.*?\)|\b\d+(?:\.\d+)?\s*(?:m|mm|wt\.?%|vol\.?%|%|v/v|w/w|mol/l)\b|"
    r"\b\d+\s*:\s*\d+\b|\baqueous\b|\bsolution\b|\bsoln\b|\banhydrous\b|\bdry\b", re.I)

UNMAPPABLE = {
    "none": "no catalyst was used",
    "n/a": "not reported",
    "na": "not reported",
    "-": "not reported",
}


def normalise(name: str) -> str:
    """Lowercase, strip qualifiers that do not change the substance."""
    text = HYDRATE.sub(" ", str(name).lower())
    text = NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,;:-")
    # a name wrapped whole in brackets, as [Zn(CH3COO)2] often is, is the same name without them
    if text.startswith("[") and text.endswith("]") and text.count("[") == 1:
        text = text[1:-1].strip()
    return text


@lru_cache(maxsize=1)
def table() -> dict:
    """(kind, normalised name) -> canonical SMILES, from the curated CSV."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    found, refused = {}, {}
    with data_path(LOOKUP).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["kind"], normalise(row["name"]))
            if not row["smiles"].strip():
                # a blank SMILES is a deliberate refusal: someone looked at this name and found
                # it does not denote one substance. That is worth distinguishing from a name
                # nobody has considered yet.
                refused[key] = row.get("note") or "ambiguous"
                continue
            mol = Chem.MolFromSmiles(row["smiles"])
            if mol is None:                     # a bad entry is dropped, never guessed at
                continue
            smiles = Chem.MolToSmiles(mol)
            if key in found and found[key] != smiles:
                # two names normalise to one key but disagree on structure, which means one of
                # them silently wins. Hydrate entries caused this: normalise() strips waters of
                # crystallisation, so "zinc acetate dihydrate" became "zinc acetate".
                raise ValueError(f"{key} maps to two structures: {found[key]} and {smiles}")
            found[key] = smiles
    return found, refused


def resolve(name, kind: str) -> tuple[str | None, str]:
    """SMILES for one field value, and how it was obtained.

    Returns (smiles, source) where source is one of: lookup, mixture, unmappable:<reason>,
    unknown, or empty when the field itself is empty.
    """
    if name is None or (isinstance(name, float) and name != name) or not str(name).strip():
        return None, "not reported"

    key = normalise(name)
    if key in UNMAPPABLE:
        return None, f"unmappable: {UNMAPPABLE[key]}"

    known, refused = table()
    if (kind, key) in refused:
        return None, f"unmappable: {refused[(kind, key)]}"
    if (kind, key) in known:
        return known[(kind, key)], "lookup"

    # Metal oxides are ionic solids rather than molecules. They are given a formula-faithful SMILES
    # so the field is usable, but tagged so anyone who considers that a misuse can filter them out.
    if kind == "catalyst" and ("oxide", key) in known:
        return known[("oxide", key)], "lookup: metal oxide, an ionic solid rather than a molecule"

    # a mixture resolves only if every component does; a half-resolved mixture is a wrong formula
    parts = [p for p in MIXTURE.split(key) if p]
    if len(parts) > 1:
        pieces = [known.get((kind, p)) for p in parts]
        if all(pieces):
            # canonicalise the joined string, not just its parts: RDKit orders the fragments of a
            # multi-component molecule itself, so "CCO.O" and "O.CCO" are the same molecule and only
            # one of them is what MolToSmiles returns.
            return canonical(".".join(pieces)), "mixture"
        return None, "unknown: mixture with an unrecognised component"

    return None, "unknown: name not in the lookup"


def canonical(smiles: str) -> str | None:
    """RDKit's canonical form, or None if it does not parse."""
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


def product_for(route: str) -> tuple[str | None, str | None]:
    """The monomer a route yields, as (name, smiles)."""
    key = ROUTE_PRODUCT.get(str(route).strip().lower())
    if not key:
        return None, None
    return key.upper(), table()[0].get(("product", key))


def substrate() -> str | None:
    """PET, as a repeat unit with attachment points rather than a discrete molecule."""
    return table()[0].get(("substrate", "pet"))


# Why a name has no SMILES. The distinction the spreadsheet colours: a name we simply have not
# added yet is worth someone's time, and a supported catalyst or a zeolite is not, because no
# single structure exists for it however long anyone looks.
NO_SINGLE_STRUCTURE = re.compile(
    r"/|@|\bon\b|wt ?%|supported|calcined|zeolite|ldh|mof|zif|mcm|sba|hap\b|amberlyst|resin|"
    r"sio2|al2o3|tio2|zro2|hbn|carbon|graphene|rgo|cnt|nanotube|nanoparticle|composite|magnetic|"
    r"powder|catalyst\s*\d|eutectic|\bdes\b\s*\d|waste|biochar|clay|dolomite|hydrotalcite|"
    r"\bnss?\b|framework|mesoporous", re.I)


def mappability(name) -> str:
    """Whether a name could in principle carry one SMILES.

    'no structure' means the string names a material, a mixture or a supported system rather than
    a substance -- 10 wt% MgO/SiO2 is a preparation, not a molecule. 'not yet mapped' means it
    probably names something definite that is simply absent from the lookup.
    """
    text = str(name).strip()
    if not text or text.lower() in UNMAPPABLE:
        return "nothing to map"
    return "no structure" if NO_SINGLE_STRUCTURE.search(text) else "not yet mapped"


# Spelling and phrasing that stop OPSIN reading an otherwise ordinary name. Nothing here changes
# which substance is meant; it only gets the string into the nomenclature OPSIN expects.
SPELLING = [
    (re.compile(r"\bsulph", re.I), "sulf"),
    (re.compile(r"\baluminium\b", re.I), "aluminum"),
    (re.compile(r"\bcaesium\b", re.I), "cesium"),
    (re.compile(r"\bglycerine\b", re.I), "glycerol"),
    (re.compile(r"\b(?:distilled|deionised|deionized|demineralized|di|ultrapure)\s+water\b", re.I), "water"),
    (re.compile(r"\bacetate\b", re.I), "acetate"),
]


def _opsin(name: str):
    """OPSIN's structure for a name, canonicalised, or None if it cannot read it."""
    try:
        from py2opsin import py2opsin
    except ImportError:
        return None
    derived = py2opsin(name)
    return canonical(derived) if derived else None


def cleaned(name: str) -> str:
    """The name with spelling and qualifiers that only obstruct nomenclature removed."""
    text = normalise(name)
    for pattern, replacement in SPELLING:
        text = pattern.sub(replacement, text)
    return text.strip()


TIERS = {
    "confirmed":   "confirmed -- OPSIN derives the same structure from the name",
    "LLM written": "written by an LLM from its own knowledge -- no library can read this name, "
                   "so nothing independent checks it",
    "unclear":     "unclear -- not mapped yet, but the name probably has a structure",
    "no catalyst": "no catalyst -- the paper reports an uncatalysed reaction. This is a finding, "
                   "not a gap: the empty SMILES is the correct value.",
    "impossible":  "impossible -- the name denotes a material or a preparation, which has no "
                   "single structure",
    "not reported": "not reported -- the paper does not say",
}


def tier_of(name, kind: str, library: str | None) -> tuple[str | None, str]:
    """The SMILES for a name and which of the four tiers it falls in.

    `library` is OPSIN's structure for the same name, or None if OPSIN could not read it. The
    tiers say how much independent support a value has, which is the thing a reader needs and the
    thing a single "source" string was failing to convey:

      confirmed   either OPSIN produced it, or a hand entry agrees with what OPSIN produced.
                  Two sources, or one authoritative one.
      LLM written a language model wrote the structure from its own knowledge, and no library can
                  read the name to check it. Abbreviations, formulas and trade names all land here.
                  It may well be right; nothing independent confirms it.
      unclear     no structure yet. Worth someone's time.
      impossible  the string names a material, a preparation or nothing at all.
    """
    curated, source = resolve(name, kind)
    if source.startswith("not reported"):
        return None, "not reported"
    if source.startswith("unmappable"):
        # "no catalyst" is an observation about the experiment, not a failure to map a name. It
        # was being counted with the zeolites and the supported catalysts, which made 781 records
        # of real chemistry look like a hole in the data.
        reason = source.split(": ", 1)[-1]
        return None, "no catalyst" if "no catalyst" in reason else "not reported"
    if curated and library:
        return curated, "confirmed"          # agreeing or differing only by bonding convention
    if library and not curated:
        return library, "confirmed"
    if curated:
        return curated, "LLM written"
    return None, ("impossible" if mappability(name) == "no structure" else "unclear")
