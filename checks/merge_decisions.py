import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import review_curation as candidates

FIELDS = candidates.FIELDS

if len(sys.argv) < 2:
    print("usage: uv run python checks/merge_decisions.py <decisions.json> [more.json ...]")
    raise SystemExit(1)

files = [Path(p) for p in sys.argv[1:]]
known = {c["id"]: (paper["doi"], c) for paper in candidates.payload.values()
         for c in paper["clusters"]}

merged, papers, source_of = {}, {}, {}
conflicts = []

for path in files:
    saved = json.loads(path.read_text())
    for key, choice in saved.get("clusters", {}).items():
        if key in merged and merged[key] != choice:
            conflicts.append((key, source_of[key], merged[key], path.name, choice))
            continue
        merged[key] = choice
        source_of[key] = path.name
    for doi, note in saved.get("papers", {}).items():
        if doi in papers:
            existing = papers[doi]
            papers[doi] = {"skip": existing.get("skip") or note.get("skip"),
                           "note": " | ".join(x for x in (existing.get("note"), note.get("note")) if x)}
        else:
            papers[doi] = note

print("MERGING")
for path in files:
    saved = json.loads(path.read_text())
    print(f"  {path.name}: {len(saved.get('clusters', {}))} decisions, "
          f"{len(saved.get('papers', {}))} paper notes")
print(f"  -> {len(merged)} decisions, {len(papers)} paper notes")

orphans = [k for k in merged if k not in known]
if orphans:
    print(f"\n{len(orphans)} decisions no longer match any experiment and were dropped.")

if conflicts:
    print(f"\n{len(conflicts)} CONFLICTS — the same experiment decided two different ways.")
    print("These are kept as the first reviewer's answer and need settling by hand:")
    for key, first_file, first, second_file, second in conflicts:
        doi, cluster = known.get(key, ("?", {"label": key}))
        print(f"  {doi}  {cluster['label']}")
        print(f"    {first_file}: {first}")
        print(f"    {second_file}: {second}")
else:
    print("\nNo conflicts: no experiment was decided differently by two reviewers.")

reviewed_papers = {known[k][0] for k in merged if k in known}
print(f"\nCOVERAGE")
print(f"  papers with at least one decision : {len(reviewed_papers)} of {len(candidates.payload)}")
print(f"  papers still untouched            : {len(candidates.payload) - len(reviewed_papers)}")

out_state = {"version": 2, "clusters": merged, "papers": papers,
             "refersTo": {k: f"{known[k][0]}  {known[k][1]['label']}"
                          for k in merged if k in known}}
state_path = candidates.ARTIFACTS / "data" / "curation_decisions_merged.json"
state_path.write_text(json.dumps(out_state, indent=2))

table = []
kept = edited = 0
for doi, paper in candidates.payload.items():
    if (papers.get(doi) or {}).get("skip"):
        continue
    rows = []
    for cluster in paper["clusters"]:
        choice = merged.get(cluster["id"], {})
        if not choice.get("keep", cluster["suggested"]):
            continue
        variant = cluster["variants"][choice.get("variant", cluster["prefer"])]
        values = dict(variant["values"])
        values.update(choice.get("edits") or {})
        if choice.get("edits"):
            edited += 1
        chunks = []
        for v in cluster["variants"]:
            for chunk in v.get("chunks") or []:
                if chunk not in chunks:
                    chunks.append(chunk)
        experiment = {f: values.get(f) for f in FIELDS}
        experiment["source_chunk_ids"] = chunks
        rows.append({"experiment_data": experiment})
    kept += len(rows)
    if rows:
        table.append({"doi": paper["doi"], "title": paper["title"],
                      "extracted_experiments": rows})

table_path = candidates.ARTIFACTS / "data" / "curated_table_merged.json"
table_path.write_text(json.dumps(table, indent=2))

print(f"\nRESULT")
print(f"  experiments  {kept}")
print(f"  papers       {len(table)}")
print(f"  hand-edited  {edited}")
print(f"\nwrote {state_path}")
print(f"wrote {table_path}")
