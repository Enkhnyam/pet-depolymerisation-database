"""Every number the manuscript quotes about the released dataset, with its derivation.

The existing macros in artifacts/paper_numbers.tex describe the *mass run* -- 5,563 records
from 1,026 papers processed. That is the right population for the extraction and audit results,
because the judge read all of it. It is the wrong population for anything the manuscript says
about what is being released, which is the homogeneous subset: 3,951 rows in
artifacts/release/pet_homogeneous_release.csv, frozen at v1.0.

Quoting the mass-run numbers under the word "homogeneous" is how the current abstract came to
say 2,128 experiments from 447 articles, which describes neither file. So the two populations
get two prefixes and never share a macro:

    Database*   the mass run          5,563 records / 1,026 papers processed
    Release*    the frozen release    3,951 records /   561 papers

Every entry below records where it comes from and how it is computed. A number whose derivation
cannot be written in one line usually should not be in an abstract.

    release_numbers.py            print the table of macro, value, source and derivation
    release_numbers.py --tex      emit the \\newcommand block for artifacts/paper_numbers.tex
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.paths import ARTIFACTS

RELEASE = ARTIFACTS / "release" / "pet_homogeneous_release.csv"
SOURCE = ARTIFACTS / "huggingface" / "full" / "records-00000-of-00001.parquet"
VERSION_FILE = ARTIFACTS / "release" / "VERSION"
CURATED = ARTIFACTS / "data" / "curated_table_final.json"

MODEL_FIELDS = ["yield_percent", "temperature_c", "reaction_time_min",
                "catalyst_amount_g", "PET_amount_g"]


def load():
    frame = pd.read_csv(RELEASE, low_memory=False)
    frame["doi_l"] = frame.doi.astype(str).str.lower()
    return frame


def phases():
    """The phase call for every record in the source, so exclusions are counted not quoted."""
    from core.solubility import classify
    source = pd.read_parquet(SOURCE)
    return pd.Series([classify(str(c), str(s or ""), str(t or ""))[0] for c, s, t in
                      zip(source.catalyst, source.catalyst_smiles, source.catalyst_smiles_tier)])


def curated_overlap(frame):
    """Papers in both the hand-curated answer key and the release, and the rows they cover."""
    curated = pd.json_normalize(json.loads(CURATED.read_text()))
    dois = set(curated.doi.astype(str).str.lower())
    shared = dois & set(frame.doi_l)
    rows = frame[frame.doi_l.isin(shared)]
    experiments = sum(len(x) for x in curated.extracted_experiments)
    return curated, dois, shared, rows, experiments


def compute():
    """Return {macro: (value, source, derivation)}. One row per number the paper may quote."""
    d = load()
    excluded = phases()
    version, digest = VERSION_FILE.read_text().split("\n")[:2]
    curated, curated_dois, shared, overlap, curated_experiments = curated_overlap(d)

    src = "pet_homogeneous_release.csv"
    modelable = d[MODEL_FIELDS].notna().all(axis=1)
    no_catalyst = d.catalyst.astype(str).str.lower().isin(["none", "no catalyst", "nan"])
    featurisable = d.catalyst_smiles.notna() | no_catalyst
    judged = d.audit.notna()
    flagged = d.quality_flags.notna() & d.quality_flags.astype(str).ne("")

    def n(x):
        return f"{int(x):,}"

    def pct(x, of):
        return f"{100 * x / of:.1f}"

    out = {
        "ReleaseVersion": (version, "artifacts/release/VERSION", "written by build_release.py"),
        "ReleaseHash": (digest, "artifacts/release/VERSION",
                        "sha256 of the released CSV, first 12 hex digits"),

        # --- size
        "ReleaseRecords": (n(len(d)), src, "row count"),
        "ReleasePapers": (n(d.doi.nunique()), src, "distinct doi"),
        "ReleaseHomogeneousRecords": (n(d.phase.eq("homogeneous").sum()), src,
                                      "rows with phase == homogeneous"),
        "ReleaseBaselines": (n(d.phase.eq("uncatalysed").sum()), src,
                             "rows with phase == uncatalysed, kept as controls"),
        "ReleaseStructures": (n(d.catalyst_smiles.nunique()), src,
                              "distinct catalyst_smiles; multi-component rows carry none"),
        "ReleaseCatalystNames": (n(d[d.phase.eq("homogeneous")].catalyst.nunique()), src,
                                 "distinct catalyst strings among catalysed rows"),
        "ReleaseSolvents": (n(d.solvent.nunique()), src, "distinct solvent strings"),

        # --- what the solubility filter removed, recomputed rather than read off a log
        "ReleaseExcludedSolid": (n(excluded.eq("heterogeneous").sum()),
                                 "huggingface/full + core.solubility",
                                 "source records whose catalyst is classed heterogeneous"),
        "ReleaseExcludedUnknown": (n(excluded.eq("unknown").sum()),
                                   "huggingface/full + core.solubility",
                                   "source records whose catalyst resolves to no compound"),

        # --- completeness, the numbers that decide what the data supports
        "ReleaseWithYield": (n(d.yield_percent.notna().sum()), src, "yield_percent not null"),
        "ReleaseYieldShare": (pct(d.yield_percent.notna().sum(), len(d)), src,
                              "yield_percent not null, as a share of all rows"),
        "ReleaseModelable": (n(modelable.sum()), src,
                             "rows with yield, temperature, time and both masses"),
        "ReleaseModelablePapers": (n(d[modelable].doi.nunique()), src,
                                   "distinct doi among those rows"),
        "ReleaseFeaturisable": (n(featurisable.sum()), src,
                                "rows with a catalyst structure, or honestly none"),

        # --- how much rests on an unverified structure
        "ReleaseConfirmed": (n(d.structure_source.eq("confirmed").sum()), src,
                             "structure_source == confirmed, i.e. OPSIN derived it from the name"),
        "ReleaseConfirmedShare": (pct(d.structure_source.eq("confirmed").sum(), len(d)), src,
                                  "as a share of all rows"),
        "ReleaseLLMWritten": (n(d.structure_source.eq("LLM written").sum()), src,
                              "structure_source == LLM written, nothing independent checked it"),
        "ReleaseLLMWrittenShare": (pct(d.structure_source.eq("LLM written").sum(), len(d)), src,
                                   "as a share of all rows"),

        # --- the audit, recomputed on this population rather than the mass run
        "ReleaseAccepted": (n(d.audit.eq("accepted").sum()), src, "audit == accepted"),
        "ReleaseFlagged": (n(d.audit.eq("flagged").sum()), src, "audit == flagged"),
        "ReleasePassRate": (pct(d.audit.eq("accepted").sum(), judged.sum()), src,
                            "accepted over judged, not over all rows"),

        # --- routes
        "ReleaseGlycolysis": (n(d.route.eq("glycolysis").sum()), src, "route == glycolysis"),
        "ReleaseHydrolysis": (n(d.route.eq("hydrolysis").sum()), src, "route == hydrolysis"),
        "ReleaseMethanolysis": (n(d.route.eq("methanolysis").sum()), src, "route == methanolysis"),
        "ReleaseNoRoute": (n(d.route.isna().sum() + d.route.eq("other/unclear").sum()), src,
                           "solvent matches none of the three rules, so no product is fixed"),

        # --- what is flagged rather than removed
        "ReleaseQualityFlagged": (n(flagged.sum()), src,
                                  "rows failing a range or identity check"),
        "ReleaseDuplicates": (n(d.duplicate_of.notna().sum()), src,
                              "rows repeating an earlier experiment in the same paper"),
        "ReleaseMultiComponent": (n((~d.single_component.astype(bool)).sum()), src,
                                  "catalyst cell names more than one substance"),

        # --- how much of the release the answer key actually covers
        "CuratedOverlapPapers": (n(len(shared)),
                                 f"{src} + curated_table_final.json",
                                 "curated dois that also appear in the release"),
        "CuratedOverlapRecords": (n(len(overlap)), f"{src} + curated_table_final.json",
                                  "release rows from a curated paper"),
        "CuratedOverlapShare": (pct(len(overlap), len(d)), f"{src} + curated_table_final.json",
                                "those rows as a share of the release"),
        "CuratedOverlapGlycolysis": (n(overlap.route.eq("glycolysis").sum()),
                                     f"{src} + curated_table_final.json",
                                     "of the covered rows, how many are glycolysis"),
    }
    return out


# =============================================================================================
# THE TWENTY CHECKS A CHEMIST WOULD RUN BEFORE BELIEVING THE SPREADSHEET
#
# Merged here from what used to be checks/release/quality.py. It read a different file --
# pet_homogeneous.xlsx, a readable export a day older than the release -- so the referee checks
# and the paper's macros described two datasets that disagreed by a thousand rows. One script
# reading one file is the only way that cannot happen again.
#
#   MECHANICAL   duplicates, ranges, units: wrong on its face, arithmetic proves it.
#   IDENTITY     catalyst and solvent columns: two names for one substance, or the reverse.
#   INFERENCE    the columns nobody extracted -- route, product, phase, class.
#   SEMANTIC     what the numbers mean, and whether the relationships physics requires appear.
# =============================================================================================

NUMERIC = ["temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
           "solvent_amount_g", "yield_percent", "conversion_percent", "selectivity_percent"]
OUTCOMES = ["yield_percent", "conversion_percent", "selectivity_percent"]
# The columns that make a row a distinct experiment. Provenance and verdict columns are
# excluded on purpose: two rows differing only in `audit` are still the same experiment.
EXPERIMENT = ["doi", "catalyst", "solvent", "route", *NUMERIC]

SHOW = 6
FAILURES = []


def report(number, name, count, total, note="", rows=None, columns=None):
    """One line per check, plus the evidence when there is any."""
    share = f"{100 * count / total:5.1f}%" if total else "     "
    mark = "\033[31m✗\033[0m" if count else "\033[32m✓\033[0m"
    print(f"\n{mark} {number:>2}. {name}")
    print(f"      {count:,} of {total:,} ({share.strip()}){'  — ' + note if note else ''}")
    if count:
        FAILURES.append((number, name, count))
    if rows is not None and len(rows):
        frame = rows[columns] if columns else rows
        text = frame.head(SHOW).to_string(index=False, max_colwidth=34)
        print("\n".join("        " + line for line in text.splitlines()))
        if len(rows) > SHOW:
            print(f"        … {len(rows) - SHOW:,} more")


# ---------------------------------------------------------------------------------------------
# MECHANICAL
# ---------------------------------------------------------------------------------------------

def mechanical(d):
    print("\n\033[1mMECHANICAL — wrong on its face\033[0m")

    # 1. The same experiment written out more than once. An extractor reading a table row by row
    #    will emit one record per row; if it also reads the same table from the abstract, or the
    #    chunker overlaps, the row appears twice. Duplicates do not just waste space: they
    #    reweight every mean, every median and every model fit toward whatever was duplicated.
    dup = d.duplicated(subset=EXPERIMENT, keep=False)
    report(1, "duplicate experiments (same paper, conditions and outcome)",
           int(d.duplicated(subset=EXPERIMENT).sum()), len(d),
           f"{int(dup.sum()):,} rows are involved in a duplicate group",
           d[dup].sort_values(EXPERIMENT[:3]),
           ["doi", "catalyst", "temperature_c", "reaction_time_min", "yield_percent"])

    # 2. A row with no outcome at all cannot be a training example and cannot be a datapoint in
    #    any plot of what conditions achieve. It is a record that an experiment happened.
    empty = d[OUTCOMES].isna().all(axis=1)
    report(2, "rows carrying no outcome (yield, conversion and selectivity all blank)",
           int(empty.sum()), len(d), "unusable as a supervised example")

    # 3. The subset that could actually train a structure-conditions-to-yield model: a yield,
    #    a temperature, a time, and both masses so that loading is derivable.
    modelable = d[["yield_percent", "temperature_c", "reaction_time_min",
                   "catalyst_amount_g", "PET_amount_g"]].notna().all(axis=1)
    report(3, "rows NOT complete enough to model (need yield, T, t, and both masses)",
           int((~modelable).sum()), len(d),
           f"the modelable core is {int(modelable.sum()):,} rows from "
           f"{d[modelable].doi.nunique()} papers")

    # 4. Percentages above 100 and yields above conversion. Arithmetic, not opinion.
    over = pd.Series(False, index=d.index)
    for column in OUTCOMES:
        over |= d[column] > 100
    both = d[["yield_percent", "conversion_percent"]].dropna()
    identity = int((both.yield_percent > both.conversion_percent + 1.0).sum())
    report(4, "percentages above 100%", int(over.sum()), len(d),
           f"and {identity} rows where yield exceeds conversion",
           d[over], ["doi", "catalyst", "temperature_c", "yield_percent", "conversion_percent"])

    # 5. Masses that are not laboratory masses. A kilogram of PET in a glycolysis paper is
    #    possible; two tonnes is a units error, and it sits in the same column as 0.5 g.
    absurd = ((d.PET_amount_g > 1000) | (d.solvent_amount_g > 5000) |
              (d.catalyst_amount_g > 100))
    report(5, "masses outside any plausible bench or pilot scale",
           int(absurd.sum()), len(d), "grams, kilograms and wt% share one column",
           d[absurd].sort_values("PET_amount_g", ascending=False),
           ["doi", "catalyst", "catalyst_amount_g", "PET_amount_g", "solvent_amount_g"])

    # 6. Catalyst loading is the one derived quantity every paper reports and this schema does
    #    not hold. Derive it, and its distribution says whether the two masses are commensurable.
    ratio = _loading(d)
    heavy = ratio[ratio > 1]
    report(6, "rows where catalyst outweighs PET (loading > 100 wt%)",
           len(heavy), len(ratio),
           f"median loading {ratio.median():.1%}; the tail reaches {ratio.max():.0f}× — "
           "consistent with wt% or mol% values entered as grams",
           d.loc[heavy.index], ["doi", "catalyst", "catalyst_amount_g", "PET_amount_g"])

    # 7. Temperatures at which PET is not being solvolysed but pyrolysed. Above ~350 C the
    #    polymer decomposes; a "depolymerisation in water at 800 C" is a different experiment
    #    that the corpus filter let through.
    hot = d.temperature_c > 350
    report(7, "temperatures above 350 °C (pyrolysis, not solvolysis)",
           int(hot.sum()), int(d.temperature_c.notna().sum()),
           "these papers are about carbon materials, not depolymerisation",
           d[hot].sort_values("temperature_c", ascending=False),
           ["doi", "catalyst", "solvent", "temperature_c", "yield_percent"])

    # 8. Zero or absent time, and runs longer than a week.
    odd = (d.reaction_time_min <= 0) | (d.reaction_time_min > 10080)
    report(8, "reaction times of zero, or longer than a week",
           int(odd.sum()), int(d.reaction_time_min.notna().sum()), "",
           d[odd].sort_values("reaction_time_min"),
           ["doi", "catalyst", "reaction_time_min", "temperature_c"])


def _loading(d):
    frame = d.dropna(subset=["catalyst_amount_g", "PET_amount_g"])
    frame = frame[frame.PET_amount_g > 0]
    return frame.catalyst_amount_g / frame.PET_amount_g


# ---------------------------------------------------------------------------------------------
# IDENTITY
# ---------------------------------------------------------------------------------------------

HYDRATE = re.compile(r"H2O|hydrate|·\s*\d|\.\s*\d\s*H2O", re.I)
MULTI = re.compile(r"\s/\s|\s\+\s|,\s|\sand\s")
LOADING_IN_NAME = re.compile(r"\d\s*(%|wt|mol|M\b|mM\b)")


def identity(d):
    print("\n\033[1mIDENTITY — what substance is this row about\033[0m")

    # 9. The headline "distinct catalysts" counts spellings, not substances. Every synonym is a
    #    separate row of the Catalysts sheet with its own median yield, computed over a slice
    #    of the evidence for that compound.
    named, structural = d.catalyst.nunique(), d.catalyst_smiles.nunique()
    grouped = (d.dropna(subset=["catalyst_smiles"]).groupby("catalyst_smiles")
               .catalyst.nunique().sort_values(ascending=False))
    worst = grouped[grouped > 1]
    report(9, "catalyst names that are a synonym of another name",
           int(named - structural), named,
           f"{named} spellings collapse to {structural} structures; "
           f"{len(worst)} structures carry more than one name")
    for smiles in worst.head(3).index:
        names = sorted(d[d.catalyst_smiles == smiles].catalyst.unique())
        print(f"        {len(names):2d} names → {smiles[:36]:36s} {names[:5]}")

    # 10. The reverse, and much worse: a structure that is not the compound the name says.
    #     Tested rather than guessed at -- each rule names a ligand a reader can see in the
    #     name and a fragment that must therefore appear in the SMILES. A model asked for a
    #     structure it does not know returns the field's commonest catalyst instead of nothing,
    #     so this error is silent and always in the same direction.
    wrong = _ligand_mismatch(d)
    report(10, "structures that contradict the name they are attached to",
           int(wrong.rows.sum()), len(d),
           "each is a ligand named in the catalyst string and absent from its SMILES",
           wrong.evidence, ["catalyst", "expected", "catalyst_smiles"])

    # 11. A name that says hydrate against a structure that does not. The mass in
    #     catalyst_amount_g is the hydrate's; the molecular weight implied by the SMILES is the
    #     anhydrous one, so moles computed from the pair are wrong by up to a third.
    hydrate = d.catalyst.astype(str).str.contains(HYDRATE, na=False)
    lost = hydrate & ~d.catalyst_smiles.astype(str).str.contains(r"\.O\b|O\.O", regex=True, na=False)
    report(11, "hydrates whose SMILES carries no water",
           int(lost.sum()), int(hydrate.sum()),
           "mass is the hydrate's, MW is the anhydrous form's",
           d[lost][["catalyst", "catalyst_smiles"]].drop_duplicates())

    # 12. One cell holding two substances. The schema has one catalyst field and one amount, so
    #     a co-catalyst system loses which mass belongs to which, and the joined SMILES makes a
    #     bicarbonate and a sulfuric acid look like one salt.
    multi = d.catalyst.astype(str).str.contains(MULTI, na=False)
    report(12, "rows naming more than one catalyst in one cell",
           int(multi.sum()), len(d), "one amount column for two substances",
           d[multi][["catalyst", "catalyst_smiles"]].drop_duplicates())

    # 13. Conditions leaking into the identity column.
    leaked = d.catalyst.astype(str).str.contains(LOADING_IN_NAME, na=False)
    report(13, "catalyst names carrying a concentration or loading",
           int(leaked.sum()), len(d), "the same catalyst at two loadings is two 'catalysts'",
           d[leaked][["catalyst", "catalyst_amount_g", "PET_amount_g"]].drop_duplicates())

    # 14. Structures nothing independent checked. OPSIN can read a systematic name; it cannot
    #     read an abbreviation or a trade name, so the abbreviations -- which is most of the
    #     corpus -- rest entirely on a language model's recall.
    llm = d.structure_source == "LLM written"
    report(14, "structures supplied by a language model and never verified",
           int(llm.sum()), len(d),
           "OPSIN confirmed the rest; the review file "
           "artifacts/release/smiles_audit.csv has an empty reviewer_verdict column")

    # 15. Solvent spellings, same argument as catalysts and never normalised at all.
    solvents = d.solvent.dropna()
    families = {"water": r"^(water|h2o|distilled water|deionis?zed water|di water)$",
                "ethylene glycol": r"^(eg|ethylene glycol|ethyleneglycol|mono ?ethylene glycol|meg)$",
                "methanol": r"^(methanol|meoh|ch3oh)$"}
    collapsed = 0
    print()
    for label, pattern in families.items():
        member = solvents[solvents.astype(str).str.strip().str.lower().str.match(pattern)]
        collapsed += member.nunique() - 1
        print(f"        {label:18s} {member.nunique()} spellings, {len(member):,} rows: "
              f"{sorted(member.unique())}")
    report(15, "solvent spellings collapsible in just three families",
           collapsed, int(solvents.nunique()), "the column is free text end to end")


# Each rule is a ligand a reader can see in the name and the substructure it must therefore put
# in the SMILES. Matched with RDKit rather than by string, so a rule cannot be defeated by the
# order the atoms happen to be written in. Conservative on purpose: a rule fires only on an
# unambiguous spelling, so a miss is silent but a hit is a contradiction anyone can check by eye.
LIGANDS = [
    ("hydroxide",    r"\(OH\)\d|hydroxide",                        "[OX1H1-]"),
    ("methoxide",    r"\(OMe\)\d|\(OCH3\)\d|methoxide|methylate", "[CH3][OX1-]"),
    # the lookbehinds keep tert-butoxide out: it is a butoxide with no four-carbon chain
    ("n-butoxide",   r"OC4H9|(?<!tert.)(?<!t.)butoxide|butyl titanate|butylate",
                                                                   "[CH2][CH2][CH2][CH3]"),
    ("isopropoxide", r"OiPr|isopropoxide|isopropylate",             "[CH3][CH]([CH3])[OX2,OX1-]"),
    ("sulfate",      r"SO4|sulph?ate",                              "[SX4](=[OX1])(=[OX1])"),
    ("carbonate",    r"CO3\b|carbonate",                            "[CX3](=[OX1])([OX1-,OX2H1])[OX1-,OX2H1]"),
    # acetate is written both as an anion and as a covalent ester in this lookup; either counts
    ("acetate",      r"OAc|CH3COO|OOCCH3|acetate",                  "[CH3][CX3](=[OX1])[OX1-,OX2]"),
    ("chloride",     r"Cl\d|chloride",                              "[Cl]"),
    ("nitrate",      r"NO3\b|nitrate",                              "[NX3](=[OX1])[OX1-]"),
]


def _ligand_mismatch(d):
    """Rows whose catalyst name names a ligand that its SMILES does not contain."""
    from types import SimpleNamespace

    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    patterns = [(label, re.compile(spelling, re.I), Chem.MolFromSmarts(smarts))
                for label, spelling, smarts in LIGANDS]

    pairs = d[["catalyst", "catalyst_smiles"]].dropna().drop_duplicates()
    found = []
    for name, smiles in pairs.itertuples(index=False):
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            continue
        for label, spelling, pattern in patterns:
            if spelling.search(str(name)) and not mol.HasSubstructMatch(pattern):
                found.append({"catalyst": name, "expected": label, "catalyst_smiles": smiles})
                break
    evidence = pd.DataFrame(found)
    if evidence.empty:
        return SimpleNamespace(rows=pd.Series(False, index=d.index), evidence=evidence)
    return SimpleNamespace(rows=d.catalyst.isin(evidence.catalyst), evidence=evidence)


def _head(name):
    """The substance a name is about, ignoring hydration, oxidation state and punctuation."""
    text = re.sub(r"[\[\](){}·.\s'\"-]", "", str(name)).lower()
    text = re.sub(r"\d*h2o$|hydrate$|dihydrate$|tetrahydrate$", "", text)
    text = re.sub(r"[（）ivx]+$", "", text)
    for canon, pattern in [("zn-acetate", r"^(zn|zinc)(ii)?(oac|ac|ch3coo|ococh3|oococh3|acetate)"),
                           ("mn-acetate", r"^(mn|manganese)(ii)?(oac|ac|ch3coo|acetate)"),
                           ("na-methoxide", r"^(ch3ona|meona|naoch3|naome|sodiummethoxide)"),
                           ("ti-isopropoxide", r"^(tip|tioipr4|titaniumisopropoxide|titaniumtetraisoprop)"),
                           ("ti-butoxide", r"^(tbt|tioc4h9|butyltitanate|nbutyltitanate|tetrabutyl)")]:
        if re.match(pattern, text):
            return canon
    return text


# ---------------------------------------------------------------------------------------------
# INFERENCE — the columns nobody extracted
# ---------------------------------------------------------------------------------------------

ROUTE_RULES = [("glycolysis", r"ethylene glycol|\beg\b|glycol(?!ic)|diethylene|propylene glycol"),
               ("methanolysis", r"methanol|\bmeoh\b"),
               ("hydrolysis", r"water|aqueous|\bnaoh\b|\bkoh\b|h2so4|h3po4|acid solution|steam")]

# Abbreviations and spellings the rules above do not match, though the full name would.
BLIND = {"DEG": "glycolysis", "H2O": "hydrolysis", "PG": "glycolysis", "TEG": "glycolysis",
         "MEG": "glycolysis", "CH3OH": "methanolysis", "H₂O": "hydrolysis"}

SOLID = re.compile(r"\bZnO\b|TiO2|Al2O3|Fe3O4|SiO2|CeO2|\bMgO\b|\bCaO\b|Sb2O3|ZrO2|Mn3O4|"
                   r"Co3O4|\bCuO\b|\bNiO\b|zeolit|enzym|lipase|cutinase|PETase|hydrolase", re.I)


def inference(d):
    print("\n\033[1mINFERENCE — the columns nobody extracted\033[0m")

    # 16. Route is a regex over the solvent string, so it is decided by how a paper abbreviates
    #     its solvent rather than by what reaction it ran. `ethylene glycol` is glycolysis and
    #     `EG` is glycolysis, but `DEG` is not, and `water` is hydrolysis while `H2O` is not.
    blind = d.solvent.astype(str).str.strip().isin(BLIND)
    report(16, "rows routed 'other/unclear' only because of the abbreviation used",
           int(blind.sum()), int((d.route == "other/unclear").sum()),
           "the same reaction is routed differently depending on the paper's spelling",
           d[blind].groupby(["solvent", "route"]).size().reset_index(name="rows"))

    # 17. Solvents matching two rules at once. The cascade returns the first match with no
    #     record that a second fired, so a mixed-solvent run silently becomes a single route.
    def fired(value):
        text = str(value).lower()
        return [label for label, pattern in ROUTE_RULES if re.search(pattern, text)]
    multi = d.solvent.map(lambda s: len(fired(s)) > 1)
    report(17, "mixed solvents assigned one route by cascade order",
           int(multi.sum()), len(d), "no column records that the assignment was ambiguous",
           d[multi].groupby(["solvent", "route"]).size().reset_index(name="rows"))

    # 18. Alcoholysis. Ethanol, butanol, pentanol, hexanol and isodecyl alcohol are a real and
    #     growing route to dialkyl terephthalates; the schema has three routes, so they land in
    #     'other/unclear' and get no product at all -- as do ionic-liquid and DES solvents.
    alcohol = d.solvent.astype(str).str.contains(
        r"^(?:et(?:h)?anol|EtOH|\d-?(?:butan|pentan|hexan|octan|propan)ol|isodecyl|"
        r"benzyl alcohol|glycerol)", case=False, regex=True, na=False)
    unclear = d.route == "other/unclear"
    report(18, "rows whose route exists but is not one of the schema's three",
           int((alcohol | (unclear & d.solvent.notna())).sum()), len(d),
           "alcoholysis, ionic-liquid and carbonate routes have no schema slot",
           d[unclear].solvent.fillna("(none)").value_counts().head(10)
           .rename_axis("solvent").reset_index(name="rows"))

    # 19. The homogeneous filter is a name regex plus a lookup keyed on kind == "oxide". Two
    #     oxides are filed in that lookup under kind == "catalyst" instead, so they are never
    #     seen as oxides, and a compound name containing an oxide is never normalised to one.
    leak = d.catalyst.astype(str).str.contains(SOLID, na=False)
    report(19, "solid or enzymatic catalysts inside the 'homogeneous' subset",
           int(leak.sum()), len(d),
           "Fe3O4 and Co3O4 sit in smiles_lookup.csv under kind='catalyst', not kind='oxide'",
           d[leak][["doi", "catalyst", "catalyst_class"]].drop_duplicates())


# ---------------------------------------------------------------------------------------------
# SEMANTIC — what the numbers mean
# ---------------------------------------------------------------------------------------------

def semantic(d):
    print("\n\033[1mSEMANTIC — whether the column means one thing\033[0m")

    # 20. The strongest test available without a chemist. Yield must rise with temperature and
    #     with time, and both relationships are visible inside a single paper. If they vanish
    #     when papers are pooled, the pooled column is not one quantity: the yields are computed
    #     on different bases, against different products, from different feedstocks.
    print("\n      pooled across all papers:")
    pooled = {}
    for column in ["temperature_c", "reaction_time_min", "catalyst_amount_g"]:
        pair = d[[column, "yield_percent"]].dropna()
        pooled[column] = pair.corr(method="spearman").iloc[0, 1]
        print(f"        yield ~ {column:20s} n={len(pair):5,d}   ρ = {pooled[column]:+.3f}")
    loading = _loading(d.dropna(subset=["yield_percent"]))
    frame = pd.DataFrame({"loading": loading,
                          "yield": d.loc[loading.index, "yield_percent"]}).dropna()
    print(f"        yield ~ {'catalyst loading':20s} n={len(frame):5,d}   "
          f"ρ = {frame.corr(method='spearman').iloc[0, 1]:+.3f}")

    print("\n      within a single paper (paper effects removed):")
    inside = {}
    for column in ["temperature_c", "reaction_time_min"]:
        rhos = []
        for _, group in d.groupby("doi"):
            pair = group[[column, "yield_percent"]].dropna()
            if len(pair) > 4 and pair[column].nunique() > 2:
                rhos.append(pair.corr(method="spearman").iloc[0, 1])
        series = pd.Series(rhos).dropna()
        inside[column] = series
        print(f"        yield ~ {column:20s} {len(series):3d} papers   "
              f"median ρ = {series.median():+.2f}   positive in "
              f"{100 * (series > 0).mean():.0f}% of them")

    broken = sum(1 for column, rho in pooled.items()
                 if column != "catalyst_amount_g" and abs(rho) < 0.10)
    report(20, "physically required trends absent once papers are pooled",
           broken, 2,
           "the signal is real within a paper and gone across papers — "
           "yield_percent is not one quantity")

    # A companion count rather than a check: how concentrated the evidence is. Any random
    # train/test split leaks, because rows from one table land on both sides.
    sizes = d.groupby("doi").size().sort_values(ascending=False)
    print(f"\n      concentration: the largest 10 papers hold "
          f"{100 * sizes.head(10).sum() / len(d):.0f}% of rows, the largest 40 hold "
          f"{100 * sizes.head(40).sum() / len(d):.0f}%.")
    print("      A random row split therefore leaks; splits must be by paper.")


def main():
    global SHOW
    parser = argparse.ArgumentParser(prog="release_numbers")
    parser.add_argument("--tex", action="store_true", help="emit the \\newcommand block")
    parser.add_argument("--numbers", action="store_true", help="the macro table only")
    parser.add_argument("--show", type=int, default=SHOW, help="offending rows to print")
    args = parser.parse_args()
    SHOW = args.show
    table = compute()

    if args.tex:
        print("% --- the released dataset "
              + "-" * 48)
        print("% Computed by checks/release/release_numbers.py from "
              f"artifacts/release/{RELEASE.name}.")
        print("% These describe the RELEASE. The Database* macros describe the mass run and "
              "are a\n% different population; the two must not be mixed in one sentence.")
        for macro, (value, _, derivation) in table.items():
            print(f"\\newcommand{{\\{macro}}}{{{value}}}  % {derivation}")
        return

    width = max(len(m) for m in table)
    print(f"{'macro':<{width}}  {'value':>9}  source / derivation")
    print("-" * (width + 60))
    for macro, (value, source, derivation) in table.items():
        print(f"{macro:<{width}}  {value:>9}  {source}")
        print(f"{'':<{width}}  {'':>9}    {derivation}")
    if args.numbers:
        return

    # The same frame the macros were computed from, so a count here and a macro there cannot
    # describe different files.
    frame = load()
    print(f"\n\033[1m{RELEASE.relative_to(ROOT)}\033[0m — {len(frame):,} rows, "
          f"{frame.doi.nunique()} papers, {frame.catalyst.nunique()} catalyst names")
    mechanical(frame)
    identity(frame)
    inference(frame)
    semantic(frame)
    print(f"\n\033[1m{'─' * 78}\033[0m")
    print(f"{len(FAILURES)} of 20 checks found something.")
    for number, name, count in FAILURES:
        print(f"  {number:>2}. {count:>6,}  {name}")


if __name__ == "__main__":
    main()
