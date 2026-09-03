"""Paste each figure's generated caption into the manuscript, replacing the one already there.

The figure modules print a caption built from the same checks that draw the panels, so a number
in a caption cannot drift from the number in the figure. That guarantee used to stop at the
clipboard, and then it stopped somewhere worse: this file hard-coded the four figure names and
the path `artifacts/figures/`, while the manuscript had moved to `artifacts/figures_pdf/`. Every
name missed, so every figure was reported "absent" and the run still exited 0 -- a green check
over a manuscript whose captions had never once been synced.

So neither the list nor the path is written down twice any more. The figures are whatever the
manuscript \\includegraphics from core.paths.FIGURES, in the order it includes them, and a figure
it asks for that has neither a module to draw it nor a PDF on disk is an error rather than a
shrug.

Captions are collapsed to one line: a blank line inside \\caption{} starts a paragraph, which
LaTeX refuses in a float.

    sync_captions.py            rewrite the manuscript
    sync_captions.py --check    report drift and change nothing (exit 1 if any)
"""
import argparse
import io
import os
import re
import runpy
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
sys.path.insert(0, str(ROOT / "checks"))

import _style
from core.paths import FIGURES

PAPERS = [ROOT / "paper_rsc.tex"]

# The manuscript is the list. \includegraphics{artifacts/figures/fig2_chemistry.pdf} says both
# that fig2_chemistry is a figure and where its PDF has to be; nothing else needs to say either.
INCLUDE = re.compile(re.escape(f"{{{FIGURES.relative_to(ROOT)}/") + r"(\w+)\.pdf\}")


def wanted(source: str) -> list[str]:
    """Figure names the manuscript includes, in order, without repeats."""
    return list(dict.fromkeys(INCLUDE.findall(source)))


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
    anchor = source.find(f"{{{FIGURES.relative_to(ROOT)}/{name}.pdf}}")
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
    if args.check:
        os.environ["FIGURES_CHECK"] = "1"      # _style.save() compares instead of overwriting

    names = list(dict.fromkeys(
        name for paper in PAPERS if paper.exists()
        for name in wanted(paper.read_text(encoding="utf-8"))))
    if not names:
        raise SystemExit(f"no \\includegraphics from {FIGURES.relative_to(ROOT)}/ in "
                         f"{', '.join(p.name for p in PAPERS)} -- nothing to sync, which is "
                         f"never what anyone wants")

    # A figure with a module is generated and its caption is written from the same run. A figure
    # without one is hand-drawn (the pipeline schematic); it only has to be on disk.
    drawn = [n for n in names if (ROOT / "figures" / f"{n}.py").exists()]
    static = [n for n in names if n not in drawn]
    missing = [n for n in static if not (FIGURES / f"{n}.pdf").exists()]
    if missing:
        raise SystemExit(f"the manuscript includes {', '.join(missing)} with neither "
                         f"figures/<name>.py to draw it nor {FIGURES.relative_to(ROOT)}/"
                         f"<name>.pdf on disk")

    # generated once, pasted into every manuscript: running each figure twice would be slow and
    # could in principle differ, and the whole point is that they cannot
    captions = {name: generated(name) for name in drawn}

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
        for name in drawn:
            print(f"  {name:16s} {'updated' if name in stale else 'already current'}")
        for name in static:
            print(f"  {name:16s} hand-drawn, caption left alone")
        if stale and not args.check:
            paper.write_text(source, encoding="utf-8")
            print(f"  -> rewrote {paper.name} ({len(stale)} caption(s))")
        total += len(stale)

    if args.check:
        # Running the modules redraws every figure, so we already know whether each PDF on disk
        # matches what the checks say now. Reporting the captions and staying quiet about that
        # was how "everything is current" came to sit over figures three days out of date.
        for name in _style.STALE:
            print(f"  {name:16s} PDF ON DISK IS STALE")
        print(f"\n{total} caption(s) and {len(_style.STALE)} figure PDF(s) differ from the checks"
              if total or _style.STALE else "\nevery caption and figure matches the checks")
        raise SystemExit(1 if total or _style.STALE else 0)
    if not total:
        print("\nno manuscript needed changing")


if __name__ == "__main__":
    main()
