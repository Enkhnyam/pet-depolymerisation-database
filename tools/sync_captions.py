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
PAPER = ROOT / "paper.tex"


def generated(name: str) -> str:
    """Run the figure module and keep what it printed after the 'wrote ...' line."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        runpy.run_path(str(ROOT / "figures" / f"{name}.py"), run_name="__main__")
    text = buffer.getvalue()
    _, _, caption = text.partition(f"{name}.pdf\n")
    return re.sub(r"\s+", " ", caption).strip()


def replace(source: str, name: str, caption: str) -> tuple[str, bool]:
    """Swap the caption of the float that includes this figure."""
    anchor = source.find(f"{{artifacts/figures/{name}.pdf}}")
    if anchor < 0:
        raise SystemExit(f"paper.tex does not include {name}.pdf")
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

    source = PAPER.read_text(encoding="utf-8")
    stale = []
    for name in FIGURES:
        caption = generated(name)
        source, changed = replace(source, name, caption)
        if changed:
            stale.append(name)
        print(f"  {name:16s} {'updated' if changed else 'already current'}")

    if args.check:
        print(f"\n{len(stale)} caption(s) differ from the figures" if stale
              else "\nevery caption matches its figure")
        raise SystemExit(1 if stale else 0)

    if stale:
        PAPER.write_text(source, encoding="utf-8")
        print(f"\nrewrote {PAPER.relative_to(ROOT)} ({len(stale)} caption(s))")
    else:
        print(f"\n{PAPER.relative_to(ROOT)} unchanged")


if __name__ == "__main__":
    main()
