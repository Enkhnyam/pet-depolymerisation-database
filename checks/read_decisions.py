import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import review_curation as candidates

FIELDS = candidates.FIELDS

if len(sys.argv) < 2:
    print("usage: uv run python checks/read_decisions.py <curation_decisions.json>")
    raise SystemExit(1)

saved = json.loads(Path(sys.argv[1]).read_text())
decisions = saved.get("clusters", {})
paper_notes = saved.get("papers", {})
labels = saved.get("refersTo", {})

known = {}
for doi, paper in candidates.payload.items():
    for cluster in paper["clusters"]:
        known[cluster["id"]] = (paper["doi"], cluster)

print(f"file          {Path(sys.argv[1]).name}")
print(f"format        version {saved.get('version', 1)}")
print(f"decisions     {len(decisions)}")
print(f"paper notes   {len(paper_notes)}")

matched = [k for k in decisions if k in known]
orphans = [k for k in decisions if k not in known]
print(f"still valid   {len(matched)}")
print(f"orphaned      {len(orphans)}")

if orphans:
    print("\nThese refer to experiments that no longer exist. The source data changed after they")
    print("were recorded, so each needs deciding again:")
    for key in orphans:
        print(f"  {key}  {labels.get(key, '(no description saved)')}")

print("\n" + "=" * 78)
print("WHAT WAS DECIDED")
print("=" * 78)

by_paper = {}
for key in matched:
    doi, cluster = known[key]
    by_paper.setdefault(doi, []).append((key, cluster, decisions[key]))

if not by_paper:
    print("Nothing yet.")

for doi in sorted(by_paper):
    print(f"\n{doi}")
    for key, cluster, choice in by_paper[doi]:
        default_keep = cluster["suggested"]
        default_variant = cluster["prefer"]
        keep = choice.get("keep", default_keep)
        variant = choice.get("variant", default_variant)
        edits = choice.get("edits") or {}

        changes = []
        if keep != default_keep:
            changes.append("EXCLUDED (was going to be kept)" if not keep
                           else "INCLUDED (was going to be dropped)")
        if variant != default_variant:
            changes.append(f"takes values from {cluster['variants'][variant]['origin']} "
                           f"instead of {cluster['variants'][default_variant]['origin']}")
        for field, value in edits.items():
            was = cluster["variants"][variant]["values"].get(field)
            changes.append(f"{field}: {was!r} -> {value!r}")

        mark = "keep" if keep else "drop"
        print(f"  [{mark}] {cluster['label']}")
        print(f"         sources: {', '.join(cluster['origins'])}")
        if changes:
            for change in changes:
                print(f"         {change}")
        else:
            print("         confirmed as suggested")

if paper_notes:
    print("\n" + "=" * 78)
    print("PAPER NOTES")
    print("=" * 78)
    for doi, note in sorted(paper_notes.items()):
        bits = []
        if note.get("skip"):
            bits.append("EXCLUDED FROM THE PROJECT")
        if note.get("note"):
            bits.append(note["note"])
        if bits:
            print(f"  {candidates.display_doi.get(doi, doi)}: {' | '.join(bits)}")

print("\n" + "=" * 78)
print("RESULTING DATASET, IF EXPORTED NOW")
print("=" * 78)

kept = 0
papers_kept = 0
edited = 0
for doi, paper in candidates.payload.items():
    if (paper_notes.get(doi) or {}).get("skip"):
        continue
    rows = 0
    for cluster in paper["clusters"]:
        choice = decisions.get(cluster["id"], {})
        if choice.get("keep", cluster["suggested"]):
            rows += 1
            if choice.get("edits"):
                edited += 1
    kept += rows
    if rows:
        papers_kept += 1

print(f"experiments   {kept}")
print(f"papers        {papers_kept}")
print(f"hand-edited   {edited}")
print(f"\nUndecided candidates fall back to the suggestion, so this number is complete whether or")
print(f"not every card has been visited.")
