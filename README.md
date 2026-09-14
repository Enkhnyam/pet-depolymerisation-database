# PET depolymerisation database — extraction and evaluation code

The code behind *Building and Auditing Chemical Databases with LLMs*: a two-model pipeline that
extracts experimental records from chemistry papers and then audits them, and the evaluation
suite that decides whether the result can be trusted.

The database itself is released separately as data. This repository is how it was built and,
more to the point, how it was checked.

## What is worth looking at

**`checks/`** is the argument. Every number the paper quotes is computed here, by a script that
prints it — no number is typed into the manuscript by hand. `tools/paper_numbers.py` reads the
checks once and emits them as a single file of LaTeX macros, so a figure, a table and a sentence
quoting the same quantity cannot drift apart. That mechanism is the reason the evaluation is
auditable rather than merely reported.

```bash
scripts/checks.sh                  # every number, grouped as the paper uses them
scripts/checks.sh curated          # one group: curated | database | human | release
```

Checks are read-only: none calls a model, none writes a file.

**`core/`** is the library — schema, extraction, judging, and the string-matching grader the LLM
judge is measured against. No printing, no CLI.

**`figures/`** draws the paper's figures by importing `compute()` from the check that prints the
same numbers, so a panel and the checks cannot disagree.

## Layout

```
core/       library: schema, extraction, judging, the heuristic grader
cli/        the pipeline, one file per stage — these are the only things that spend money
configs/    one YAML per run; the filename is the run directory name
checks/     analysis that prints; read-only
figures/    the paper's figures, drawn from the checks
tools/      things that produce files — macros, reports, the reviewable HTML pages
prompts/    the extraction and judging prompts, verbatim
```

## Running it

Nothing here runs end-to-end from a clone, and that is deliberate: the corpus is 1,027 papers we
were licensed to *read* under text-and-data-mining agreements, not to redistribute. What a clone
gives you is the pipeline, the prompts, the schema, the grader and the whole evaluation suite,
which is what a reader needs to judge the method or point it at their own corpus.

```bash
uv sync
CONFIRM=1 scripts/run/extract.sh      # extraction over a corpus you supply
CONFIRM=1 scripts/run/judge.sh        # the audit pass over it
```

Run scripts ask before they start; top-level scripts only derive things that already exist.

If you want to try the pipeline on papers rather than read the code, the companion
[toolkit](https://github.com/Enkhnyam/chemistry-data-extractor-toolkit) is the same two-model
design as a local web app, and it ships with two open-access papers already processed.

## Configs

The filename is the run directory under `artifacts/runs/`.

| pattern | meaning |
|---|---|
| `extract_<model>` | that model on the curated benchmark papers |
| `judge_<A>_on_<B>` | judge A grading extraction B — the agreement matrix |
| `mass_<model>` | that model on the full corpus — the database |

`extract_luna` and `mass_luna` are the same model on different corpora: the first can be scored
against a hand-curated table, the second cannot, which is the problem the judge exists to solve.

## One thing that will bite you

The human-labelled records identify records **by position** within the run they were drawn from,
and are only meaningful against that run — scoring them against a different extraction silently
relabels about a quarter of them. `checks/_setup.py:golden()` handles this; do not repoint it.

## Licensing

The code is MIT (`LICENSE`). The papers it was run on are not ours to pass on, and none are in
this repository — see `NOTICE.md` for what that means in practice and what the released dataset
does and does not contain.
