"""Does the catalyst dissolve in the reaction liquid?

The release is homogeneous catalysis: one phase, catalyst in solution. That is a chemical
judgement, not something a SMILES string carries -- solubility is not in a structure any more
than melting point is. The previous rule (core.catalyst_class.phase) treated "homogeneous" as
"nothing in the name says otherwise", which let Fe3O4 and Co3O4 through because they were filed
in the lookup under kind='catalyst' rather than kind='oxide'.

This module decides properly, in four passes, and every row records which pass decided it and
why. A reader who disagrees with a call can find it and argue with it.

  1. curated     compounds named often enough in this corpus to be worth deciding by hand.
                 Ordered first so a hand decision always beats a pattern.
  2. solid       forms and materials that only exist as a suspended solid: oxides, zeolites,
                 layered double hydroxides, MOFs, supported and nano and calcined preparations,
                 ion-exchange resins, carbons, metal plates. Named oxides are enumerated; any
                 remaining bare metal-oxide formula is caught by shape, because an enumeration
                 only knows the oxides somebody thought of.
  3. soluble     compound classes that dissolve at reaction temperature: alkali hydroxides,
                 carbonates and alkoxides, metal carboxylates, metal halides, mineral acids,
                 amidine and guanidine organocatalysts, ionic liquids, quaternary ammonium
                 and phosphonium salts, deep eutectic mixtures, metal alkoxides.
  4. structure   the last resort, from the SMILES: a metal oxide anion means a solid, an
                 organic cation with a counter-ion means a salt that melts or dissolves.

Anything none of the four decides is returned as `unknown`, not as `homogeneous`. For a release
an honest gap is worth more than a guess, and the guess would always fall the same way.

Edge calls, made once and recorded here rather than argued twice:

  Ca(OH)2, Mg(OH)2   sparingly soluble at best. Called solid: in glycolysis they are slurries.
  Sb2O3              dissolves slowly in hot glycol and is used industrially as a solution in
                     EG. Called solid when named alone, soluble when the name says "in EG".
  metal stearates    long-chain carboxylates, insoluble in water, soluble in hot glycol, which
                     is where they are used here. Called soluble.
  Na2CO3, K2CO3      soluble in water, sparingly in glycol; run as solutions. Called soluble.
  enzymes            excluded as a separate modality rather than called either way.
"""
from __future__ import annotations

import re
from functools import lru_cache

PHASES = {
    "homogeneous": "dissolves in the reaction liquid",
    "heterogeneous": "a solid suspended in the liquid",
    "uncatalysed": "no catalyst was used",
    "biocatalytic": "an enzyme -- a different modality, not chemical catalysis",
    "unknown": "the name and structure decide nothing",
}

# --- 1. hand decisions ------------------------------------------------------------------------
# Every name here appears in the corpus. The comment is the reason a chemist would give.
CURATED = {
    # --- solids, named individually because a pattern would be too blunt
    "cao": ("heterogeneous", "quicklime, an insoluble ionic solid"),
    "mgo": ("heterogeneous", "magnesia, insoluble"),
    "zno": ("heterogeneous", "zinc oxide, insoluble"),
    "sb2o3": ("heterogeneous", "antimony trioxide; dissolves only slowly in hot glycol"),
    "fe3o4": ("heterogeneous", "magnetite, an insoluble spinel"),
    "co3o4": ("heterogeneous", "cobalt oxide, insoluble"),
    "tio2": ("heterogeneous", "titania, insoluble"),
    "ca(oh)2": ("heterogeneous", "slaked lime, sparingly soluble -- run as a slurry"),
    "mg(oh)2": ("heterogeneous", "insoluble hydroxide"),
    "zn(oh)2": ("heterogeneous", "insoluble hydroxide"),
    "calcined dolomite": ("heterogeneous", "a calcined mineral"),
    "waste battery powder": ("heterogeneous", "a recovered solid powder"),
    "zinc plates": ("heterogeneous", "bulk metal, not dissolved"),
    "basic carbocatalyst": ("heterogeneous", "a carbon material"),
    "titanium (iv)-phosphate": ("heterogeneous", "insoluble metal phosphate"),
    "natnt": ("heterogeneous", "sodium titanate nanotubes"),
    "tnt": ("heterogeneous", "titanate nanotubes"),
    "sodium metasilicate": ("homogeneous", "water-soluble silicate"),

    # --- soluble, named because the pattern rules would miss or mis-fire
    "na2co3": ("homogeneous", "soluble carbonate"),
    "k2co3": ("homogeneous", "soluble carbonate"),
    "nahco3": ("homogeneous", "soluble bicarbonate"),
    "sodium carbonate": ("homogeneous", "soluble carbonate"),
    "potassium carbonate": ("homogeneous", "soluble carbonate"),
    "sodium bicarbonate": ("homogeneous", "soluble bicarbonate"),
    "sodium oxalate": ("homogeneous", "soluble oxalate"),
    "nacl": ("homogeneous", "soluble halide"),
    "ammonia": ("homogeneous", "dissolved gas"),
    "tbd": ("homogeneous", "triazabicyclodecene, a soluble guanidine base"),
    "dbu": ("homogeneous", "amidine base, miscible"),
    "dbn": ("homogeneous", "amidine base, miscible"),
    "dmap": ("homogeneous", "soluble amine catalyst"),
    "mdea": ("homogeneous", "methyldiethanolamine, miscible"),
    "tpa": ("homogeneous", "terephthalic acid, dissolves in the reaction medium"),
    "sodium titanium glycolate": ("homogeneous", "glycolate complex formed in solution"),
    "ti(och2ch2o)3na2": ("homogeneous", "sodium titanium glycolate, formed in solution"),
    "siw11zn": ("homogeneous", "a polyoxometalate, soluble in polar media"),
    "cationic surfactant": ("homogeneous", "surfactants dissolve above the cmc"),
    "3bu6dpb": ("homogeneous", "a phosphonium/borate ionic liquid"),
    "tmam": ("homogeneous", "a quaternary ammonium salt"),
    "tbhdpb": ("homogeneous", "tetrabutyl/hexadecyl phosphonium bromide, an ionic liquid"),
    "tomab": ("homogeneous", "trioctylmethylammonium bromide, a phase-transfer salt"),
    "kf:eg 1:6": ("homogeneous", "a potassium fluoride / glycol deep eutectic mixture"),
    "pil-zn2+": ("heterogeneous", "a poly(ionic liquid) support carrying zinc"),
    "b-cn-1.2": ("heterogeneous", "boron-doped carbon nitride, a solid"),
    "zn-bdc": ("heterogeneous", "a zinc terephthalate framework"),
    "co sscs": ("heterogeneous", "single-site catalyst on a support"),
    "rsa": ("unknown", "a paper-internal label; no compound can be assigned"),
    "bpe": ("unknown", "a paper-internal label; no compound can be assigned"),
    "tn-10": ("unknown", "a paper-internal label; no compound can be assigned"),
    "5w/s1": ("heterogeneous", "a supported tungsten preparation"),
    "mn1": ("unknown", "a paper-internal label; no compound can be assigned"),
    "1mn/zn": ("heterogeneous", "a supported manganese-on-zinc preparation"),
    "[(ch3)2sn(ococh3)2]": ("homogeneous", "dimethyltin diacetate, soluble"),
    "[ch]3[po4]": ("homogeneous", "choline phosphate, an ionic liquid"),
    "mtbn": ("homogeneous", "a methylated amidine base"),
    "nmp": ("homogeneous", "N-methylpyrrolidone, miscible"),
    "lmgk": ("unknown", "a paper-internal label; no compound can be assigned"),
    "bla": ("unknown", "a paper-internal label; no compound can be assigned"),
    "ch/zn (2:1)": ("homogeneous", "a choline/zinc deep eutectic mixture"),
    "chcl-zn(oac)2": ("homogeneous", "a choline chloride / zinc acetate eutectic"),
    "sb2o3 solution in ethylene glycol": ("homogeneous",
                                          "antimony trioxide predissolved in glycol"),
    "sb2o3 + eg": ("homogeneous", "antimony trioxide predissolved in glycol"),
}

# An oxide the paper says it dissolved first is a solution, whatever the oxide rule would say.
PREDISSOLVED = re.compile(r"solution in|dissolved in|\bin (eg|ethylene glycol|water)\b", re.I)

# --- 2. solid forms ---------------------------------------------------------------------------
SOLID = re.compile(
    r"zeolit|\bzsm\b|\bbeta\b|\bfau\b|\bmcm\b|\bsba\b|\bmcf\b|silicalite|"
    r"\bldh\b|layered double hydroxide|hydrotalcite|\bht\d|dolomite|"
    r"\bmof\b|\bzif\b|metal[- ]organic framework|\bdmc\b|"
    r"amberlyst|amberlite|\bresin\b|dowex|nafion|\bmn-\d|purolite|"
    r"biochar|\bchar\b|carbocatalyst|carbon nitride|\bc3n4\b|graphit|graphene|\bcnt\b|"
    # Activated carbon, which this corpus writes only as the bare abbreviation. A plain \bac\b
    # is NOT safe here: "Ac" is also the acetate abbreviation, and \bac\b matches the Ac in
    # Zn(Ac)2, Mn(Ac)2 and [VEIm]Ac because the bracket before it is a word boundary -- 29
    # perfectly soluble acetates, which is how this was caught. Activated carbon is written
    # either as the whole cell or as an added component, so those are the two shapes matched.
    r"activated carbon|active carbon|charcoal|^\s*ac\s*$|\+\s*ac\b|"
    r"hydroxyapatite|\bhap[- ]|montmorillonit|\bmmt\b|bentonite|\bclay\b|kaolin|"
    r"perovskite|spinel|molecular sieve|silica gel|\bsio2\b|\bal2o3\b|\bzro2\b|\bceo2\b|"
    r"\bmno2\b|\bcuo\b|\bnio\b|\bmgo\b|\bcao\b|\bzno\b|\bfe2o3\b|\bfe3o4\b|\bco3o4\b|"
    r"\bnano|nanoparticle|nanosheet|\bnss\b|nanotube|nanorod|quantum dot|"
    r"magnetic|\bcalcined\b|supported|immobili[sz]ed|\bheterogeneous\b|"
    r"\bwt\.? ?%|\bpowder\b|\bplate|\bpellet|\bfoam\b|\bbead|\bfilm\b|"
    r"@|\bhbn\b|\bmxene\b|\bldhs\b|"
    # a slash means a support only when a real support follows it; ZnCl2/EG is a solution
    r"/\s*(sio2|al2o3|tio2|zno|mgo|ceo2|zro2|y2o3|mcf|mcm|sba|zsm|hbn|ac\b|c\b|carbon|zeolite|silica|alumina|clay)|"
    # layered double hydroxides and mixed-oxide precursors are written as element runs
    r"^(ni)?(zn|mg|cu|co)al-?\d|^mg-?al|^zn-?al|^ni-?zn|"
    r"\bcn-?\d|c3n4|carbon nitride|-bdc\b|\bbdc\b|\bmil-\d|\buio-\d|"
    r"fe2o4|ferrite|\bcfo\b|\bcat-\d{3}",
    re.I)

# A bare metal-oxide formula, whatever the metal. SOLID above enumerates oxides by hand --
# zno, cuo, fe3o4, mno2 and a dozen more -- and an enumeration only knows the oxides somebody
# thought of. Cu2O, SnO, CdO, Mn3O4, Sb2O5 and La2O3 were not on it, and each fell through to
# SOLUBLE, where the bare element symbols that are there to catch salt names ("cu" for copper
# acetate, "sn" for tin octanoate) matched inside the formula and called a solid oxide a
# solution. One of them reached a review sample from a paper titled "Catalysis investigation of
# PET depolymerization under metal oxides", which is as clear a signal as a rule ever gets.
#
# So the shape is recognised instead of the members: one element symbol, an optional count, an
# O, an optional count, and nothing else. Anchored, so it reads a whole catalyst cell and never
# a fragment of one -- "Sb2O3 in EG" is not a bare formula and keeps its curated homogeneous
# call, which is decided two passes earlier anyway.
BARE_OXIDE = re.compile(r"^[A-Z][a-z]?\d*O\d*$")

ENZYME = re.compile(r"enzym|lipase|cutinase|petase|hydrolase|esterase|\bfast-?petase\b|"
                    r"leaf.?branch|\blcc\b|protein", re.I)

# --- 3. soluble classes -----------------------------------------------------------------------
SOLUBLE = re.compile(
    r"acetate|\boac\b|\back?\d?\b|ch3coo|coocH3|"
    r"stearate|oleate|laurate|palmitate|octanoate|neodecanoate|ethylhexanoate|isononanoate|"
    r"benzoate|citrate|lactate|glycolate|oxalate|formate|"
    r"chloride|bromide|iodide|fluoride|\bcl\d?\b|\bbr\b|sulfate|sulphate|nitrate|"
    r"hydroxide|\bnaoh\b|\bkoh\b|\bliOH\b|\btbaoh\b|"
    r"carbonate|bicarbonate|methoxide|ethoxide|butoxide|isopropoxide|alkoxide|"
    r"\bnaome\b|\bkome\b|\bnaoet\b|\bnaoch3\b|\bkotbu\b|\btbuok\b|"
    r"sulfuric|sulphuric|hydrochloric|nitric|phosphoric|\bh2so4\b|\bhcl\b|\bh3po4\b|"
    r"\bhno3\b|\btsoh\b|\bptsa\b|toluenesulfonic|methanesulfonic|triflic|"
    r"imidazolium|pyridinium|pyrrolidinium|phosphonium|ammonium|imidazol|"
    r"\bbmim\b|\bemim\b|\bomim\b|\bhmim\b|\bamim\b|\bmmim\b|\bbzmim\b|\[c\dc\dim\]|"
    r"ionic liquid|\bil\b|deep eutectic|\bdes\b|choline|\bchcl\b|urea|thiourea|"
    r"\bctab\b|\bctac\b|\btbab\b|\btbai\b|\btbac\b|surfactant|\btomab\b|\bhdtmac\b|"
    r"\btbd\b|\bdbu\b|\bdbn\b|\bdmap\b|\btmg\b|guanidin|amidin|\bamine\b|"
    r"\bdabco\b|\bmtbd\b|\bmtbn\b|\bdbn\b|\bnmi\b|\bdmi\b|imidazole|pyridine|"
    r"proline|prolinate|\bmea\b|\bdea\b|\btea\b|morpholine|piperidine|"
    r"titanate|\btbt\b|\btip\b|isopropylate|titanium.*butoxide|butyl titanate|"
    r"triisopropoxide|tetraisopropoxide|tetrabutoxide|"
    r"\bzn\(|\bmn\(|\bco\(|\bcu\(|\bfe\(|\bmg\(|\bpb\(|\bni\(|\bsn\(|\bti\(|"
    # a metal symbol fused to its anion, which carries no word boundary: ZnAc2, ZnCl2, FeCl3
    r"\b(zn|mn|co|cu|fe|ni|mg|ca|pb|sn|ti|sb|na|k|li|al|ce|la|zr|in|bi|cd|cr)"
    r"\d?h?\d?(ac(?=\d|\b)|oac|st(?=\d|\b)|cl|br|f(?=\d|\b)|so4|so3|no3|co3|c2o4|po4|oh|ome|oet|o(?=\d|\b))"
    r"\d*(·|\.|\s|$|\d)|"
    # the same salts written anion-first, and formula spellings of alkoxides
    r"^(ch3o|meo|eto|tbuo|c2h5o)(na|k|li)\b|(na|k|li)(ome|oet|otbu|och3)\b|"
    # bracketed ionic-liquid notation, including cations the list above does not name
    r"mim\]|mim\b|\[[a-z0-9]{2,8}\]\[|\]\[[a-z0-9]|pyrr\]|\bpy\]|"
    r"\bw\d+o\d+|zn\dw\d|polyoxometal|\bpom\b|heteropoly|"
    r"acid$|^acid|base$",
    re.I)

DES_PAIR = re.compile(r"\s*[:/+]\s*|\bwith\b|\band\b")


@lru_cache(maxsize=4096)
def classify(name: str, smiles: str = "", tier: str = "") -> tuple[str, str, str]:
    """Return (phase, reason, which pass decided it)."""
    if tier == "no catalyst":
        return "uncatalysed", "the paper reports no catalyst", "tier"
    text = str(name or "").strip()
    if not text or text.lower() in {"none", "nan", "no catalyst", "-", "(none)"}:
        return "uncatalysed", "no catalyst named", "name"

    key = text.lower()
    if key in CURATED:
        phase, reason = CURATED[key]
        return phase, reason, "curated"

    if PREDISSOLVED.search(text):
        return "homogeneous", "the paper states it was dissolved before use", "predissolved"
    if ENZYME.search(text):
        return "biocatalytic", "an enzyme, excluded as a different modality", "enzyme"
    if SOLID.search(text):
        return "heterogeneous", "named as a solid material, support or nano/calcined form", "solid"
    if BARE_OXIDE.match(text):
        return "heterogeneous", "a bare metal-oxide formula, insoluble as named", "oxide"
    if SOLUBLE.search(text):
        return "homogeneous", "a compound class that dissolves at reaction temperature", "soluble"

    phase, reason = _from_structure(smiles)
    return phase, reason, "structure" if phase != "unknown" else "none"


def _from_structure(smiles) -> tuple[str, str]:
    """The last resort. An oxide anion is a solid; an organic salt dissolves or melts."""
    if not isinstance(smiles, str) or not smiles.strip():
        return "unknown", "no name rule matched and no structure to fall back on"
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return "unknown", "no name rule matched and the structure does not parse"

    has_oxide = any(a.GetSymbol() == "O" and a.GetFormalCharge() == -2 for a in mol.GetAtoms())
    if has_oxide:
        return "heterogeneous", "an oxide anion -- an insoluble ionic solid"

    fragments = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    organic_cation = any(
        Chem.GetFormalCharge(f) > 0
        and any(a.GetAtomicNum() == 6 for a in f.GetAtoms())
        and f.GetNumHeavyAtoms() > 3
        for f in fragments)
    if organic_cation and len(fragments) > 1:
        return "homogeneous", "an organic cation with a counter-ion -- a salt that dissolves"
    return "unknown", "no name rule matched and the structure decides nothing"


def decisions(names, smiles=None, tiers=None):
    """A table of every distinct decision, for review. One row per name."""
    import pandas as pd
    smiles = smiles if smiles is not None else [""] * len(names)
    tiers = tiers if tiers is not None else [""] * len(names)
    rows = []
    for name, structure, tier in zip(names, smiles, tiers):
        phase, reason, pass_ = classify(str(name), str(structure or ""), str(tier or ""))
        rows.append({"catalyst": name, "phase": phase, "why": reason, "decided_by": pass_})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # The oxide rule, and the three things it must not break. Written because the enumeration it
    # replaces was wrong for six oxides for as long as it existed and nothing noticed.
    call = lambda name: classify(name, "", "")[0]
    for solid in ("Cu2O", "SnO", "CdO", "Mn3O4", "Sb2O5", "La2O3", "Nb2O5", "ZnO", "TiO2"):
        assert call(solid) == "heterogeneous", solid
    for soluble in ("Zn(OAc)2", "[Bmim][Br]", "sodium hydroxide", "aluminium triisopropoxide",
                    "ChCl-ZnCl2", "FeCl3"):
        assert call(soluble) == "homogeneous", soluble
    # a curated hand call and a predissolved statement both outrank the shape
    assert classify("Sb2O3", "", "")[2] == "curated"
    assert call("Sb2O3 in EG") == "homogeneous"
    # the shape is a whole cell, never a fragment of one
    assert not BARE_OXIDE.match("Cu2O supported on SiO2")
    # "Ac" is acetate as often as it is activated carbon; only the whole cell and an added
    # component are the carbon. This cost 29 soluble acetates once.
    assert call("AC") == "heterogeneous"
    assert call("Zn(OAc)2 (1%) + AC (1%)") == "heterogeneous"
    for acetate in ("Zn(Ac)2", "Mn(Ac)2.2H2O", "[VEIm]Ac", "NaOAc", "Zn(OAc)2"):
        assert call(acetate) == "homogeneous", acetate
    print("solubility self-check ok")
