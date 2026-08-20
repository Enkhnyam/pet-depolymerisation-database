"""Shape of the answer key: how big it is and which fields the literature omits."""
from _setup import *

table = curated()
show("size", {"papers": table.doi.nunique(),
              "experiments": len(table),
              "distinct catalysts": table.catalyst.nunique()}, fmt="{:.0f}")
show("share of experiments where the field is blank",
     table[FIELDS].isna().mean().sort_values(ascending=False), fmt="{:.0%}")
