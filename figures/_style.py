"""The visual language every figure shares: one palette, one set of panel primitives.

A figure module composes panels; it never computes. The numbers come from the check that prints
them, so a panel and `scripts/checks.sh` cannot disagree.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))          # checks import each other by bare name
from core.paths import ARTIFACTS

# Two categorical roles, never mixed: route in the chemistry canvas, grader in the quality one.
ROUTE = {"glycolysis": "#0E7C6B", "hydrolysis": "#C4527A",
         "methanolysis": "#9A6510", "other/unclear": "#4A6B8A"}
GRADER = {"metric": "#0E7C6B", "judge": "#C4527A"}
VERDICT = {"accepted": "#0E7C6B", "corrected": "#9A6510", "dropped": "#A33A2E"}
SEQUENTIAL = "BuGn"          # single hue, so heatmaps never compete with the categoricals

INK, DIM, RULE, WARN = "#12201F", "#5D716E", "#D2DEDB", "#A33A2E"

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 300, "savefig.bbox": "tight",
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
    """Labels, scales and the sub-title that sits after the panel letter."""
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    if title:
        axis.set_title(f"{axis.get_title(loc='left')}   {title}", loc="left", fontsize=7.5)
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
                 tick_labels=[str(name).split()[0][:6] for name in order],
                 showfliers=False, widths=0.6, medianprops=dict(color=INK))
    if rotate:
        axis.tick_params(axis="x", labelrotation=rotate)
    _finish(axis, xlabel, ylabel, title)


def bars(axis, series, *, colour="#0E7C6B", horizontal=False, xlabel="", ylabel="", title=None,
         logx=False, annotate=False):
    """A bar chart from a Series, indexed by category."""
    if horizontal:
        axis.barh(range(len(series))[::-1], series.values, color=colour, height=0.72)
        axis.set_yticks(range(len(series))[::-1], [str(i)[:24] for i in series.index])
    else:
        axis.bar(range(len(series)), series.values, color=colour, width=0.72)
        axis.set_xticks(range(len(series)), [str(i)[:14] for i in series.index])
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


def note(axis, text, *, colour=WARN, y=0.04):
    """A short annotation inside a panel, for a caveat the reader needs at the point of looking."""
    axis.text(0.03, y, text, transform=axis.transAxes, fontsize=5.6, color=colour)


def legend_above(figure, axis, labels_from=None):
    """One legend for the whole canvas, so no panel loses points behind a key."""
    handles, labels = (labels_from or axis).get_legend_handles_labels()
    if axis.get_legend():
        axis.get_legend().remove()
    figure.legend(handles, labels, loc="upper center", ncol=max(len(labels), 1), markerscale=1.6,
                  handletextpad=0.25, columnspacing=1.4, bbox_to_anchor=(0.5, 1.02))


def save(figure, name: str, *, legend_room=False):
    figure.tight_layout(rect=(0, 0, 1, 0.955) if legend_room else None)
    out = ARTIFACTS / "figures" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)}")
    return out
