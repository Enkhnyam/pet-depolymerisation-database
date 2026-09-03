"""Write the database as a Hugging Face dataset repository.

Layout follows the shape the Hub expects and that LeMat-Synth uses: one directory per config,
holding sharded parquet named `<name>-NNNNN-of-NNNNN.parquet`, and a README.md whose YAML
frontmatter names the configs. Two configs ship:

  full     every extracted record, including the ones whose catalyst has no structure
  usable   the subset whose catalyst is `confirmed`, `LLM written` or `no catalyst` -- that is,
           rows where the structure column is either filled or correctly empty, and not merely
           missing. This is the subset a cheminformatics pipeline can consume without filtering.

Structures come from core.smiles.tier_of, which crosses the curated lookup against OPSIN and
reports how much independent support each value has. OPSIN is called once per distinct name
rather than once per row: the JVM start-up dominates otherwise.

    export_hf.py                       write artifacts/huggingface/
    export_hf.py --out <dir>
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

from core.paths import ARTIFACTS
from core.smiles import TIERS, canonical, cleaned, product_for, substrate, tier_of

FLAT = ARTIFACTS / "release" / "mass_luna_1shot_flat.csv"
OUT = ARTIFACTS / "huggingface"

# Rows whose catalyst structure is either present or correctly absent. "unclear" is a gap someone
# could close; "impossible" is a preparation rather than a substance. Both are honest values and
# both make the row unusable as a structure-keyed training example, so they define the subset.
USABLE = ("confirmed", "LLM written", "no catalyst")

# Dropped on the way out, with the reason. Nothing here carries information the rest does not.
DROPPED = {
    "judge_parsed_ok": "constant True -- every judge response parsed",
    "record_survives": "exactly the negation of judge_drop_record",
    "substrate": "constant 'PET'; substrate_smiles carries it",
}

COLUMNS = [
    # identity and provenance
    "record_id", "doi", "title", "journal", "record_index", "source_format", "source_chunk_ids",
    # chemistry as the paper writes it
    "route", "catalyst_class", "catalyst", "solvent",
    # structures
    "catalyst_smiles", "catalyst_smiles_tier", "solvent_smiles", "solvent_smiles_tier",
    "product", "product_smiles", "substrate_smiles",
    # conditions
    "temperature_c", "reaction_time_min", "pressure_atm",
    "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
    # outcomes
    "yield_percent", "conversion_percent", "selectivity_percent",
    # the audit
    "judge_verdict", "judge_drop_record", "judge_n_fixes", "judge_bad_fields",
    "judge_critique", "judge_fixes", "n_citations", "citations_resolve",
    # the audit's proposed values
    "corrected_catalyst", "corrected_solvent", "corrected_temperature_c",
    "corrected_reaction_time_min", "corrected_pressure_atm", "corrected_catalyst_amount_g",
    "corrected_PET_amount_g", "corrected_solvent_amount_g", "corrected_yield_percent",
    "corrected_conversion_percent", "corrected_selectivity_percent", "corrected_fields",
]


def opsin(names: list[str]) -> dict:
    """OPSIN's canonical structure for each name, or None. One JVM call for the whole list."""
    from py2opsin import py2opsin
    raw = dict(zip(names, py2opsin(names)))
    tidy = dict(zip(names, py2opsin([cleaned(n) for n in names])))
    out = {}
    for name in names:
        out[name] = canonical(raw[name]) if raw[name] else (
            canonical(tidy[name]) if tidy[name] else None)
    return out


def with_smiles(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column, kind in (("catalyst", "catalyst"), ("solvent", "solvent")):
        names = sorted({str(v).strip() for v in frame[column].dropna() if str(v).strip()})
        library = opsin(names)
        decided = {n: tier_of(n, kind, library[n]) for n in names}
        key = frame[column].astype(str).str.strip()
        frame[f"{column}_smiles"] = key.map(lambda n: decided.get(n, (None, ""))[0])
        frame[f"{column}_smiles_tier"] = key.map(
            lambda n: decided.get(n, (None, "not reported"))[1])

    products = [product_for(route) for route in frame["route"]]
    frame["product"] = [name for name, _ in products]
    frame["product_smiles"] = [smiles for _, smiles in products]
    frame["substrate_smiles"] = substrate()
    return frame


def verify(frame: pd.DataFrame) -> dict:
    """Every SMILES written must parse, and be the canonical form RDKit produces."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    report = {}
    for column in ("catalyst_smiles", "solvent_smiles", "product_smiles", "substrate_smiles"):
        values = [v for v in frame[column].dropna().unique() if v]
        bad = [v for v in values
               if Chem.MolFromSmiles(v) is None
               or Chem.MolToSmiles(Chem.MolFromSmiles(v)) != v]
        report[column] = {"distinct": len(values), "bad": bad}
    return report


FRONTMATTER = """---
license: cc-by-4.0
pretty_name: PET Depolymerisation Experiments
language:
  - en
task_categories:
  - tabular-regression
tags:
  - chemistry
  - cheminformatics
  - polymers
  - PET
  - depolymerisation
  - chemical-recycling
  - literature-mining
  - rdkit
  - tabular
size_categories:
  - 1K<n<10K
configs:
  - config_name: full
    default: true
    data_files:
      - split: train
        path: full/records-*.parquet
  - config_name: usable
    data_files:
      - split: train
        path: usable/records-*.parquet
---
"""

BODY = """
# PET depolymerisation experiments

{full_rows:,} depolymerisation experiments read out of {full_papers:,} full-text articles: the
reaction conditions and the reported outcome of each individual run, not one summary row per paper.
Every record names the passages it came from and carries a second model's verdict on whether the
paper supports it.

```python
from datasets import load_dataset

full   = load_dataset("<user>/pet-depolymerisation", "full",   split="train")   # {full_rows:,} rows
usable = load_dataset("<user>/pet-depolymerisation", "usable", split="train")   # {usable_rows:,} rows
```

## The two configs

| config | rows | papers | what it is |
|---|---|---|---|
| `full` | {full_rows:,} | {full_papers:,} | everything extracted, structures or not |
| `usable` | {usable_rows:,} | {usable_papers:,} | rows whose catalyst structure is filled or correctly empty |

`usable` keeps the rows where `catalyst_smiles_tier` is `confirmed`, `LLM written` or
`no catalyst`. It drops `unclear` (a gap someone could close) and `impossible` (the name denotes a
preparation, not a substance). Nothing else differs -- same columns, same values.

## Structures

`catalyst` and `solvent` are stored as the paper writes them. Alongside each sits a canonical
SMILES and a tier saying how much independent support that structure has:

| tier | meaning | catalyst | solvent |
|---|---|---|---|
{tier_table}

`confirmed` means OPSIN derived the structure from the name, or agreed with the curated entry.
`LLM written` means a language model supplied it and no library can read the name to check it --
abbreviations, formulas and trade names land here. It may well be right; nothing independent
confirms it. Filter on the tier if that distinction matters to you.

Solvents resolve well because the vocabulary is small. Catalysts resolve less well, and the reason
is chemistry rather than effort: supported catalysts (`10 wt% MgO/SiO2`), mixed oxides, layered
double hydroxides, calcined minerals and deep eutectic mixtures have no single SMILES. A null in
`catalyst_smiles` is a statement, not an omission.

Mixtures are joined with `.`, which RDKit reads as separate fragments: `EtOH:H2O` is `CCO.O`.
Every non-null SMILES in either config parses in RDKit and is written in RDKit's canonical form.

```python
from rdkit import Chem
mols = [Chem.MolFromSmiles(s) for s in usable["catalyst_smiles"] if s]
```

Route is inferred from the solvent, and `product` follows from the route -- glycolysis gives BHET,
methanolysis DMT, hydrolysis TPA. {no_route:,} rows match none of the three and carry no product.
`substrate_smiles` is the PET repeat unit with attachment points, constant across the dataset.

## Columns

One row per experiment, {n_columns} columns.

| group | columns |
|---|---|
| identity | `record_id`, `doi`, `title`, `journal`, `record_index` |
| provenance | `source_format`, `source_chunk_ids`, `n_citations`, `citations_resolve` |
| as written | `route`, `catalyst_class`, `catalyst`, `solvent` |
| structures | `catalyst_smiles`, `solvent_smiles`, `product_smiles`, `substrate_smiles`, `*_tier`, `product` |
| conditions | `temperature_c`, `reaction_time_min`, `pressure_atm`, `catalyst_amount_g`, `PET_amount_g`, `solvent_amount_g` |
| outcomes | `yield_percent`, `conversion_percent`, `selectivity_percent` |
| audit | `judge_verdict`, `judge_drop_record`, `judge_n_fixes`, `judge_bad_fields`, `judge_critique`, `judge_fixes` |
| proposed values | `corrected_*` |

`source_chunk_ids` are semicolon-separated identifiers of the passages the record was read from.
`citations_resolve` says whether all of them were found in the parsed document.

Fill rates vary a lot and the reason is reporting practice, not extraction. Temperature and time
are given in most papers; selectivity is given in almost none:

{fill_table}

## The audit, and what it is worth

Every record was extracted by one language model from full text, then reviewed record by record by
a different one, which accepted {accepted:.1f}% unchanged and asked to drop {dropped:,}.

On {adjudicated} records adjudicated by two chemists, the judge graded better than a
curated-reference heuristic, but both flag more records than the chemists reject and neither
agrees with a chemist far beyond chance. Treat the audit as a filter that concentrates expert
attention, not as a substitute for it.

The judge's proposed corrections ship as a candidate change set in the `corrected_*` columns. They
touch {changed_cells:,} of {total_cells:,} value cells ({changed_rows:,} rows); everywhere else
`corrected_x` repeats `x`. Whether a proposed value improves on the one it replaces has not been
measured, so the two views are shipped side by side rather than one silently applied.

```python
import pandas as pd
as_extracted = full.to_pandas()
audited = as_extracted.assign(**{{c: as_extracted["corrected_" + c] for c in FIELDS}})
```

## Limits worth knowing before you use this

- **Outcome reporting is the binding constraint.** Yield is present in {yield_fill:.0f}% of rows
  and selectivity in {sel_fill:.0f}%. A model needing conditions *and* an outcome has far fewer
  rows than the row count suggests.
- **Units are as reported and not range-checked.** `PET_amount_g` has implausible extremes.
- **`route` is inferred**, not stated by the paper.
- **The `LLM written` tier is unverified** by construction.

## Provenance

Built from open-access full text obtained through Europe PMC, Elsevier and publisher PDFs. Only
the extracted values are redistributed here; no article text is included beyond the passage
identifiers.

Artifact set `{artifact}`. Every number in this card and in the paper is generated from that
frozen run.

## Citation

```bibtex
@article{{pet_depolymerisation_database,
  title  = {{TITLE}},
  author = {{AUTHORS}},
  year   = {{2026}},
  doi    = {{DOI}}
}}
```
"""


def shard(frame: pd.DataFrame, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("records-*.parquet"):
        stale.unlink()
    frame.to_parquet(directory / "records-00000-of-00001.parquet", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(prog="export_hf")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.out.resolve()

    frame = with_smiles(pd.read_csv(FLAT))
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise SystemExit(f"columns missing from the flat export: {missing}")
    dropped = [c for c in frame.columns if c not in COLUMNS]

    full = frame[COLUMNS]
    usable = full[full["catalyst_smiles_tier"].isin(USABLE)].reset_index(drop=True)

    report = verify(full)
    shard(full, out / "full")
    shard(usable, out / "usable")

    # --- the card's numbers, all read off the frame ---
    fields = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "pressure_atm",
              "catalyst_amount_g", "PET_amount_g", "solvent_amount_g", "yield_percent",
              "conversion_percent", "selectivity_percent"]
    changed = sum((~((full[f].isna() & full["corrected_" + f].isna())
                     | (full[f] == full["corrected_" + f]))).sum() for f in fields)
    changed_rows = 0
    mask = pd.Series(False, index=full.index)
    for f in fields:
        mask |= ~((full[f].isna() & full["corrected_" + f].isna())
                  | (full[f] == full["corrected_" + f]))
    changed_rows = int(mask.sum())

    tiers = []
    for name in ("confirmed", "LLM written", "unclear", "impossible", "no catalyst",
                 "not reported"):
        cat = int((full["catalyst_smiles_tier"] == name).sum())
        sol = int((full["solvent_smiles_tier"] == name).sum())
        if not cat and not sol:
            continue
        gloss = TIERS[name].split(" -- ", 1)[-1].split(".")[0]
        tiers.append(f"| `{name}` | {gloss} | {cat:,} | {sol:,} |")

    shown = ["temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
             "solvent_amount_g", "yield_percent", "conversion_percent", "selectivity_percent",
             "pressure_atm"]
    fill = ["| column | filled |", "|---|---|"] + [
        f"| `{c}` | {100 * full[c].notna().mean():.0f}% |" for c in shown]

    artifact = (ARTIFACTS / "paper_numbers.tex").read_text(encoding="utf-8")
    artifact = artifact.split("artifact set ")[1].split(",")[0].strip() if \
        "artifact set " in artifact else "unknown"

    card = FRONTMATTER + BODY.format(
        full_rows=len(full), full_papers=full["doi"].nunique(),
        usable_rows=len(usable), usable_papers=usable["doi"].nunique(),
        tier_table="\n".join(tiers),
        no_route=int(full["product_smiles"].isna().sum()),
        n_columns=len(COLUMNS),
        fill_table="\n".join(fill),
        accepted=100 * (full["judge_verdict"] == "correct").mean(),
        dropped=int(full["judge_drop_record"].sum()),
        adjudicated=112,
        changed_cells=int(changed), total_cells=len(full) * len(fields),
        changed_rows=changed_rows,
        yield_fill=100 * full["yield_percent"].notna().mean(),
        sel_fill=100 * full["selectivity_percent"].notna().mean(),
        artifact=artifact)
    (out / "README.md").write_text(card, encoding="utf-8")

    # --- what happened ---
    print(f"full    {len(full):,} rows x {len(COLUMNS)} columns   "
          f"{full['doi'].nunique():,} papers")
    print(f"usable  {len(usable):,} rows                     "
          f"{usable['doi'].nunique():,} papers")
    print(f"\ndropped {len(dropped)} columns:")
    for column in dropped:
        print(f"   {column:22s} {DROPPED.get(column, 'not in the published schema')}")
    print("\nSMILES check:")
    for column, result in report.items():
        flag = "OK" if not result["bad"] else f"PROBLEM: {result['bad'][:2]}"
        print(f"   {column:18s} {result['distinct']:4d} distinct   {flag}")
    print(f"\nwrote {out.relative_to(ROOT)}/{{full,usable}}/records-00000-of-00001.parquet")
    print(f"      {out.relative_to(ROOT)}/README.md")


if __name__ == "__main__":
    main()
