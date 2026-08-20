"""The judge on the database. No curated table exists here, which is the point: this is the
number the agreement study licenses us to read as a quality estimate.

It measures precision, not recall -- the judge only ever sees records that exist, so a missed
experiment is invisible to it.
"""
from collections import Counter
from _setup import *

verdicts = []
for path in (DATABASE_JUDGE / "verdicts").glob("*.json"):
    verdicts += json.loads(path.read_text())["verdicts"]

accepted = sum(1 for v in verdicts if v["verdict"] == "correct")
rejected = [v for v in verdicts if v["verdict"] != "correct"]
corrected = sum(1 for v in rejected if v["bad_fields"])

show("verdicts", {"records judged": len(verdicts),
                  "accepted": accepted,
                  "rejected, with a correction": corrected,
                  "rejected outright": len(rejected) - corrected}, fmt="{:.0f}")
print(f"\npass rate {accepted / len(verdicts):.1%}")

show("fields corrected",
     pd.Series(Counter(f for v in rejected for f in v["bad_fields"])).sort_values(ascending=False),
     fmt="{:.0f}")
