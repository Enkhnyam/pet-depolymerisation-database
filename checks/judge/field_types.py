"""Why the two graders agree: eight of the ten fields are numbers, and a number is inside
tolerance or it is not. Almost every disagreement sits on the catalyst, the one free-text
field -- so on a schema this rigid, reading the paper and matching a table do nearly the
same job.
"""
from collections import Counter
from _setup import *

TEXT = {"catalyst", "solvent"}
both = scored().query("situation != 'no curated counterpart'").merge(judged(), on=["doi", "index"])

show("on records the table could be compared against",
     {"records": len(both), "graders agree": (both.judge == both.metric).sum()}, fmt="{:.0f}")

flagged = both.query("judge == 'incorrect'")
show(f"fields the judge names in the {len(flagged)} it rejects",
     pd.Series(Counter(f for row in flagged.bad_fields for f in row)).sort_values(ascending=False),
     fmt="{:.0f}")
print(f"  of those, naming a text field: "
      f"{sum(1 for row in flagged.bad_fields if TEXT & set(row))}")

accepted = both.query("verdict == 'TP'")
still_wrong = Counter(f for row in accepted.field_errors for f in row)
show(f"wrong fields inside the {len(accepted)} pairs the metric accepted",
     {"total": sum(still_wrong.values()),
      "numeric": sum(v for f, v in still_wrong.items() if f not in TEXT)}, fmt="{:.0f}")
