"""Separates 'our matcher is broken' from 'this subfield is unlookuppable'.

Where both names in a rejected pair are ordinary chemical names, the metric paired the wrong
experiments -- a real defect. Elsewhere at least one name is a mixture, a supported material or
a code the paper coined, none of which any string comparison could resolve.
"""
from _setup import *

def kind_of(name):
    text, lowered = str(name), str(name).lower()
    if "/" in text or "+" in text or " and " in lowered:
        return "mixture of two"
    if "@" in text:
        return "supported on a carrier"
    if lowered.startswith(("pil", "cat-", "il-", "des")):
        return "code the paper coined"
    return "plain chemical name"

names = sorted(set(curated().catalyst.dropna()) | set(records().catalyst.dropna()))
show(f"all {len(names)} distinct catalyst names",
     pd.Series([kind_of(n) for n in names]).value_counts(), fmt="{:.0f}")

rejected = scored().query("verdict == 'MISMATCH' and catalyst_match == False")
pairs = pd.DataFrame({"curated": [f["catalyst"]["curated"] for f in rejected.fields],
                      "extracted": [f["catalyst"]["extracted"] for f in rejected.fields]})
pairs["kinds"] = [f"{kind_of(a)} / {kind_of(b)}" for a, b in zip(pairs.curated, pairs.extracted)]

show(f"the {len(pairs)} pairs rejected on the name", pairs.kinds.value_counts(), fmt="{:.0f}")
both_plain = pairs[pairs.kinds == "plain chemical name / plain chemical name"]
show(f"both names ordinary -- mispaired, not misnamed ({len(both_plain)})",
     both_plain[["curated", "extracted"]].reset_index(drop=True))
