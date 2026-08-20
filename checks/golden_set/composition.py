import hashlib
from _setup import *

labelled = golden()
checksum = hashlib.sha256(golden_set_file.read_bytes()).hexdigest()
by_split = pd.crosstab(labelled.split, labelled.human)
revised = labelled.correction.notna().sum()

print("records ", len(labelled))
print("papers  ", labelled.doi.nunique())
print("sha256  ", checksum)
print()
print("labels by split:")
print(by_split.to_string())
print()
print("Two chemists labelled the records independently, without seeing either grader's verdict.")
print("They judged one question: is this record a faithful rendering of one experiment the paper")
print("actually reports?")
print()
print("The split was fixed before the final judge rubric was written, so the test half is a clean")
print("estimate of anything decided while looking at the other half.")
print()
print(revised, "labels were revised once the criteria were settled; the reasons are recorded in")
print("the correction field of each record.")
