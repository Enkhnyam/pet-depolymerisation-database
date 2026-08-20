from sklearn.metrics import cohen_kappa_score
from _setup import *

labelled = golden()
graders = {"judge": "judge_v4", "metric": "metric"}
splits = {"all": labelled,
          "dev": labelled[labelled.split == "dev"],
          "test (held out)": labelled[labelled.split == "test"]}

agreement = {}
kappa = {}
for split_name, part in splits.items():
    agreement[split_name] = {}
    kappa[split_name] = {}
    for grader_name, column in graders.items():
        agreement[split_name][grader_name] = (part.human == part[column]).mean()
        kappa[split_name][grader_name] = cohen_kappa_score(part.human, part[column])

sizes = {name: len(part) for name, part in splits.items()}

print("raw agreement")
print(pd.DataFrame(agreement).to_string(float_format="{:.0%}".format))
print()
print("Cohen's kappa")
print(pd.DataFrame(kappa).to_string(float_format="{:+.2f}".format))
print()
print("records per split", sizes)
