"""Do the records point at text that exists?

Every record cites the chunk ids it was read from, which is what lets a reader check a number
against the sentence it came from. A citation that matches no chunk breaks that promise, so it
is worth counting rather than assuming.
"""
import glob
import json
import re
from pathlib import Path

from _setup import DATABASE, show, sources
from core.licensing import licensable_dois
from core.paths import data_path
from core.utils import doi_to_filename

CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)


def chunk_ids(markdown_dir: Path, doi: str) -> set:
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    if not path.exists():
        return set()
    return set(CHUNK_PATTERN.findall(path.read_text(encoding="utf-8")))


def compute() -> dict:
    """Whether each cited chunk resolves to text in the paper it belongs to."""
    corpus = data_path("corpus_markdown")

    # ids belonging to the worked examples, to spot the model copying them into its answer
    demo_dir = data_path("curated_data_markdown_by_doi")
    demo_ids = set()
    for doi in licensable_dois():
        demo_ids |= chunk_ids(demo_dir, doi)

    total = valid = from_demos = invented = 0
    papers_affected = set()

    for path in glob.glob(str(DATABASE / "extractions/*.json")):
        paper = json.loads(Path(path).read_text())
        own = chunk_ids(corpus, paper["doi"])
        if not own:
            continue
        for record in paper["records"]:
            for cited in record.get("source_chunk_ids") or []:
                total += 1
                if cited in own:
                    valid += 1
                elif cited in demo_ids:
                    from_demos += 1
                    papers_affected.add(paper["doi"])
                else:
                    invented += 1
                    papers_affected.add(paper["doi"])

    return {"counts": {"total": total,
                       "resolve to the paper's own text": valid,
                       "copied from a worked example": from_demos,
                       "match no chunk anywhere": invented,
                       "papers affected": len(papers_affected)},
            "traceable": valid / total if total else 0}


def main() -> None:
    sources(corpus="corpus_markdown", extraction=DATABASE)
    result = compute()
    show("chunk citations", result["counts"], fmt="{:.0f}")
    print(f"\n{result['traceable']:.1%} of citations are traceable")


if __name__ == "__main__":
    main()
