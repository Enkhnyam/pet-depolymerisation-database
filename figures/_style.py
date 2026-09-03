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

# ---------------------------------------------------------------------------------------------
# One palette, five inks, used the same way in every figure.
#
# Colour is spent only where it encodes something. A panel that counts one thing is drawn in
# NEUTRAL; colour appears when, and only when, a second variable is being shown. That is why most
# panels in this paper are grey: most of them are one series.
#
# The categorical sets below are slices of the same ordered CYCLE, so the first category of any
# set is always teal, the second always rose, and a reader who has learned one figure has learned
# them all. Two sets never share a canvas -- routes belong to the chemistry figures, measures and
# graders to the quality ones -- so no colour carries two meanings on one page.
# ---------------------------------------------------------------------------------------------
CYCLE = ["#0E7C6B", "#C4527A", "#9A6510", "#4A6B8A"]     # teal, rose, amber, slate

ROUTE = dict(zip(["glycolysis", "hydrolysis", "methanolysis", "other/unclear"], CYCLE))
ROUTES = ["glycolysis", "hydrolysis", "methanolysis"]

MEASURE = dict(zip(["precision", "recall", "f1", "kappa"], CYCLE))
GRADER = dict(zip(["metric", "judge"], CYCLE))
VERDICT = dict(zip(["accepted", "corrected", "dropped"], CYCLE))

SEQUENTIAL = "BuGn"          # single hue, so heatmaps never compete with the categoricals

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
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def canvas(rows: int, cols: int, width: float = 9.2, height: float = None):
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
            axis.scatter(pair[x], pair[y], s=13, alpha=0.45, linewidths=0,
                         color=(palette or {}).get(name, "#0E7C6B"), label=name)
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
    if horizontal:
        axis.barh(range(len(series))[::-1], series.values, color=colour, height=BAR)
        axis.set_yticks(range(len(series))[::-1], [str(i) for i in series.index])
    else:
        axis.bar(range(len(series)), series.values, color=colour, width=BAR)
        axis.set_xticks(range(len(series)), [str(i) for i in series.index])
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
        axis.hist(data, bins=edges, stacked=True,
                  color=[(palette or {}).get(name, DIM) for name in groups], label=groups)
    else:
        axis.hist(values, bins=edges, color=colour or REACHABLE)

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
        axis.bar(positions, frame[measure].values, width=width, label=str(measure),
                 color=(palette or {}).get(measure, CYCLE[offset % len(CYCLE)]))
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
        axis.scatter(rhos, position + jitter, s=5, alpha=0.45, linewidths=0,
                     color=ROUTE["glycolysis"], zorder=2)
        axis.scatter([np.median(rhos)], [position], marker="D", s=22, zorder=4,
                     color=ROUTE["glycolysis"], edgecolors="white", linewidths=0.7)
        axis.scatter([table.loc[name, "pooled"]], [position], marker="|", s=90, zorder=5,
                     color=WARN, linewidths=1.6)
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


def lollipop(axis, series, *, colour=NEUTRAL, xlabel="", ylabel="", annotate=False, xmax=None):
    """A ranked category as a stem and a dot, read top to bottom.

    A bar chart spends a rectangle of ink on a value that one dot already fixes, and eleven of
    them in a row read as a wall. The stem carries the comparison, the dot carries the value, and
    the panel stops competing with the ones beside it.
    """
    positions = range(len(series))[::-1]
    axis.hlines(list(positions), 0, series.values, color=colour, lw=1.0, alpha=0.55)
    axis.plot(series.values, list(positions), "o", ms=3.6, color=colour, lw=0)
    axis.set_yticks(list(positions), [str(name) for name in series.index])
    if xmax is not None:
        # a little past the maximum: "catalyst" is reported in 100% of records, and an axis that
        # stopped at 100 cut that dot in half against the spine
        axis.set_xlim(0, xmax * 1.04)
    if annotate:
        for position, value in zip(positions, series.values):
            axis.annotate(f"{value:,.0f}", (value, position), textcoords="offset points",
                          xytext=(5, 0), fontsize=5.5, color=DIM, va="center")
    _finish(axis, xlabel, ylabel)


def step_hist(axis, values, *, bins=30, colour=NEUTRAL, xlabel="", ylabel="records", logx=False):
    """A distribution as an outline rather than a block of bars."""
    values = pd.Series(values).dropna()
    if logx:
        values = values[values > 0]
        edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins)
        axis.set_xscale("log")
    else:
        edges = np.linspace(values.min(), values.max(), bins)
    axis.hist(values, bins=edges, histtype="step", lw=1.1, color=colour)
    _finish(axis, xlabel, ylabel)
