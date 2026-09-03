"""The visual language every figure shares: one palette, one set of panel primitives.

A figure module composes panels; it never computes. The numbers come from the check that prints
them, so a panel and `scripts/checks.sh` cannot disagree.
"""
import io
import os
import sys
from pathlib import Path

import matplotlib
import numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "checks"))          # checks import each other by bare name
from core.paths import ARTIFACTS, FIGURES
from core.schema import OTHER_ROUTE, ROUTES

# ---------------------------------------------------------------------------------------------
# One palette, and one rule for when colour is allowed to mean anything.
#
# The previous scheme had four categorical sets -- ROUTE, MEASURE, GRADER, VERDICT -- all slices
# of one four-colour cycle. Teal meant glycolysis in one figure, precision in the next and the
# metric grader in a third, and every panel that happened to count one thing was grey. Across a
# page that reads as colour arriving and leaving for no reason the reader can learn.
#
# So colour encodes exactly one variable in this manuscript:
#
#   ROUTE       the depolymerisation route, the one category a chemistry reader tracks between
#               figures. Teal is glycolysis everywhere, rose hydrolysis, amber methanolysis.
#   INK         everything not split by route. A panel counting one thing is one ink.
#   WARN        one meaning only: a value that is physically impossible, or a known defect.
#               Not "the other series", not "the reference line".
#   SHADES      several measures of the same quantity -- precision, recall, F1, kappa -- as one
#               hue at four lightnesses. A family, not four categories, which is what they are.
#               Never on the same canvas as ROUTE.
#
# Position separates within a panel; colour separates between panels. That ordering is
# Cleveland's and it is also why most panels here need no colour at all.
# ---------------------------------------------------------------------------------------------
INK, DIM, RULE, WARN = "#12201F", "#5D716E", "#D2DEDB", "#A33A2E"
NEUTRAL = "#54696E"          # the one ink for anything that encodes no category
GUIDE = "#C9D6D3"            # connectors, frontiers, reference lines that are not data

CYCLE = ["#0E7C6B", "#C4527A", "#9A6510"]     # teal, rose, amber -- routes, in the field's order
ROUTE = dict(zip(ROUTES, CYCLE)) | {OTHER_ROUTE: NEUTRAL}

# One hue, four lightnesses, dark to light. Ordered on purpose: a reader who cannot tell the
# middle two apart still sees which end of the family a bar sits at.
SHADES = ["#0B5F52", "#2E8577", "#68AFA3", "#A8D2CA"]

# Colour is not enough, and in this palette it is measurably not enough. Teal against rose fails
# deuteranopia simulation at dE = 11.8 (Machado 2009, CIE76), and the SHADES ramp collapses
# toward one grey in black-and-white print. So every category is encoded twice, keyed on position
# in whichever ordered list it came from.
HATCH = ["", "///", "...", "xxx"]
MARKER = ["o", "s", "^", "D"]

SEQUENTIAL = "BuGn"          # single hue, so a heatmap never competes with the route colours

# Placement. Every figure in this manuscript is a figure* at \textwidth, and \includegraphics
# scales the PDF to fit -- so a figure drawn at 9.4 in arrives at 0.75 scale and its 6 pt tick
# labels print at 4.5 pt, under the 5 pt floor. Draw at the printed width and scale is 1.0.
# (Requires a4paper in the geometry call: letterpaper gives 7.32 in, which RSC does not typeset.)
DOUBLE_COLUMN = 7.087        # 18.0 cm, \textwidth in the two-column layout
SINGLE_COLUMN = 3.474        # 8.82 cm, \columnwidth

INK, DIM, RULE, WARN = "#12201F", "#5D716E", "#D2DEDB", "#A33A2E"
NEUTRAL = "#54696E"          # anything that encodes no category
GUIDE = "#C9D6D3"            # connectors, frontiers, reference lines that are not data

# Bar geometry. A bar's width carries no information, so it should take the least ink that still
# reads as a bar: with three categories in a panel, filling 0.72 of each slot made slabs.
BAR = 0.30          # single series
GROUP = 0.46        # total width of one cluster in grouped_bars

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 300, "savefig.bbox": "tight",
    # Figures are written as PDF, so they scale with the page instead of being resampled to it.
    # fonttype 42 embeds TrueType outlines rather than Type 3, which is what most publishers
    # require and what keeps the text selectable and searchable in the submitted PDF.
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": RULE, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": DIM, "ytick.color": DIM, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 6.5,
    # fine enough that a hatch reads as texture rather than as a second fill colour at 7 pt
    "hatch.linewidth": 0.35,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def redundant(colour):
    """The hatch and marker that go with a palette colour.

    Keyed on the colour itself rather than on a category name, so it works for ROUTE, MEASURE,
    GRADER and VERDICT alike without any of them saying so. A colour that is not in CYCLE
    encodes no category -- NEUTRAL, DIM, WARN -- and gets no second channel, which is correct.
    """
    for ordered in (CYCLE, SHADES):
        if colour in ordered:
            position = ordered.index(colour)
            return HATCH[position], MARKER[position]
    return "", "o"


def canvas(rows: int, cols: int, width: float = DOUBLE_COLUMN, height: float = None):
    """A multi-panel figure with the panel letters already placed."""
    figure, axes = plt.subplots(rows, cols, figsize=(width, height or width * rows / cols * 0.62))
    panels = list(axes.ravel()) if rows * cols > 1 else [axes]
    for letter, axis in zip("abcdefghijklmnopqrstuvwxyz", panels):
        axis.set_title(letter, loc="left", fontsize=9, fontweight="bold", pad=5)
    return figure, panels


def _finish(axis, xlabel, ylabel, title=None, logx=False, logy=False, ylim=None):
    """Labels and scales. `title` is accepted and ignored: panels carry only their letter, and
    what a panel is arguing belongs in the caption where it can be said properly."""
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    if logx:
        axis.set_xscale("log")
    if logy:
        axis.set_yscale("log")
    if ylim:
        axis.set_ylim(*ylim)


def points(axis, frame, x, y, *, colour_by=None, palette=None, order=None, xlabel="", ylabel="",
           title=None, logx=False, logy=False, ylim=None, trend=False, legend=False):
    """A scatter, optionally split by a categorical column.

    Translucent and small on purpose: with a thousand points, opacity is what separates a cloud
    from a smear.
    """
    groups = [(None, frame)] if colour_by is None else [
        (name, frame[frame[colour_by] == name]) for name in (order or sorted(frame[colour_by].unique()))]

    for name, part in groups:
        pair = part[[x, y]].dropna()
        if logx:
            pair = pair[pair[x] > 0]
        if logy:
            pair = pair[pair[y] > 0]
        if len(pair):
            colour = (palette or {}).get(name, CYCLE[0])
            _, marker = redundant(colour)
            axis.scatter(pair[x], pair[y], s=13, alpha=0.45, linewidths=0, marker=marker,
                         color=colour, label=name)
    if trend:
        _trend(axis, frame, x, y, logx)
    if legend:
        axis.legend(markerscale=1.5, handletextpad=0.2, borderpad=0.2)
    _finish(axis, xlabel, ylabel, title, logx, logy, ylim)


def _trend(axis, frame, x, y, logx):
    """A rolling median through the cloud: the shape, without implying a fitted model."""
    pair = frame[[x, y]].dropna()
    pair = pair[pair[x] > 0] if logx else pair
    if len(pair) < 40:
        return
    pair = pair.sort_values(x)
    window = max(20, len(pair) // 12)
    axis.plot(pair[x], pair[y].rolling(window, center=True, min_periods=window // 2).median(),
              color=DIM, lw=1.1, ls="--", zorder=3)


def box(axis, frame, group, value, *, order=None, xlabel="", ylabel="", title=None, rotate=0):
    """Distribution of `value` per category, outliers hidden so the boxes stay readable."""
    order = order or list(frame[group].value_counts().index)
    axis.boxplot([frame[frame[group] == name][value].dropna() for name in order],
                 # full names: a label cut to six characters turns "methanolysis" into "methan"
                 tick_labels=[str(name) for name in order],
                 showfliers=False, widths=0.6, medianprops=dict(color=INK))
    if rotate:
        axis.tick_params(axis="x", labelrotation=rotate)
    _finish(axis, xlabel, ylabel, title)


def bars(axis, series, *, colour="#0E7C6B", horizontal=False, xlabel="", ylabel="", title=None,
         logx=False, annotate=False):
    """A bar chart from a Series, indexed by category."""
    # one hatch per bar when the caller passed a palette colour per bar; a single colour for
    # every bar encodes nothing, so it gets no hatch
    hatches = [redundant(c)[0] for c in colour] if isinstance(colour, list) else None
    edges = dict(edgecolor="white", linewidth=0.3) if hatches else {}
    if horizontal:
        patches = axis.barh(range(len(series))[::-1], series.values, color=colour, height=BAR,
                            **edges)
        axis.set_yticks(range(len(series))[::-1], [str(i) for i in series.index])
    else:
        patches = axis.bar(range(len(series)), series.values, color=colour, width=BAR, **edges)
        axis.set_xticks(range(len(series)), [str(i) for i in series.index])
    for patch, hatch in zip(patches, hatches or []):
        patch.set_hatch(hatch)
    if annotate:
        for position, value in enumerate(series.values):
            axis.text(value, len(series) - 1 - position, f" {value:,.0f}", va="center", fontsize=5.5,
                      color=DIM) if horizontal else None
    _finish(axis, xlabel, ylabel, title, logx=logx)


def stacked(axis, frame, *, palette=None, xlabel="", ylabel="", title=None, legend=True):
    """A stacked bar per row of `frame`, one segment per column."""
    bottom = pd.Series(0.0, index=frame.index)
    for column in frame.columns:
        axis.bar(range(len(frame)), frame[column], bottom=bottom, width=0.68,
                 color=(palette or {}).get(column), label=str(column))
        bottom += frame[column].fillna(0)
    axis.set_xticks(range(len(frame)), [str(i)[:14] for i in frame.index])
    if legend:
        axis.legend(fontsize=5.8, handlelength=1.1, handletextpad=0.4)
    _finish(axis, xlabel, ylabel, title)


def heatmap(axis, grid, *, vmin=None, vmax=None, xlabel="", ylabel="", title=None, fmt="{:.2f}"):
    """A matrix with every cell labelled, since nine cells deserve their numbers shown."""
    image = axis.imshow(grid.values, cmap=SEQUENTIAL, vmin=vmin, vmax=vmax, aspect="auto")
    axis.set_xticks(range(len(grid.columns)), grid.columns)
    axis.set_yticks(range(len(grid.index)), grid.index)
    span = (vmax or grid.values.max()) - (vmin or grid.values.min())
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            value = grid.values[i, j]
            light = value > (vmin or grid.values.min()) + span * 0.62
            axis.text(j, i, fmt.format(value), ha="center", va="center", fontsize=6.5,
                      color="white" if light else INK)
    _finish(axis, xlabel, ylabel, title)
    return image


def note(axis, text, *, colour=WARN, x=0.03, y=0.04, ha="left"):
    """A short annotation inside a panel, for a caveat the reader needs at the point of looking."""
    axis.text(x, y, text, transform=axis.transAxes, fontsize=5.6, color=colour,
              ha=ha, va="center")


def legend_above(figure, axis, labels_from=None):
    """One legend for the whole canvas, so no panel loses points behind a key."""
    handles, labels = (labels_from or axis).get_legend_handles_labels()
    if axis.get_legend():
        axis.get_legend().remove()
    figure.legend(handles, labels, loc="upper center", ncol=max(len(labels), 1), markerscale=1.6,
                  handletextpad=0.25, columnspacing=1.4, bbox_to_anchor=(0.5, 1.02))


# Figures a save() call found different from what was already on disk. matplotlib's PDF output
# is byte-reproducible for identical input, so "the bytes changed" means "the data changed",
# which is the only honest definition of a stale figure: scripts/paper.sh --check used to pass
# over figure PDFs three days older than the macros beside them, because nothing compared them
# to anything.
STALE = []


def save(figure, name: str, *, legend_room=False):
    figure.tight_layout(rect=(0, 0, 1, 0.955) if legend_room else None)
    out = FIGURES / f"{name}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    buffer = io.BytesIO()
    # CreationDate omitted, so identical data gives identical bytes across processes and
    # "the bytes changed" keeps meaning "the data changed" rather than "the clock moved"
    figure.savefig(buffer, format="pdf", metadata={"CreationDate": None})
    plt.close(figure)
    drawn = buffer.getvalue()

    changed = not out.exists() or out.read_bytes() != drawn
    if changed:
        STALE.append(name)
    # FIGURES_CHECK is how --check asks "would this differ?" without answering it by overwriting
    checking = bool(os.environ.get("FIGURES_CHECK"))
    if changed and not checking:
        out.write_bytes(drawn)
    verb = "stale" if changed and checking else "wrote" if changed else "unchanged"
    print(f"{verb} {out.relative_to(ROOT)}")
    return out


def histogram(axis, frame, column, *, bins=30, logx=False, xlabel="", ylabel="records",
              colour=None, split=None, palette=None, order=None):
    """Distribution of one column, optionally stacked by a categorical.

    Stacking rather than overlaying: with three routes an overlay hides whichever is drawn first,
    and the question here is usually what the corpus as a whole looks like.
    """
    values = frame[column].dropna()
    if logx:
        values = values[values > 0]
        edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins)
    else:
        edges = np.linspace(values.min(), values.max(), bins)

    if split:
        groups = order or list(frame[split].value_counts().index)
        data = [frame.loc[frame[split] == name, column].dropna() for name in groups]
        if logx:
            data = [d[d > 0] for d in data]
        colours = [(palette or {}).get(name, DIM) for name in groups]
        _, _, patches = axis.hist(data, bins=edges, stacked=True, color=colours, label=groups)
        # hist() takes no per-dataset hatch, so it goes on afterwards, one dataset at a time
        for colour, artists in zip(colours, patches if len(groups) > 1 else [patches]):
            hatch, _ = redundant(colour)
            for patch in artists:
                patch.set(hatch=hatch, edgecolor="white", linewidth=0.3)
    else:
        axis.hist(values, bins=edges, color=colour or NEUTRAL)

    _finish(axis, xlabel or column, ylabel, logx=logx)
    return axis


def caption(template: str, **values) -> str:
    """Fill a LaTeX caption by token, never by str.format.

    Captions are full of braces -- \\textbf{...}, \\% -- and format() reads every one of them as a
    placeholder. Tokens are written __LIKE_THIS__ and substituted literally.
    """
    text = template
    for name, value in values.items():
        text = text.replace(f"__{name.upper()}__", str(value))
    return text


def grouped_bars(axis, frame, *, xlabel="", ylabel="", palette=None, rotate=0, errors=None):
    """One cluster per row of `frame`, one bar per column -- for comparing a few measures across
    a few models, where a heatmap would be overkill and a line would imply an ordering.

    `errors` is an optional frame of the same shape. Pass it whenever the numbers are means over
    repeats: four runs of one model at identical settings span 0.05 in F1 here, wider than the
    gap between two of the models, and a bare bar asserts a precision the data does not have.
    """
    names, measures = list(frame.index), list(frame.columns)
    width = GROUP / len(measures)
    for offset, measure in enumerate(measures):
        positions = [i + offset * width - GROUP / 2 + width / 2 for i in range(len(names))]
        colour = (palette or {}).get(measure, CYCLE[offset % len(CYCLE)])
        hatch, _ = redundant(colour)
        # white hatch over the fill: it reads as texture in colour and as the only difference
        # between the bars in greyscale, where all four fills are one L* 44-51 grey
        axis.bar(positions, frame[measure].values, width=width, label=str(measure),
                 color=colour, hatch=hatch, edgecolor="white", linewidth=0.3)
        if errors is not None and measure in errors:
            axis.errorbar(positions, frame[measure].values, yerr=errors[measure].values,
                          fmt="none", ecolor=INK, elinewidth=0.8, capsize=1.8, zorder=4)
    axis.set_xticks(range(len(names)), [str(n) for n in names])
    if rotate:
        axis.tick_params(axis="x", labelrotation=rotate)
    axis.legend(frameon=False, fontsize=6)
    _finish(axis, xlabel, ylabel)
    return axis


def paired_rho(axis, table, curves, *, xlabel="Spearman rho", labels=None):
    """Per-paper correlations as a strip, against the single pooled value for the same pair.

    The point of the panel is the gap between the two, so both live on one axis: a cloud of
    per-paper rhos sitting off zero while the pooled marker sits on it is the whole argument,
    and separating them into two panels would make the reader do the comparison from memory.
    """
    rows = list(table.index)[::-1]          # first relationship at the top
    axis.axvline(0, color=RULE, lw=1, zorder=0)
    for position, name in enumerate(rows):
        rhos = curves[name].values
        jitter = np.random.default_rng(0).uniform(-0.13, 0.13, len(rhos))
        # NEUTRAL, not a route colour: these dots pool all three routes, so colouring them
        # glycolysis-teal claimed a split the panel does not make
        axis.scatter(rhos, position + jitter, s=5, alpha=0.45, linewidths=0,
                     color=NEUTRAL, zorder=2)
        axis.scatter([np.median(rhos)], [position], marker="D", s=22, zorder=4,
                     color=NEUTRAL, edgecolors="white", linewidths=0.7)
        axis.scatter([table.loc[name, "pooled"]], [position], marker="|", s=90, zorder=5,
                     color=INK, linewidths=1.6)
    axis.set_yticks(range(len(rows)))
    axis.set_yticklabels(labels or rows, fontsize=6)
    axis.set_xlim(-1.05, 1.05)
    axis.set_ylim(-0.6, len(rows) - 0.4)
    _finish(axis, xlabel, "")


def sci(value: float, digits: int = 0) -> str:
    """A small number as LaTeX maths: 6.8e-07 -> 7\\times10^{-7}.

    Captions are pasted into the paper verbatim, so a p-value has to arrive already typeset;
    "7e-07" in a caption is a leaked repr, not a number.
    """
    mantissa, exponent = f"{value:.{digits}e}".split("e")
    return f"{mantissa}\\times10^{{{int(exponent)}}}"


def ranked_bars(axis, series, *, colour=None, accent=None, xlabel="", fmt="{:,.0f}",
                axis_off=True):
    """A ranked horizontal bar per category, largest at the top, value on the bar end.

    Replaces a lollipop -- a stem and a dot -- which is the right mark for a distribution of
    ranges and the wrong one for a magnitude. Three of six panels in Figure 1 were lollipops and
    the page read as rows of faint lines.

    `accent` colours the largest bar alone, for the panels where one category dominates and that
    is the finding. The x axis is dropped by default: the bar ends carry the numbers, so an axis
    would be a second copy of them.
    """
    series = series.sort_values()
    colour = colour or NEUTRAL
    colours = [colour] * len(series)
    if accent is not None and len(series):
        colours[-1] = accent
    positions = range(len(series))
    axis.barh(list(positions), series.values, color=colours, height=0.62)
    axis.set_yticks(list(positions), [str(name) for name in series.index])
    span = float(series.max()) if len(series) and series.max() else 1.0
    for position, value in zip(positions, series.values):
        axis.annotate(fmt.format(value), (value, position), textcoords="offset points",
                      xytext=(3, 0), fontsize=5.4, color=DIM, va="center")
    axis.set_xlim(0, span * 1.22)
    if axis_off:
        axis.set_xticks([])
        axis.spines["bottom"].set_visible(False)
    _finish(axis, xlabel, "")
    return axis


def step_hist(axis, values, *, bins=30, colour=NEUTRAL, xlabel="", ylabel="records", logx=False,
              logy=False):
    """A distribution as an outline rather than a block of bars.

    `logy` for the heavily skewed counts: papers-per-record peaks at one and runs to 84, and on a
    linear axis that panel was a single spike with nine tenths of it empty.
    """
    values = pd.Series(values).dropna()
    if logx:
        values = values[values > 0]
        edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins)
        axis.set_xscale("log")
    else:
        edges = np.linspace(values.min(), values.max(), bins)
    axis.hist(values, bins=edges, histtype="step", lw=1.1, color=colour)
    if logy:
        axis.set_yscale("log")
    _finish(axis, xlabel, ylabel)


if __name__ == "__main__":
    # The palette rule, asserted rather than described. If a future edit reintroduces a second
    # categorical set, or gives two routes the same hatch, this fails.
    glycolysis, hydrolysis, methanolysis = CYCLE
    assert list(ROUTE) == [*ROUTES, OTHER_ROUTE], "ROUTE must follow core.schema's route order"
    assert ROUTE[OTHER_ROUTE] == NEUTRAL, "an unassigned route is not a category"

    # teal against rose fails deuteranopia simulation, so route must differ in a second channel
    for left, right in ((glycolysis, hydrolysis), (hydrolysis, methanolysis),
                        (glycolysis, methanolysis)):
        assert redundant(left)[0] != redundant(right)[0], "two routes share a hatch"
        assert redundant(left)[1] != redundant(right)[1], "two routes share a marker"
    # and the measure family collapses toward one grey in print, so the same applies to it
    assert len({redundant(c)[0] for c in SHADES}) == len(SHADES), "two measures share a hatch"

    # anything that encodes no category gets no second channel
    for name, colour in (("NEUTRAL", NEUTRAL), ("WARN", WARN), ("DIM", DIM), ("GUIDE", GUIDE)):
        assert redundant(colour) == ("", "o"), f"{name} is not a category and must not look like one"

    # the figures are drawn at the width they are printed at, so nothing is scaled
    assert canvas(1, 1)[0].get_figwidth() == DOUBLE_COLUMN
    plt.close("all")
    print("_style self-check ok")
