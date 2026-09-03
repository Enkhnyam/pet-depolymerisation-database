"""Download Elsevier full-text XML only. Conversion is a separate step (cli/build_corpus.py),
so the whole corpus can be re-chunked without re-downloading anything."""
import argparse, csv, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from core.paths import data_path
from cli.fetch_elsevier import credentials, request, QUOTA

OUT = ROOT / "download_data_xml" / "elsevier"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-csv", default="corpus_candidates.csv")
    args = ap.parse_args()
    headers = credentials()
    OUT.mkdir(parents=True, exist_ok=True)
    with data_path(args.from_csv).open(encoding="utf-8") as fh:
        wanted = [r["doi"] for r in csv.DictReader(fh)
                  if r["keep"].lower() == "true" and r["doi"].startswith("10.1016")]
    have = {p.name.replace(".xml", "").replace("@", "/").lower() for p in OUT.glob("*.xml")}
    todo = [d for d in wanted if d.lower() not in have]
    print(f"{len(wanted)} Elsevier candidates, {len(wanted) - len(todo)} already downloaded, "
          f"{len(todo)} to fetch\n")
    got = failed = 0
    reasons = {}
    for doi in todo:
        status, body = request(f"https://api.elsevier.com/content/article/doi/{doi}?view=FULL",
                               headers, "text/xml")
        if status == 200 and len(body) > 20000:
            (OUT / (doi.replace("/", "@") + ".xml")).write_bytes(body)
            got += 1
            if got % 25 == 0: print(f"  {got} downloaded", flush=True)
        else:
            failed += 1
            reasons[str(status)] = reasons.get(str(status), 0) + 1
        time.sleep(0.15)
    print(f"\ndownloaded {got} | failed {failed}  {reasons}")
    if QUOTA["remaining"]: print(f"quota left: {QUOTA['remaining']}/{QUOTA['limit']}")

if __name__ == "__main__":
    main()
