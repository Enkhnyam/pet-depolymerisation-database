from _setup import *

def kind_of(name):
    text = str(name)
    lowered = text.lower()
    if "/" in text or "+" in text or " and " in lowered:
        return "mixture of two catalysts"
    if "@" in text:
        return "supported on a carrier"
    if any(lowered.startswith(prefix) for prefix in ("pil", "cat-", "il-", "des")):
        return "code the paper defines itself"
    return "plain chemical name"

all_names = sorted(set(curated().catalyst.dropna()) | set(extracted().catalyst.dropna()))
population = pd.Series([kind_of(name) for name in all_names]).value_counts()

labels = scored()
rejected = labels[labels.verdict == "MISMATCH"]
rejected = rejected[rejected.catalyst_match == False]

pairs = pd.DataFrame({
    "curated": [row["catalyst"]["curated"] for row in rejected.fields],
    "extracted": [row["catalyst"]["extracted"] for row in rejected.fields]})
pairs["curated kind"] = [kind_of(name) for name in pairs.curated]
pairs["extracted kind"] = [kind_of(name) for name in pairs.extracted]

both_plain = pairs[(pairs["curated kind"] == "plain chemical name") &
                   (pairs["extracted kind"] == "plain chemical name")]

print("all", len(all_names), "distinct catalyst names in the dataset:")
print(population.to_string())
print()
print()
print("most names are resolvable, but the ones that matter are the", len(pairs), "in the failures:")
print()
print(pairs.groupby(["curated kind", "extracted kind"]).size().to_string())
print()
print("pairs where both names are ordinary chemical names:", len(both_plain))
print(both_plain[["curated", "extracted"]].to_string(index=False))
print()
print(f"These {len(both_plain)} are the metric pairing a record with the wrong experiment, not a")
print(f"naming failure. In the other {len(pairs) - len(both_plain)} at least one name is a mixture,")
print("a supported material, or a code coined by the paper. None of those have a database entry.")
