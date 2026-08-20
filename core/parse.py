import uuid
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem, TextItem

NS = uuid.UUID("f3c1e5d0-8b6e-4f9a-9c2b-1e5d0f8b6e4f")

def parse_src_dest_directories(src: Path, dest: Path) -> tuple[list[str], int]:
    dest.mkdir(parents=True, exist_ok=True)
    converter = DocumentConverter()
    pdf_files = list(src.glob("*.pdf"))
    parsed_files = list(pdf.stem for pdf in dest.glob("*.md"))

    s, p = 0, 0
    for pdf in sorted(pdf_files):
        if pdf.stem in parsed_files:
            print(f"skipping {pdf.name} (already parsed)")
            s += 1
            continue
        print(f"parsing {pdf.name}...")
        doc = converter.convert(pdf).document
        out = []
        for i, (item, _) in enumerate(doc.iterate_items()):
            if isinstance(item, TableItem):
                text = item.export_to_markdown(doc).strip()
            elif isinstance(item, TextItem):
                text = (item.text or "").strip()
            else:
                continue
            if not text:
                continue
            cid = uuid.uuid5(NS, f"{pdf.stem}|{i}|{text}")
            out.append(f"ID: {cid}\n{text}\n")
            p += 1
        parsed_files.append(pdf.stem)
        out_text = "\n".join(out).replace("\x00", "")
        (dest / f"{pdf.stem}.md").write_text(out_text)
    print(f"processed {len(parsed_files)} files ({s} skipped, {p} parsed)")
    return parsed_files, len(parsed_files)

def run(src: str, dest: str) -> None:
    if not src or not dest:
        raise ValueError("Both --src and --dest must be provided for parsing stage.")
    parse_src_dest_directories(Path(src), Path(dest))