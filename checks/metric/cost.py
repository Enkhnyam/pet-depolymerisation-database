"""The spend ledger across every run that still has a config."""
from _setup import runs, show

COLUMNS = ["model", "n_papers", "prompt_tokens", "completion_tokens", "cost_usd",
           "parse_failed_papers"]


def main() -> None:
    ledger = runs().set_index("run")[COLUMNS]

    show("runs", ledger, fmt="{:.2f}")
    print(f"\ntotal spent ${ledger.cost_usd.sum():.2f}")


if __name__ == "__main__":
    main()
