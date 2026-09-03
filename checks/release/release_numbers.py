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

The data-quality battery that used to sit under these 185 lines -- 420 more lines asking twenty
questions about the same file -- is checks/release/quality.py. They shared nothing but load().

    release_numbers.py            print the table of macro, value, source and derivation
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



def main():
    parser = argparse.ArgumentParser(prog="release_numbers")
    parser.add_argument("--tex", action="store_true", help="emit the \\newcommand block")
    parser.parse_args()
    table = compute()

    width = max(len(m) for m in table)
    print(f"{'macro':<{width}}  {'value':>9}  source / derivation")
    print("-" * (width + 60))
    for macro, (value, source, derivation) in table.items():
        print(f"{macro:<{width}}  {value:>9}  {source}")
        print(f"{'':<{width}}  {'':>9}    {derivation}")


if __name__ == "__main__":
    main()
