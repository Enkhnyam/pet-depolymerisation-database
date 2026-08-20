from _setup import *

completed = runs().set_index("run")
columns = ["model", "n_papers", "prompt_tokens", "completion_tokens", "cost_usd",
           "parse_failed_papers"]
table = completed[columns].to_string(float_format="{:.2f}".format)
total = completed.cost_usd.sum()

print(table)
print()
print("total spent", f"${total:.2f}")
