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
| `ground_truth/` | is the curated answer key itself sound? |
| `metric/` | is the metric grader behaving? thresholds, catalyst matching, cost |
| `golden_set/` | what the two chemists said about 48 records |
| `judge/` | judge against metric, and against the chemists |
| `database/` | the 447-paper corpus run, its verdicts, and whether its citations resolve |

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
