"""Whether a palette is actually distinguishable, computed rather than judged.

The house palette was five steps of one hue. It was consistent, and it was five shades of green:
a reader asked to tell four categories apart in it could not, which is the complaint that
prompted this file. Replacing it is easy; replacing it with something that is *measurably*
separable, in colour and in greyscale and under colour blindness, is not something to do by eye.

So the six checks live here and run in the suite. They are the ones the dataviz guidance
specifies, whose reference implementation is a Node script this machine does not have:

  1. lightness band     no slot so dark or so light that it disappears against the surface
  2. chroma floor       no slot so grey it reads as the de-emphasis ink
  3. CVD separation     every pair, under deuteranopia, protanopia and tritanopia
  4. normal vision      every pair, to full-colour readers
  5. contrast           every slot against the surface it is drawn on
  6. greyscale          every pair once hue is discarded, for print

Distance is Euclidean in OKLab, scaled by 100, which is the unit the >= 8 and >= 15 thresholds
in that guidance are quoted in. Colour-blind simulation is Machado, Oliveira and Fernandes
(2009) at full severity, applied in linear light.

    _palette.py       print the report and exit non-zero on any failure
"""
import numpy as np

# Machado 2009, severity 1.0, operating on linear-light RGB.
CVD = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868],
                            [0.114503, 0.786281, 0.099216],
                            [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968],
                              [0.280085, 0.672501, 0.047413],
                              [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.array([[1.255528, -0.076749, -0.178779],
                            [-0.078411, 0.930809, 0.147602],
                            [0.004733, 0.691367, 0.303900]]),
}

# OKLab, Björn Ottosson's coefficients.
_LMS = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                 [0.2119034982, 0.6806995451, 0.1073969566],
                 [0.0883024619, 0.2817188376, 0.6299787005]])
_LAB = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                 [1.9779984951, -2.4285922050, 0.4505937099],
                 [0.0259040371, 0.7827717662, -0.8086757660]])

# Thresholds. CVD_FLOOR is the "legal only with a second channel" floor; CVD_TARGET is the one
# to actually clear. NORMAL_FLOOR is a hard failure -- below it, full-colour readers cannot
# separate the pair and no amount of hatching excuses it.
CVD_TARGET, CVD_FLOOR, NORMAL_FLOOR = 8.0, 6.0, 15.0
GREY_FLOOR = 6.0                 # in L* alone, for a black-and-white print
LIGHTNESS_BAND = (30.0, 82.0)    # OKLab L, x100
CHROMA_FLOOR = 4.0
CONTRAST_FLOOR = 1.6             # WCAG-style ratio against the surface


def _linear(hexc: str) -> np.ndarray:
    channels = np.array([int(hexc.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return np.where(channels <= 0.04045, channels / 12.92,
                    ((channels + 0.055) / 1.055) ** 2.4)


def oklab(hexc: str, simulate: str | None = None) -> np.ndarray:
    """OKLab of a hex colour, x100, optionally as one kind of colour blindness sees it."""
    rgb = _linear(hexc)
    if simulate:
        rgb = np.clip(CVD[simulate] @ rgb, 0, 1)
    return 100 * (_LAB @ np.cbrt(_LMS @ rgb))


def distance(left: str, right: str, simulate: str | None = None) -> float:
    return float(np.linalg.norm(oklab(left, simulate) - oklab(right, simulate)))


def relative_luminance(hexc: str) -> float:
    return float(np.array([0.2126, 0.7152, 0.0722]) @ _linear(hexc))


def contrast(left: str, right: str) -> float:
    a, b = relative_luminance(left), relative_luminance(right)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def report(slots: dict[str, str], surface: str = "#FFFFFF") -> list[str]:
    """Every check, as a list of failures. Empty list means the palette passes."""
    failures = []
    names = list(slots)

    for name, colour in slots.items():
        lab = oklab(colour)
        chroma = float(np.hypot(lab[1], lab[2]))
        if not LIGHTNESS_BAND[0] <= lab[0] <= LIGHTNESS_BAND[1]:
            failures.append(f"lightness  {name} {colour} L={lab[0]:.1f} outside "
                            f"{LIGHTNESS_BAND}")
        if chroma < CHROMA_FLOOR:
            failures.append(f"chroma     {name} {colour} C={chroma:.1f} below {CHROMA_FLOOR}")
        ratio = contrast(colour, surface)
        if ratio < CONTRAST_FLOOR:
            failures.append(f"contrast   {name} {colour} {ratio:.2f}:1 against {surface}")

    for i, left in enumerate(names):
        for right in names[i + 1:]:
            pair = f"{left}/{right}"
            normal = distance(slots[left], slots[right])
            if normal < NORMAL_FLOOR:
                failures.append(f"normal     {pair} dE={normal:.1f} below {NORMAL_FLOOR}")
            for kind in CVD:
                seen = distance(slots[left], slots[right], kind)
                if seen < CVD_FLOOR:
                    failures.append(f"{kind[:9]:9s}  {pair} dE={seen:.1f} below {CVD_FLOOR}")
            grey = abs(oklab(slots[left])[0] - oklab(slots[right])[0])
            if grey < GREY_FLOOR:
                failures.append(f"greyscale  {pair} dL={grey:.1f} below {GREY_FLOOR}")
    return failures


def table(slots: dict[str, str]) -> str:
    lines = [f"{'slot':<10}{'hex':<10}{'L':>6}{'chroma':>8}{'contrast':>10}"]
    for name, colour in slots.items():
        lab = oklab(colour)
        lines.append(f"{name:<10}{colour:<10}{lab[0]:6.1f}{np.hypot(lab[1], lab[2]):8.1f}"
                     f"{contrast(colour, '#FFFFFF'):9.2f}:1")
    names = list(slots)
    lines.append("")
    lines.append(f"{'pair':<22}{'normal':>8}{'deuter':>8}{'protan':>8}{'tritan':>8}{'grey':>7}")
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            lines.append(
                f"{left + '/' + right:<22}"
                f"{distance(slots[left], slots[right]):8.1f}"
                f"{distance(slots[left], slots[right], 'deuteranopia'):8.1f}"
                f"{distance(slots[left], slots[right], 'protanopia'):8.1f}"
                f"{distance(slots[left], slots[right], 'tritanopia'):8.1f}"
                f"{abs(oklab(slots[left])[0] - oklab(slots[right])[0]):7.1f}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    from _style import CATEGORICAL

    print(table(CATEGORICAL))
    problems = report(CATEGORICAL)
    print()
    if problems:
        print(f"{len(problems)} failure(s):")
        for line in problems:
            print("  " + line)
        sys.exit(1)
    print(f"palette of {len(CATEGORICAL)} passes all six checks "
          f"(CVD target {CVD_TARGET:g}, normal-vision floor {NORMAL_FLOOR:g})")
