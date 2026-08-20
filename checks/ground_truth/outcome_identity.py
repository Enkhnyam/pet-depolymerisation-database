"""Yield should equal conversion x selectivity. Needs no external truth -- the identity holds
or the three numbers came from different tables."""
from _setup import *

table = curated()
complete = table.dropna(subset=OUTCOMES)
error = (complete.yield_percent
         - complete.conversion_percent * complete.selectivity_percent / 100).abs()

print(f"\nexperiments reporting all three outcomes: {len(complete)} of {len(table)}")
show("reported minus implied yield", error.describe())
