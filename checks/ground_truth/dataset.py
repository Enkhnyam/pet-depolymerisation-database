from _setup import *

experiments = curated()

paper_count = experiments.doi.nunique()
catalyst_count = experiments.catalyst.nunique()
missing_share = experiments[fields].isna().mean().sort_values(ascending=False)
missing_table = missing_share.to_string(float_format="{:.0%}".format)

print("papers            ", paper_count)
print("experiments       ", len(experiments))
print("distinct catalysts", catalyst_count)
print()
print("share of experiments where the field is missing:")
print(missing_table)
