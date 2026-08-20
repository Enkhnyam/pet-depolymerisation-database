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

## Running things

Two kinds of script. The top level derives things from what already exists and is always safe to
run; `run/` spends money or hours and asks first.

```bash
scripts/checks.sh                     # every number, grouped as the paper uses them
scripts/checks.sh curated             # one group: curated | database | human
scripts/figures.sh                    # draw the figures into artifacts/figures/
scripts/pages.sh                      # the reviewable HTML pages
```

```bash
CONFIRM=1 scripts/run/extract.sh              # the 447-paper extraction (~$8.50, not resumable)
CONFIRM=1 scripts/run/judge.sh                # judging it (free, ~3 h, resumable)
CONFIRM=1 scripts/run/ablation_shots.sh       # n_shots 0..6 x 3 (~$8)
CONFIRM=1 scripts/run/ablation_source.sh      # citing sources on/off x 3 (~$3)
```

## Figures

```
core/ → checks/ (compute + print) → figures/ (compute + draw)
```

A figure module imports `compute()` from the check that prints the same numbers, so a panel and
`scripts/checks.sh` cannot disagree — nothing is recomputed for a plot. `figures/_style.py` holds
the palette and the panel primitives, so all three canvases share one visual language by
construction.

Three canvases, one per claim: `fig1_database` (what was built), `fig2_chemistry` (does it behave
like chemistry), `fig3_quality` (how far we can vouch for it).

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
