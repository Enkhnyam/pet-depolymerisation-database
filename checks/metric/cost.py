"""The spend ledger across every run that still has a config."""
from _setup import *

ledger = runs().set_index("run")[
    ["model", "n_papers", "prompt_tokens", "completion_tokens", "cost_usd", "parse_failed_papers"]]
show("runs", ledger, fmt="{:.2f}")
print(f"\ntotal spent ${ledger.cost_usd.sum():.2f}")
