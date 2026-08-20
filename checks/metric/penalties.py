"""Among pairs the matcher did pair, which fields disagreed and how much headroom the
accepted ones had. Penalties clustered just under the cutoff mean a fragile result."""
from _setup import *

result = totals()
show("field disagreements among matched pairs",
     pd.Series(result["field_error_counts"]).sort_values(ascending=False), fmt="{:.0f}")
show(f"penalty of accepted matches (accepted below {ACCEPT:.2f})",
     scored().query("verdict == 'TP'").avg_penalty.describe())
