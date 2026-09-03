"""The spend ledger across every run that still has a config."""
from _setup import ROOT, RUNS_DIR, runs, show, sources

COLUMNS = ["model", "n_papers", "prompt_tokens", "completion_tokens", "cost_usd",
           "parse_failed_papers"]


def compute():
    """The spend ledger, one row per run that still has a config."""
    return runs()


def arm_cost(model: str, n_shots: int) -> float:
    """Mean cost of one benchmark arm: a model at a shot count, across its repeats.

    Lived in tools/paper_numbers.py as a closure over two frames it re-indexed itself. The
    ledger is here, so the question about it is too.
    """
    from curated import extractions
    arm = extractions.runs()
    arm = arm[(arm.model == model) & (arm.n_shots == int(n_shots))]
    ledger = compute().set_index("run")
    spent = [ledger.loc[key, "cost_usd"] for name in arm.run
             for key in ledger.index if key.endswith("/" + name)]
    return sum(spent) / len(spent) if spent else float("nan")


def main() -> None:
    sources(runs=RUNS_DIR, configs=ROOT / 'configs')
    ledger = runs().set_index("run")[COLUMNS]

    show("runs", ledger, fmt="{:.2f}")
    print(f"\ntotal spent ${ledger.cost_usd.sum():.2f}")


if __name__ == "__main__":
    main()
