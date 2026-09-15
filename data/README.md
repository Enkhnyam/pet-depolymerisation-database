# The dataset

3,942 homogeneous catalytic PET depolymerisation experiments, read out of 561 articles by an
LLM extractor and audited against those same articles by an independent LLM judge.

| file | rows | what it is |
|---|---|---|
| `pet_homogeneous_catalysis.csv` | 3,942 | one row per experiment — start here |
| `pet_homogeneous_catalysis.xlsx` | 3,942 | the same table, for spreadsheet users |
| `benchmark/curated_benchmark.json` | 295 | the hand-curated reference key: 295 experiments across 24 ionic-liquid glycolysis papers, used to validate the judge before it was deployed |

## The values are as extracted, not as corrected

`catalyst`, `temperature_c`, `yield_percent` and the rest hold what the extractor read from the
paper. The judge's opinion sits beside them in the `judge_*` columns, and the values it would
have put there instead are in the `corrected_*` columns. Nothing is substituted silently.

Applying a correction is a decision for you, not one we made on your behalf — and it should be
an informed one. In our own human review of 120 proposed corrections, 49% were real errors and
48% were two defensible readings of the same paper; of 22 proposals to rename a substance, 21
turned out to be an alternative name for the same compound rather than a mistake.

## Columns

**Identity** — `record_id` (unique), `doi`, `title`, `journal`, `record_index`, `source_format`.

**Provenance** — `source_chunk_ids` lists the UUIDs of the text chunks the extractor cited for
this record; `n_citations` and `citations_resolve` say how many there were and how many resolved
to a real chunk. Recovering the passage behind a UUID needs your own access to the article: no
article text is redistributed here.

**Chemistry** — `route` (glycolysis / methanolysis / hydrolysis, inferred from the solvent),
`catalyst`, `catalyst_class`, `solvent`, `product`, and RDKit SMILES for each with a
`*_smiles_tier` recording how confidently the name resolved.

**Conditions and outcomes** — `temperature_c`, `reaction_time_min`, `pressure_atm`,
`catalyst_amount_g`, `PET_amount_g`, `solvent_amount_g`, `yield_percent`, `conversion_percent`,
`selectivity_percent`. A null means the paper did not report it, which is not the same as zero.

**The judge's audit** — `judge_verdict` (correct / incorrect), `judge_bad_fields`,
`judge_critique` (why, in a sentence or two), `judge_n_fixes`, `judge_fixes`, and
`judge_drop_record` for records it would delete rather than repair.

**The judge's proposed values** — `corrected_<field>` for each data field, plus
`corrected_fields`.

**Curation** — `phase`, `phase_why`, `phase_by` (how the catalyst was established as
homogeneous), `structure_source`, `catalyst_loading_wt`, `yield_basis`, `single_component`,
`duplicate_of`, `quality_flags`, `audit`.

## What is not here

The articles. The corpus behind this reached us under text-and-data-mining entitlements that
permit reading and mining but not redistribution, so no article text — converted or original —
is published. What you have is extracted values, the identifiers of the chunks they came from,
and the judge's short critique of each. See `../NOTICE.md`.

## Licence

CC BY 4.0, covering the extracted data. It does not extend to the articles the data was read
from, which remain under their publishers' terms.
