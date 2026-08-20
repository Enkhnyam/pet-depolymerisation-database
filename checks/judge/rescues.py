from _setup import *

labels = scored()
rejected = labels[labels.verdict == "MISMATCH"]
rejected = rejected[rejected.catalyst_match == False]

names = pd.DataFrame({"doi": rejected.doi,
                      "index": rejected.extracted_index,
                      "curated": rejected.fields.map(lambda f: f["catalyst"]["curated"]),
                      "extracted": rejected.fields.map(lambda f: f["catalyst"]["extracted"])})
with_verdicts = names.merge(golden()[["doi", "extracted_index", "judge_v4", "human"]],
                            left_on=["doi", "index"], right_on=["doi", "extracted_index"])
comparison = with_verdicts[["judge_v4", "human", "curated", "extracted"]]
comparison.columns = ["judge", "chemists", "curated", "extracted"]
agreement = pd.crosstab(comparison.judge, comparison.chemists)

print(len(rejected), "matches rejected because the two catalyst names differ")
print("all of them were labelled by the chemists")
print()
print(comparison.to_string(index=False))
print()
print("judge against the chemists on these records:")
print(agreement.to_string())
print()
print("Where both say correct, the two names are the same substance written differently and the")
print("metric was wrong to reject. Where both say incorrect, the extracted name is a placeholder")
print("that identifies no substance, so rejecting it was right for the wrong reason.")
