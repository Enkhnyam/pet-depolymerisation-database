"""Convert the corpus to the chunked markdown the extractor reads, using this repo's own parsers.

Every paper goes through src.parser.Parser with identifier_source_tracking, which is what produces
the "ID: <uuid>" markers source_chunk_ids refers to. One parser for the whole corpus, so no paper
is chunked differently from its neighbours: Elsevier XML through the Elsevier reader, PDFs through
docling.

    build_corpus.py --from-csv corpus_candidates.csv           # the filtered Elsevier candidates
    build_corpus.py --from-csv corpus_candidates.csv --pdf     # the open-access PDFs instead
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import sett
from src.parser import Parser
from core.paths import data_path
from core.utils import doi_to_filename

XML_DIR = ROOT / "download_data_xml" / "elsevier"
PDF_DIR = ROOT / "download_data_pdf"


def index_of(directory, suffixes):
    """doi -> file, keyed on the @-escaped filenames this repo already uses."""
    found = {}
    for suffix in suffixes:
        for path in directory.glob(f"*{suffix}"):
            doi = path.name[: -len(suffix)].replace("@", "/").lower()
            found[doi] = path
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-csv", default="corpus_candidates.csv")
    ap.add_argument("--pdf", action="store_true", help="convert PDFs with docling instead of XML")
    ap.add_argument("--out", default="corpus_markdown")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    # Chosen globally in settings before any Parser is built. src/sett/sections.py defaults to
    # paragraph/1000, which collapses a whole paper into a handful of chunks and makes
    # source_chunk_ids meaningless, so the values settings.yaml intends are set explicitly.
    sett.Parser.reader = "docling" if args.pdf else "elsevier"
    sett.Parser.splitter = "sentence"
    sett.Parser.chunk_size = 10
    sett.Parser.chunk_overlap = 0
    available = (index_of(PDF_DIR, [".pdf", ".PDF"]) if args.pdf
                 else index_of(XML_DIR, [".xml", ".XML"]))

    with data_path(args.from_csv).open(encoding="utf-8") as fh:
        wanted = [r["doi"].lower() for r in csv.DictReader(fh) if r["keep"].lower() == "true"]

    out_dir = data_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [d for d in wanted if d in available]
    missing = [d for d in wanted if d not in available]
    print(f"reader        {sett.Parser.reader}  splitter {sett.Parser.splitter}/"
          f"{sett.Parser.chunk_size}")
    print(f"wanted        {len(wanted)} papers that passed the filter")
    print(f"available     {len(todo)} have a source file here")
    print(f"no file       {len(missing)}\n")
    if args.limit:
        todo = todo[: args.limit]

    done = skipped = failed = 0
    problems = []
    for doi in todo:
        target = out_dir / doi_to_filename(doi, "md")
        if target.exists():
            skipped += 1
            continue
        try:
            parser = Parser(directory="doi named", filepath=str(available[doi]),
                            identifier_source_tracking=True)
            parser.parse()
            text = parser.full_text
            if not text or len(parser.chunks) < 5:
                problems.append((doi, f"only {len(parser.chunks)} chunks"))
                failed += 1
                continue
            target.write_text(text, encoding="utf-8")
            done += 1
            if done % 25 == 0:
                print(f"  {done} converted", flush=True)
        except Exception as e:
            problems.append((doi, f"{type(e).__name__}: {str(e)[:60]}"))
            failed += 1

    print(f"\nconverted {done} | already present {skipped} | failed {failed}")
    print(f"wrote {out_dir}")
    for doi, why in problems[:10]:
        print(f"  FAILED {doi}: {why}")


if __name__ == "__main__":
    main()
