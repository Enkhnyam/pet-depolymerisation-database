"""Paste each figure's generated caption into paper.tex, replacing the one already there.

The figure modules print a caption built from the same checks that draw the panels, so a number
in a caption cannot drift from the number in the figure. That guarantee stopped at the clipboard:
paper.tex held whatever caption was pasted the last time somebody remembered, and after the
database was rebuilt it described a corpus of 451 papers under figures drawn from 1,026 --- median
5 and "largest 75" against a panel running to 84, "527 distinct names" against 1,110.

This closes that gap, so the guarantee reaches the page.

Captions are collapsed to one line: a blank line inside \\caption{} starts a paragraph, which
LaTeX refuses in a float.

    sync_captions.py            rewrite paper.tex
    sync_captions.py --check    report drift and change nothing (exit 1 if any)
"""
import argparse
import io
import re
import runpy
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "figures"))
sys.path.insert(0, str(ROOT / "checks"))

FIGURES = ["fig1_database", "fig2_chemistry", "fig3_graders", "fig4_choices"]

# Both manuscripts get the same captions. paper_rsc.tex previously carried its own hand-written
# ones in the "(a) the funnel; (b) records per paper" style, which described a panel layout two
# revisions old -- eight panels for a figure that now has six.
PAPERS = [ROOT / "paper.tex", ROOT / "paper_rsc.tex", ROOT / "paper_rsc_si.tex"]


def generated(name: str) -> str:
    """Run the figure module and keep what it printed after the 'wrote ...' line."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        runpy.run_path(str(ROOT / "figures" / f"{name}.py"), run_name="__main__")
    text = buffer.getvalue()
    _, _, caption = text.partition(f"{name}.pdf\n")
    return re.sub(r"\s+", " ", caption).strip()


def replace(source: str, name: str, caption: str) -> tuple[str, bool]:
    """Swap the caption of the float that includes this figure. Absent figure, no change."""
    anchor = source.find(f"{{artifacts/figures/{name}.pdf}}")
    if anchor < 0:
        return source, False
    start = source.find("\\caption{", anchor)
    label = source.find("\\label{", anchor)
    if start < 0 or label < 0 or label < start:
        raise SystemExit(f"no \\caption{{...}}\\label{{...}} after {name}.pdf")
    end = source.rfind("}", start, label)          # the caption's closing brace
    new = f"\\caption{{{caption}}}"
    if source[start:end + 1] == new:
        return source, False
    return source[:start] + new + source[end + 1:], True


def main() -> None:
    parser = argparse.ArgumentParser(prog="sync_captions")
    parser.add_argument("--check", action="store_true",
                        help="report which captions are stale, write nothing")
    args = parser.parse_args()

    # generated once, pasted into every manuscript: running each figure twice would be slow and
    # could in principle differ, and the whole point is that they cannot
    captions = {name: generated(name) for name in FIGURES}

    total = 0
    for paper in PAPERS:
        if not paper.exists():
            continue
        source = paper.read_text(encoding="utf-8")
        stale = []
        for name, caption in captions.items():
            source, changed = replace(source, name, caption)
            if changed:
                stale.append(name)
        print(f"{paper.name}")
        for name in FIGURES:
            state = ("updated" if name in stale
                     else "absent" if f"{{artifacts/figures/{name}.pdf}}" not in source
                     else "already current")
            print(f"  {name:16s} {state}")
        if stale and not args.check:
            paper.write_text(source, encoding="utf-8")
            print(f"  -> rewrote {paper.name} ({len(stale)} caption(s))")
        total += len(stale)

    if args.check:
        print(f"\n{total} caption(s) differ from the figures" if total
              else "\nevery caption matches its figure")
        raise SystemExit(1 if total else 0)
    if not total:
        print("\nno manuscript needed changing")


if __name__ == "__main__":
    main()
