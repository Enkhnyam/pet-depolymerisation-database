# PET depolymerisation database

A database of PET depolymerisation experiments extracted from 447 papers, with a quality figure
derived from judge–metric agreement rather than from curating the whole corpus.

## Layout

```
core/       the library — schema, extraction, judging, the metric grader. No printing, no CLI.
cli/        the pipeline, one file per stage. These write to artifacts/runs/.
configs/    one YAML per run. The filename is the run directory name.
checks/     analysis that prints. Read-only: no check calls a model or writes a file.
tools/      things that produce files — figures and the supervisor review pages.
artifacts/  everything produced. Nothing here is hand-edited.
```

## Running the pipeline

```bash
./.venv/bin/python -W ignore -u cli/run.py extract --config configs/extract/mass_luna.yaml
./.venv/bin/python -W ignore -u cli/judge.py --config configs/judge/mass_oss.yaml
./.venv/bin/python -W ignore -u cli/apply_fixes.py --judge-run mass_oss/mass_oss
```

Judging is resumable; extraction is not, and re-runs every paper from the start.

## Running the checks

```bash
./.venv/bin/python -W ignore checks/run.py                    # all of them
./.venv/bin/python -W ignore checks/run.py metric/scores.py   # one or several
```

Always go through `run.py` — the scripts do `from _setup import *`, and the runner is what puts
`checks/` on the import path. None of them take arguments: what is being measured is set in
`checks/_setup.py`, in one place, so no two checks can disagree.

| group | asks |
|---|---|
| `curated/` | the 24-paper benchmark — the answer key, the metric on it, grader vs grader |
| `database/` | the 447-paper mass run — funnel, verdicts, citation provenance |
| `human/` | the 48 records two chemists adjudicated |
| `cost.py` | the spend ledger, which spans all of them |

## Getting the numbers

Each script prints one group of results, using the checks that produce them.

```bash
scripts/results_curated.sh    # the 24-paper benchmark: answer key, model scores, agreement matrix
scripts/results_database.sh   # the 447-paper database: funnel, verdicts, citation provenance
scripts/results_human.sh      # the 48 adjudicated records: what they establish and what they cannot
scripts/results_all.sh        # all of it, grouped the way the paper uses it
```

## Adjudicating a new comparison

```bash
scripts/build_adjudication.sh                    # the shipped pair (oss judging luna)
JUDGE=luna TARGET=terra scripts/build_adjudication.sh
```

Collects the records the two graders disagree about into a page where a chemist decides each one
without seeing either grader's verdict. Only disagreements are worth labelling — each becomes an
informative McNemar pair the moment it is decided, because one grader must be the one that
matched. `checks/judge/power.py` says how many are needed.

## Publishing a review page

```bash
./.venv/bin/python -W ignore tools/review_database.py \
    --extraction mass_luna --judge mass_oss/mass_oss --corpus corpus_markdown
```

Writes a self-contained HTML page: every record with its fields, the judge's verdict and
reasoning, the corrections it proposed, and the source text the record cites with the extracted
values highlighted inside it. A toggle switches between the extracted and the corrected values.

Any extraction and judge run work, whatever models produced them — `--extraction` and `--judge`
take run directories under `artifacts/runs/`. Omit `--judge` to render an extraction on its own,
which is how the corrected bundle from `apply_fixes.py` is rendered.

## Configs

The filename is the run directory under `artifacts/runs/`.

| pattern | meaning |
|---|---|
| `extract_<model>` | that model on the 24 curated papers — the benchmark |
| `judge_<A>_on_<B>` | judge A grading extraction B — the agreement matrix |
| `mass_<model>` | that model on the 447-paper corpus — the database |

`extract_luna` and `mass_luna` are the same model on different corpora: the first can be scored
against the curated table, the second cannot, which is the point of the project.

## The one thing to know about the labelled set

The 48 human-labelled records in `artifacts/gold/` identify records **by position** within the
run they were drawn from, which is kept beside them as `artifacts/gold/source_run/`. They are
only meaningful against that run — scoring them against a different extraction silently relabels
about a quarter of them. `_setup.golden()` handles this; do not repoint it at `EXTRACTION`.
