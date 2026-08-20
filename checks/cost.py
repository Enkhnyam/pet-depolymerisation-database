"""The spend ledger across every run that still has a config."""
from _setup import ROOT, RUNS_DIR, runs, show, sources

COLUMNS = ["model", "n_papers", "prompt_tokens", "completion_tokens", "cost_usd",
           "parse_failed_papers"]


def main() -> None:
    sources(runs=RUNS_DIR, configs=ROOT / 'configs')
    ledger = runs().set_index("run")[COLUMNS]

    show("runs", ledger, fmt="{:.2f}")
    print(f"\ntotal spent ${ledger.cost_usd.sum():.2f}")


if __name__ == "__main__":
    main()
