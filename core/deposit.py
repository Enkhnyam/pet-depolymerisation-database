import json
import shutil
from pathlib import Path

from .licensing import licensable_dois
from .paths import resolve, data_path
from .utils import filename_to_doi

def sanitize_run(run_dir: Path, out_dir: Path) -> dict:
    """Copy one run bundle to out_dir, keeping raw/ only for licensable papers."""
    allowed = licensable_dois()
    out_dir.mkdir(parents=True, exist_ok=True)

    for src_file in run_dir.glob("*.json"):
        shutil.copy2(src_file, out_dir / src_file.name)

    if (run_dir / "extractions").exists():
        shutil.copytree(run_dir / "extractions", out_dir / "extractions", dirs_exist_ok=True)

    kept = dropped = 0
    for raw_file in sorted((run_dir / "raw").glob("*.json")):
        if filename_to_doi(raw_file.name) in allowed:
            (out_dir / "raw").mkdir(exist_ok=True)
            shutil.copy2(raw_file, out_dir / "raw" / raw_file.name)
            kept += 1
        else:
            dropped += 1
    return kept, dropped


def sanitize_curated(curated_path: str, out_path: Path) -> None:
    """Write a public curated dataset: keep records (facts) for all papers, but
    drop full_text for non-licensable papers."""
    allowed = licensable_dois()
    data = json.loads(data_path(curated_path).read_text(encoding="utf-8"))
    for paper in data:
        if paper["doi"] not in allowed:
            paper.pop("full_text", None)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_credits(out_path: Path) -> None:
    """Generate the attribution file (both CC-BY and CC-BY-NC-SA require it)."""
    entries = json.loads(resolve("licenses.json").read_text(encoding="utf-8"))
    lines = ["# Credits & Licenses", "",
             "Redistributed source-paper content (full text and derived few-shot "
             "exemplars) is used under the following open licenses, with attribution:", ""]
    for e in entries:
        lines += [f"- **{e['title']}**",
                  f"  - DOI: https://doi.org/{e['doi']}",
                  f"  - License: {e['license']} — {e['permissions']}", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
