# Configs

One YAML per run. `configs/extract/*.yaml` name an extraction; `configs/judge/*.yaml` name a
judge run over a named extraction. `cli/run.py --config` and `cli/judge.py --config` take them.

**These files are not just parameters, they are the registry of which runs are real.**
`checks/_setup.runs()` keeps a run bundle in the spend ledger only if a config with its stem
still exists, so deleting a config silently removes the run it describes from `checks/cost.py`.
The nine `judge_*_on_*.yaml` are 141 lines with 46 unique among them, and they stay that way on
purpose: each is the exact, reviewable record of one cell of the agreement matrix the paper
reports. Collapsing them into CLI flags would move the parameters of a published result out of
version control and into a shell invocation someone has to retype correctly.

## The model nicknames

Each key is the short name used in run directories, macros and figures.

| key       | model                                | endpoint | max tokens | metered |
|-----------|--------------------------------------|----------|-----------:|---------|
| `sol`     | `azure/gpt-5.6-sol`                  | Azure    |     16,000 | yes     |
| `luna`    | `azure/gpt-5.6-luna`                 | Azure    |     16,000 | yes     |
| `terra`   | `azure/gpt-5.6-terra`                | Azure    |     16,000 | yes     |
| `mini`    | `azure/gpt-5.4-mini`                 | Azure    |     16,000 | yes     |
| `mlarge`  | `azure/Mistral-Large-3`              | Azure    |      8,192 | yes     |
| `oss`     | `openai/gpt-oss-120b`                | RWTH     |      8,192 | no      |
| `mistral` | `openai/mistral-small-4-119b-2603`   | RWTH     |      8,192 | no      |

Azure is `karim-api-resource.openai.azure.com` (`${azure_key}`); RWTH is
`chat.kiconnect.nrw/api/v1/` (`${openai_key}`). The unmetered RWTH models cost nothing, which is
why `oss` is the judge everywhere the matrix does not require otherwise.

`gpt-5.5` is deliberately absent: the RWTH endpoint caps it at 20 messages an hour and 50 a day,
which cannot carry a 24-paper benchmark run, let alone the 1,026-paper extraction.

Recorded here because `cli/make_matrix_configs.py`, which generated these files from this table,
was deleted -- the configs it wrote are committed, and a generator with no callers writing files
that are already in git is a second copy of them.
