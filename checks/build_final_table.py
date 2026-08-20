import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _setup import data_path, curated_table
from review_curation import clean_name, clean_solvent, FIELDS

MERGED = "curated_table_merged.json"
FINAL = "curated_table_final.json"

papers = json.loads(data_path(MERGED).read_text())
established = json.loads(data_path(curated_table).read_text())

# Notation already settled in the table we have been using wins, so the reviews' spellings are
# brought into line with ours rather than the other way round. Only spelling changes here: two
# names that survive clean_name() identically are the same substance written differently.
def preferred(field):
    settled = collections.Counter()
    for paper in established:
        for entry in paper["extracted_experiments"]:
            value = entry["experiment_data"].get(field)
            if value:
                settled[value] += 1
    everywhere = collections.Counter()
    for paper in papers:
        for entry in paper["extracted_experiments"]:
            value = entry["experiment_data"].get(field)
            if value:
                everywhere[value] += 1

    key = clean_name if field == "catalyst" else clean_solvent
    groups = collections.defaultdict(set)
    for value in everywhere:
        groups[key(value)].add(value)

    choice = {}
    for spellings in groups.values():
        if len(spellings) == 1:
            continue
        winner = max(spellings, key=lambda s: (settled.get(s, 0), everywhere[s]))
        for spelling in spellings:
            if spelling != winner:
                choice[spelling] = winner
    return choice


renames = {field: preferred(field) for field in ("catalyst", "solvent")}

changed = collections.Counter()
for paper in papers:
    for entry in paper["extracted_experiments"]:
        data = entry["experiment_data"]
        for field, mapping in renames.items():
            value = data.get(field)
            if value in mapping:
                data[field] = mapping[value]
                changed[field] += 1

data_path(FINAL).write_text(json.dumps(papers, indent=2))

total = sum(len(p["extracted_experiments"]) for p in papers)
print("NOTATION UNIFIED")
for field, mapping in renames.items():
    print(f"  {field}: {len(mapping)} spellings folded, {changed[field]} rows rewritten")
    for old, new in sorted(mapping.items()):
        print(f"      {old!r} -> {new!r}")

print(f"\nFINAL TABLE")
print(f"  experiments {total}")
print(f"  papers      {len(papers)}")

untraceable = [(p["doi"], e["experiment_data"].get("catalyst"))
               for p in papers for e in p["extracted_experiments"]
               if not e["experiment_data"].get("source_chunk_ids")]
print(f"\n  rows with no link back to the paper text: {len(untraceable)}")
print("  These came from the published reviews rather than our own extraction, so nothing")
print("  points at where in the paper they are stated.")
for doi, catalyst in untraceable[:6]:
    print(f"      {doi}  {catalyst}")
if len(untraceable) > 6:
    print(f"      ... and {len(untraceable) - 6} more")

leftover = collections.defaultdict(set)
for paper in papers:
    for entry in paper["extracted_experiments"]:
        value = entry["experiment_data"].get("catalyst")
        if value:
            leftover[clean_name(value)].add(value)
still = {k: v for k, v in leftover.items() if len(v) > 1}
print(f"\n  substances still written more than one way: {len(still)}")
print(f"\nwrote {data_path(FINAL)}")
