"""Stage 1 of the corpus build: find every candidate, keep them all, then filter on record.

Searching Scopus for PET depolymerisation also returns positron-emission tomography and tumour
glycolysis, so a filter is unavoidable. Writing every candidate to disk with the reason it was kept
or dropped makes the funnel reportable -- how many papers the searches found, how many survived,
and why the rest did not -- instead of a number that has to be taken on trust.

Fetching full text is stage 2 (cli/fetch_elsevier.py --dois-from), so nothing is downloaded until
after the filter has run.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.paths import data_path
from cli.fetch_elsevier import credentials, worth_fetching

SCOPUS = "https://api.elsevier.com/content/search/scopus"

QUERIES = [
    'TITLE-ABS-KEY("poly(ethylene terephthalate)" AND glycolysis)',
    'TITLE-ABS-KEY(PET AND glycolysis AND (catalyst OR BHET OR monomer))',
    'TITLE-ABS-KEY("poly(ethylene terephthalate)" AND (methanolysis OR alcoholysis))',
    'TITLE-ABS-KEY(PET AND methanolysis AND (catalyst OR DMT OR dimethyl OR monomer))',
    'TITLE-ABS-KEY("poly(ethylene terephthalate)" AND hydrolysis)',
    'TITLE-ABS-KEY(PET AND hydrolysis AND (catalyst OR TPA OR terephthalic OR monomer))',
    'TITLE-ABS-KEY("poly(ethylene terephthalate)" AND depolymeriz*)',
    'TITLE-ABS-KEY(PET AND "chemical recycling" AND (BHET OR DMT OR TPA OR monomer))',
    'TITLE-ABS-KEY(BHET OR "bis(2-hydroxyethyl) terephthalate")',
    'TITLE-ABS-KEY(PET AND solvolysis)',
]


def fetch_page(query, start, headers, per_page=25):
    url = (f"{SCOPUS}?query={urllib.parse.quote(query)}"
           f"&count={per_page}&start={start}&field=doi,dc:title,dc:description,prism:publicationName")
    for attempt in range(4):
        req = urllib.request.Request(url, headers={**headers, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read())["search-results"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(5 * 2 ** attempt)
                continue
            return None
        except Exception:
            if attempt < 3:
                time.sleep(5 * 2 ** attempt)
                continue
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-query", type=int, default=2000)
    ap.add_argument("--out", default="corpus_candidates.csv")
    args = ap.parse_args()

    headers = credentials()
    seen = {}

    for query in QUERIES:
        start, taken = 0, 0
        while taken < args.max_per_query:
            page = fetch_page(query, start, headers)
            if not page:
                break
            entries = page.get("entry", [])
            if not entries:
                break
            for e in entries:
                doi = e.get("prism:doi")
                if not doi:
                    continue
                if doi not in seen:
                    seen[doi] = {"doi": doi,
                                 "title": (e.get("dc:title") or "").replace("\n", " "),
                                 "abstract": (e.get("dc:description") or "").replace("\n", " ")[:600],
                                 "journal": e.get("prism:publicationName") or "",
                                 "queries": []}
                seen[doi]["queries"].append(query.split("(")[1][:28])
            taken += len(entries)
            start += len(entries)
            total = int(page.get("opensearch:totalResults", 0))
            print(f"  {query[:52]:54s} {min(taken, total):5d}/{total}", end="\r")
            if start >= total:
                break
            time.sleep(0.2)
        print(f"  {query[:52]:54s} {taken:5d} collected")

    rows = []
    for entry in seen.values():
        # the filter reads title and abstract together, so a bare title still gets a fair chance
        keep, why = worth_fetching(f"{entry['title']} {entry['abstract']}")
        rows.append({**entry, "queries": "|".join(sorted(set(entry["queries"]))),
                     "keep": keep, "reason": why})

    out = data_path(args.out)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["doi", "keep", "reason", "title", "journal",
                                                "queries", "abstract"])
        writer.writeheader()
        writer.writerows(rows)

    kept = sum(r["keep"] for r in rows)
    print(f"\n{'=' * 66}\nFUNNEL")
    print(f"  candidates found by {len(QUERIES)} searches   {len(rows):6d}")
    reasons = {}
    for r in rows:
        if not r["keep"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    dropped, {why:32s} {n:6d}")
    print(f"  passed the title/abstract filter    {kept:6d}   ({kept / len(rows):.1%})")
    print(f"\nwrote {out}")
    print("next: cli/fetch_elsevier.py --dois-from " + args.out)


if __name__ == "__main__":
    main()
