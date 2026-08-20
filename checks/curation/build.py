from _setup import *
from _curation import *

raw = json.loads(data_path(as_curated).read_text())
started_with = sum(len(paper["extracted_experiments"]) for paper in raw)

papers = cleaned_papers()
removed = started_with - sum(len(paper["extracted_experiments"]) for paper in papers)
total = write_version(curated_table, papers)

print("hand-curated experiments    ", started_with)
print("entered twice or no outcome ", -removed)
print("curated table               ", total)
