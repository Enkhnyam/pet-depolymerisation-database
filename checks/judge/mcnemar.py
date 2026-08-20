from scipy.stats import binomtest
from _setup import *

labelled = golden()
splits = {"all": labelled, "test (held out)": labelled[labelled.split == "test"]}

comparison = {}
for split_name, part in splits.items():
    judge_alone = ((part.judge_v4 == part.human) & (part.metric != part.human)).sum()
    metric_alone = ((part.metric == part.human) & (part.judge_v4 != part.human)).sum()
    p_value = binomtest(judge_alone, judge_alone + metric_alone).pvalue
    comparison[split_name] = {"records": len(part),
                              "only the judge right": judge_alone,
                              "only the metric right": metric_alone,
                              "p": p_value}

print(pd.DataFrame(comparison).T.to_string(float_format="{:.4f}".format))
print()
print("The test split was fixed before the final rubric was written, so it is held out.")
print()
print("Records where both graders agree carry no information about which is better, so the test")
print("uses only the ones where exactly one of them matched the chemists.")
print()

discordant = int(comparison["all"]["only the judge right"] + comparison["all"]["only the metric right"])
print(f"informative records: {discordant} of {len(labelled)} ({discordant / len(labelled):.1%})")
print()
print("smallest p reachable at a given number of informative records, if every one of them")
print("favoured the same grader:")
for count in range(2, 9):
    best = binomtest(count, count).pvalue
    mark = "  <- first count that could reach 0.05" if best < 0.05 <= binomtest(count - 1, count - 1).pvalue else ""
    print(f"  {count}: p = {best:.4f}{mark}")
print()
print(f"With {discordant} informative records the smallest p available is "
      f"{binomtest(discordant, discordant).pvalue:.3f}, so no result on this labelled set can reach")
print("significance however the records fall. The finding is that the set is too small to settle")
print("the question, not that the two graders are equally good.")
print()
print("how many informative records the observed 3:1 split would need:")
for count in [4, 8, 12, 16, 20]:
    favouring = round(count * 0.75)
    p_value = binomtest(favouring, count).pvalue
    print(f"  {favouring} of {count}: p = {p_value:.3f}" + ("  <- significant" if p_value < 0.05 else ""))
print()
print(f"At the observed rate that would take roughly "
      f"{round(20 / (discordant / len(labelled)) / 10) * 10} labelled records, about five times what")
print("we have. Labelling more of this corpus is one route; a corpus where the two graders disagree")
print("more often is the cheaper one.")
