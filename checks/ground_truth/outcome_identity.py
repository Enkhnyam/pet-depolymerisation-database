from _setup import *

experiments = curated()
complete = experiments.dropna(subset=outcomes)

implied_yield = complete.conversion_percent * complete.selectivity_percent / 100
error = (complete.yield_percent - implied_yield).abs()
summary = error.describe().to_string(float_format="{:.3f}".format)

print("experiments reporting all three outcomes", len(complete), "of", len(experiments))
print()
print("difference between the reported and the implied yield:")
print(summary)
