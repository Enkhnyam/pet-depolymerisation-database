"""Can a reader actually tell the figures' colours apart?

Not a question to answer by looking. The palette this replaced was five steps of one green, and
a reader asked to separate four categories in it could not -- which figures/_palette.py puts a
number on: two of its adjacent pairs sat at dE 14.7 and 14.1 against a normal-vision floor of
15. The complaint was measurable, so the replacement is measured.

Six checks, from the dataviz guidance whose reference implementation is a Node script this
machine does not have: lightness band, chroma floor, colour-blind separation under all three
kinds, normal-vision separation, contrast against the surface, and greyscale separation for
print. Distance is Euclidean in OKLab x100; simulation is Machado, Oliveira and Fernandes
(2009) at full severity.

It runs here rather than only inside _style.py's self-check because a palette edit that breaks
separability should fail the suite, not wait to be noticed on a page.

    palette.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "figures"))

from _palette import CVD, CVD_TARGET, NORMAL_FLOOR, distance, drawn_colours, report, table
from _style import CATEGORICAL, DIM, INK, RAMP, RAMP_RED, RULE, SLOTS
from _setup import show
from core.paths import FIGURES

# Everything a figure is allowed to paint with: the four categorical slots, the five ramp steps,
# the three inks, and the two the renderer supplies for the page itself.
ALLOWED = ({c.upper() for c in list(CATEGORICAL.values()) + RAMP + RAMP_RED
            + [INK, DIM, RULE]} | {"#FFFFFF", "#000000"})


def stray() -> dict[str, list[str]]:
    """Colours in the drawn figures that are in no palette, per figure.

    The palette checks above prove the palette is separable. They say nothing about what the
    figures actually contain, and the two came apart: a plot() call that named a marker colour
    but no line colour drew its empty line from matplotlib's cycle, and three tab10 hues were
    written into fig_chemistry while every palette check passed.
    """
    off = {}
    for pdf in sorted(FIGURES.glob("fig_*.pdf")):
        extra = sorted(drawn_colours(pdf) - ALLOWED)
        if extra:
            off[pdf.name] = extra
    return off


def compute() -> dict:
    problems = report(CATEGORICAL)
    worst = min(distance(SLOTS[i], SLOTS[j], kind)
                for i in range(len(SLOTS)) for j in range(i + 1, len(SLOTS))
                for kind in CVD)
    return {"slots": len(CATEGORICAL), "failures": problems, "off palette": stray(),
            "worst colour-blind separation": worst}


def main() -> None:
    print("reads")
    print("  palette    figures/_style.py CATEGORICAL and RAMP")
    print(f"  figures    {len(list(FIGURES.glob('fig_*.pdf')))} drawn PDFs in "
          f"{FIGURES.relative_to(FIGURES.parents[1])}")
    print("  thresholds "
          f"colour-blind target dE {CVD_TARGET:g} · normal-vision floor dE {NORMAL_FLOOR:g}")

    print()
    print(table(CATEGORICAL))

    result = compute()
    show("summary", {"categorical slots": result["slots"],
                     "worst pair, any colour blindness": result["worst colour-blind separation"],
                     "failures": len(result["failures"]),
                     "figures painting an unlisted colour": len(result["off palette"])},
         fmt="{:.1f}")

    if result["failures"] or result["off palette"]:
        print()
        for line in result["failures"]:
            print("  " + line)
        for name, extra in result["off palette"].items():
            print(f"  off palette  {name} paints {', '.join(extra)} -- an artist somewhere is "
                  f"taking its colour from matplotlib's cycle")
        raise SystemExit(1)

    print(f"\n  every pair separates for every reader; worst case is dE "
          f"{result['worst colour-blind separation']:.1f} against a target of {CVD_TARGET:g}")
    print(f"  the ordered ramp is {len(RAMP)} steps of one hue, which is the only place a ramp "
          f"belongs")
    print(f"  and every colour in the {len(list(FIGURES.glob('fig_*.pdf')))} drawn figures is "
          f"one of them")


if __name__ == "__main__":
    main()
