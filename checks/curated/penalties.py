"""Among pairs the matcher did pair, which fields disagreed, and how much headroom the accepted
ones had against the cutoff.

Penalties clustered just under the cutoff mean the threshold is carrying the result and it is
fragile. Clustered near zero, the matches are comfortable and the cutoff barely matters.
"""
import pandas as pd

from _setup import ACCEPT, scored, show, totals


def main() -> None:
    result = totals()
    field_errors = pd.Series(result["field_error_counts"]).sort_values(ascending=False)

    accepted = scored().query("verdict == 'TP'")

    show("field disagreements among matched pairs", field_errors, fmt="{:.0f}")
    show(f"penalty of accepted matches (accepted below {ACCEPT:.2f})",
         accepted.avg_penalty.describe())


if __name__ == "__main__":
    main()
