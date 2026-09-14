"""The visual language every figure shares: one palette, one set of panel primitives.

A figure module composes panels; it never computes. The numbers come from the check that prints
them, so a panel and `scripts/checks.sh` cannot disagree.
"""
import io
import math
import os
import sys
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.colors import ListedColormap
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "checks"))          # checks import each other by bare name
from core.paths import ARTIFACTS, FIGURES
from core.schema import OTHER_ROUTE, ROUTES

# ---------------------------------------------------------------------------------------------
# Two palettes, and a rule for which one a panel gets.
#
# The old one was five steps of a single green. It was consistent, and it was five shades of
# green: asked to tell four categories apart in it, a reader could not. figures/_palette.py puts
# a number on that -- the old ramp failed the normal-vision floor on two of its adjacent pairs,
# at dE 14.7 and 14.1 against a floor of 15. So the complaint was not taste, it was measurable.
#
#   CATEGORICAL   four clearly different hues, for data whose categories are its subject.
#                 Blue, red, yellow, purple, assigned in that fixed order and never cycled.
#                 Chosen by search over muted candidates and validated by _palette.py against
#                 all six checks: worst-case separation under deuteranopia, protanopia or
#                 tritanopia is dE 11.1 against a target of 8, and every pair also separates in
#                 greyscale. Chroma stays between 9 and 13, so none of them is bright.
#
#                 There is deliberately no green. Red against green is the one pair that
#                 red-green colour blindness destroys, and every candidate set holding both
#                 failed: the search returned 27 passing sets built on blue, red and yellow and
#                 none built on red and green.
#
#   RAMP          one hue, five steps, light to dark, for data that is *ordered* -- a funnel, a
#                 verdict split, a heatmap. Magnitude is what a ramp is for, and it is not what
#                 the complaint was about. Anchored on CATEGORICAL blue so the two relate.
#
# DATA is the single-series colour: one panel counting one thing is blue, everywhere.
# ---------------------------------------------------------------------------------------------
CATEGORICAL = {"blue": "#25517E", "red": "#9C3F36", "yellow": "#C69A2E", "purple": "#7C68A6"}
SLOTS = list(CATEGORICAL.values())

RAMP = ["#16324E", "#25517E", "#4E7BA8", "#8AA8C6", "#C6D5E3"]     # dark to light, L* 31..87

INK, DIM, RULE = "#12201F", "#5D716E", "#DFE7E5"   # reference lines, tick labels, axis rules
GUIDE = "#C9D6D3"
DATA = CATEGORICAL["blue"]     # every panel that counts one thing
EMPHASIS = RAMP[0]             # the one mark worth pointing at, by weight not by a new hue

# Routes are three categories a chemistry reader tracks between figures, so they take the first
# three slots in order. An unassigned route is not a category and gets the de-emphasis ink.
ROUTE = dict(zip(ROUTES, SLOTS[:3])) | {OTHER_ROUTE: DIM}
CYCLE = SLOTS[:3]

# The two graders are two subjects and the comparison the whole section is about, so they take
# the first two slots -- blue for the heuristic, red for the judge.
GRADER = dict(zip(["metric", "judge"], SLOTS[:2]))

# Several measures of one quantity -- precision, recall, F1, kappa -- are a family and not four
# subjects, so they take the ramp rather than four hues.
SHADES = RAMP[:4]

SEQUENTIAL = ListedColormap(RAMP[::-1])
WASH = RAMP[4]

MARKER = ["o", "s", "^", "D"]

# Placement. Every figure in this manuscript is a figure* at \textwidth, and \includegraphics
# scales the PDF to fit -- so a figure drawn at 9.4 in arrives at 0.75 scale and its 6 pt tick
# labels print at 4.5 pt, under the 5 pt floor. Draw at the printed width and scale is 1.0.
# (Requires a4paper in the geometry call: letterpaper gives 7.32 in, which RSC does not typeset.)
DOUBLE_COLUMN = 7.087        # 18.0 cm, \textwidth in the two-column layout
SINGLE_COLUMN = 3.474        # 8.82 cm, \columnwidth

# Bar geometry. A bar's width carries no information, so it should take the least ink that still
# reads as a bar: with three categories in a panel, filling 0.72 of each slot made slabs.
BAR = 0.30          # single series
GROUP = 0.46        # total width of one cluster in grouped_bars

# When each bar is named under itself rather than in a legend, the cluster has to open up: a
# name set on the slant still needs the width of a line of type, and GROUP/3 of a unit slot is
# narrower than that. So the bars go one unit apart with a blank gap between clusters, and the
# tilt is what keeps a six-letter name inside one unit.
CLUSTER_GAP = 1.5
TILT = 45

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
    # Hatching is one panel's business -- panel i, where two regions overlap and
    # both have to stay readable through each other. At the default 1.0 it is a
    # scribble in a 1.5 in panel; this is a texture.
    "hatch.linewidth": 0.3,
})

# ---------------------------------------------------------------------------------------------
# seaborn draws the panels now. It is matplotlib underneath -- the rcParams above still govern
# type, spines and the PDF writer, and save() and the colour audit are unchanged -- so this is a
# change of drawing API, not of renderer.
#
# What it buys: forms that took a custom primitive here and got them wrong twice. A univariate
# kdeplot with common_norm=False normalises each group separately, so a route holding 273
# records reads as clearly as one holding 1,724 -- the exact failure that defeated histograms,
# cumulative curves, quantile rows and violins in turn. A bivariate kdeplot with hue and fill
# replaces overlap(), which hand-rolled contour extraction and needed an assertion to catch
# regions running off the grid.
#
# set_theme is called with the house rcParams re-applied over it, because seaborn's own theme
# would otherwise overwrite the type sizes and the axis colours. The palette is the validated
# one and nothing else: seaborn's defaults are its own ten hues, and checks/palette.py reads
# the drawn PDFs, so a seaborn default reaching a figure fails the suite rather than the page.
# ---------------------------------------------------------------------------------------------
_HOUSE = dict(plt.rcParams)
sns.set_theme(style="ticks", context="paper")
plt.rcParams.update(_HOUSE)
sns.set_palette(SLOTS)


def kde(axis, frame, x, *, hue=None, palette=None, order=None, fill=True, common_norm=False,
        multiple="layer", clip=None, xlabel="", ylabel="density", legend=False, **kw):
    """A distribution by group, each group normalised to itself unless told otherwise.

    common_norm=False is the whole reason this is a kde and not a histogram. Under it each
    group's curve integrates to one, so shape is comparable between groups of wildly different
    size; the shared-axis histogram this replaces made methanolysis, at a sixth of glycolysis,
    a flat line beside a tall one.

    `clip` does two jobs and only one of them is seaborn's. It bounds where the curve is drawn,
    which is what stops a density over a percentage spilling past 100. It does *not* bound what
    the bandwidth is fitted to -- seaborn estimates that from the whole column -- and for the
    amount fields the whole column runs to eight tonnes of solvent, so Scott's rule returned a
    bandwidth wider than the window and drew three flat rectangles. The window is therefore
    applied to the data as well: what each curve shows is the distribution of the records inside
    it, which is what the axis label's "in view" share already declares.
    """
    data = frame if hue is None else frame[frame[hue].notna()]
    if clip is not None:
        data = data[data[x].between(*clip)]
    sns.kdeplot(data=data, x=x, hue=hue, ax=axis, fill=fill, common_norm=common_norm,
                multiple=multiple, palette=palette, hue_order=order, clip=clip,
                # A thin line under a pale fill reads as faint, which is what "it looks weak"
                # was about. Four weights were drawn side by side: a heavier line with a
                # *lighter* fill is the one that gains presence without the three overlaps
                # turning to mud, because the line carries the shape and the fill only says
                # which curve owns which area.
                linewidth=1.6, alpha=0.22 if multiple == "layer" else 0.9,
                legend=legend, warn_singular=False, **kw)
    # No numbers on the density axis. Each curve is normalised to itself, so the height carries
    # no unit a reader can act on -- only the shapes are being compared, and printing 0.023
    # beside them invites reading it as a quantity.
    if multiple == "layer":
        axis.set_yticks([])
    _finish(axis, xlabel or x, ylabel)
    return axis


def route_key(axis, palette: dict, order, *, title="") -> None:
    """A legend given an axes of its own, for a grid with a cell to spare.

    legend_above() put this over the canvas at 6.5 pt, competing with the caption for the
    reader's first glance. A spare cell in the grid is a better home: the swatches can be large
    enough to read and the key sits inside the figure's own frame.
    """
    axis.set_axis_off()
    for position, name in enumerate(order):
        y = 0.78 - position * 0.16
        axis.add_patch(plt.Rectangle((0.06, y - 0.035), 0.10, 0.075, transform=axis.transAxes,
                                     facecolor=palette[name], edgecolor="none", clip_on=False))
        axis.text(0.21, y, str(name), transform=axis.transAxes, fontsize=7, color=INK,
                  va="center")
    if title:
        axis.text(0.06, 0.94, title, transform=axis.transAxes, fontsize=6.2, color=DIM,
                  va="center")


def walled(axis, xlim, ylim):
    """Limits set to the density's own support, and a box drawn round it.

    Two spines is the house rule and it is right for a curve or a scatter, because nothing is
    drawn where the missing spines would be. A filled bivariate density on a bounded field is
    the one exception. Yield stops at 100%, records pile up against it, and the outer contour
    therefore ends in a flat cut along the bound rather than closing -- measured, up to 13% of
    its length on the yield and selectivity panels, and 29% along conversion in fig_gao(b).

    That cut is honest. What made it read as a shape escaping its panel was padding the axis
    past the bound: the limit went to 110%, the cut stayed at 100, and the flat edge floated in
    white with no line beneath it. Nothing was outside the axes -- the truncation just had
    nothing to be truncated *by*. Putting the limit on the bound and closing the box gives every
    flat edge a wall to lie on, and the panel reads as a density filling its range.
    """
    axis.set_xlim(*xlim)
    axis.set_ylim(*ylim)
    for side in ("top", "right"):
        axis.spines[side].set_visible(True)
    return axis


def marker_for(colour):
    """The marker shape that goes with a ramp step, for scatters where clouds overlap.

    Keyed on the colour rather than on a category name, so any slice of RAMP gets a consistent
    shape without saying so. This used to return a hatch as well; hatching is gone, because the
    ramp's lightness spacing already separates every step in greyscale.
    """
    for ordered in (SLOTS, RAMP):
        if colour in ordered:
            return MARKER[ordered.index(colour) % len(MARKER)]
    return "o"


def canvas(rows: int, cols: int, width: float = DOUBLE_COLUMN, height: float = None):
    """A multi-panel figure with the panel letters already placed."""
    figure, axes = plt.subplots(rows, cols, figsize=(width, height or width * rows / cols * 0.62))
    panels = list(axes.ravel()) if rows * cols > 1 else [axes]
    for letter, axis in zip("abcdefghijklmnopqrstuvwxyz", panels):
        axis.set_title(letter, loc="left", fontsize=9, fontweight="bold", pad=5)
    return figure, panels


def headroom(axis, tallest: float, *, ticks: int = 5) -> None:
    """Put the top tick at or above the tallest mark.

    matplotlib picks ticks to span the data, not to sit above it, so a bar of 631 under a top
    tick of 600 is the default rather than a mistake -- and it leaves a reader unable to read
    the peak off the axis. This rounds the limit up to a round number the ticks can land on.
    """
    if not tallest or tallest != tallest:                # zero or NaN: leave the autoscale
        return
    step = 10 ** np.floor(np.log10(tallest / max(ticks - 1, 1)))
    for multiple in (1, 1.5, 2, 2.5, 3, 4, 5, 8, 10):
        nice = step * multiple
        if nice * (ticks - 1) >= tallest:
            break
    top = nice * np.ceil(tallest / nice)
    axis.set_ylim(0, top)
    axis.set_yticks(np.arange(0, top + nice / 2, nice))


def stack_tops(axis) -> float:
    """The tallest *stack* in a bar axis, which is what a reader sees on a stacked histogram.

    Individual patch heights understate it: matplotlib stacks by giving each segment its own
    bottom, so the visible top of a column is bottom + height of its last segment.
    """
    tops = [p.get_y() + p.get_height() for p in axis.patches if hasattr(p, "get_height")]
    return max(tops) if tops else 0.0


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


def density(axis, frame, x, y, *, gridsize=26, xlabel="", ylabel="", xlim=None, ylim=None):
    """Two columns as a binned density rather than a cloud of translucent dots.

    A thousand-point scatter at alpha 0.45 needs opacity to read as a cloud, and opacity is how
    the colour audit found four blended greens belonging to no palette. A hex bin uses the five
    ramp steps and nothing else, and it shows where the mass actually is, which an overplotted
    cloud cannot.
    """
    pair = frame[[x, y]].dropna()
    axis.hexbin(pair[x], pair[y], gridsize=gridsize, cmap=SEQUENTIAL, mincnt=1,
                linewidths=0.15, edgecolors="white", bins="log")
    if xlim:
        axis.set_xlim(*xlim)
    if ylim:
        axis.set_ylim(*ylim)
    _finish(axis, xlabel, ylabel)
    return axis


def cloud(axis, x, y, *, colour, marker="o", size=7, label=None, edge=None, zorder=2):
    """One set of points. Overlay two calls to compare two datasets on the same axes.

    Solid fills, no opacity: alpha over alpha was where the colour audit found blends belonging
    to no palette. Two sets separate by lightness and by marker instead, and the paler one is
    drawn first so the darker overlay sits on top of it.
    """
    axis.scatter(x, y, s=size, marker=marker, color=colour, linewidths=0.3 if edge else 0,
                 edgecolors=edge or "none", label=label, zorder=zorder)
    return axis


def shares(values, *, decimals: int = 0) -> list[float]:
    """Percentages that sum to exactly 100, by largest remainder.

    Rounding each share on its own does not give a hundred. Fig. 2b printed 81 + 6 + 14 = 101,
    because 80.70, 5.61 and 13.68 all round up, and a reader who adds the legend up finds the
    figure wrong about its own total. The remainder method hands the shortfall to the slices
    with the largest fractional parts, which is the smallest change that closes it: at most one
    slice moves, and it moves by one unit in the last place printed.

    The caller chooses the precision, because it has to match whatever the body text quotes:
    the route pie is integers because the manuscript says 48%, and the grader pie needs one
    decimal because no integer split of 230/16/39 sums to a hundred.
    """
    total = float(sum(values))
    if not total:
        return [0.0] * len(values)
    scale = 10 ** decimals
    exact = [float(v) / total * 100 * scale for v in values]
    floors = [int(math.floor(e)) for e in exact]
    short = int(round(100 * scale - sum(floors)))
    by_remainder = sorted(range(len(exact)), key=lambda i: exact[i] - floors[i], reverse=True)
    for index in by_remainder[:short]:
        floors[index] += 1
    return [value / scale for value in floors]


def pie(axis, series, *, colours, fmt="{:,.0f}", title="", decimals: int = 0,
        key="below", ncol=None):
    """A part-to-whole with a legend under it, no labels on the slices.

    A pie is the wrong mark for comparing magnitudes and the right one for showing that a set
    decomposes: every record has exactly one route, and the slices sum to the database.

    The slices were labelled outside, and it was reported that the labels did not line up with
    them. They did not. Each label was pinned to a fixed x at the side of the circle, so a slice
    near twelve o'clock got a label out at the edge with nothing joining the two, and the leader
    line that was supposed to join them ended on the label's own line rather than on the wedge.
    Pushing colliding labels apart then moved a label away from the only slice that identified
    it.

    A legend cannot have that fault: the swatch *is* the identification, so there is nothing to
    align. It also gives the circle back the width four labels were spending -- the pie having
    been too small was the other complaint about this panel -- and it puts the name, the count
    and the share on one line each, where they read as a small table.

    `key="right"` or `"left"` sets that table beside the circle instead of under it. Under it is
    right for a panel in a row, where the space below is the caption's anyway; beside it is right
    for a panel in a grid, where the space below belongs to the panel underneath and the circle is
    the thing being squeezed. Which side depends on the panel below: a key on the same side as
    that panel's row labels gives the column one shape -- text left, graphic right -- instead of
    two panels leaning opposite ways.
    """
    percent = shares(list(series.values), decimals=decimals)
    wedges, _ = axis.pie(series.values, colors=colours, startangle=90, counterclock=False,
                         radius=1.0, center=(0, 0),
                         wedgeprops=dict(linewidth=0.6, edgecolor="white"))

    placement = {"right": dict(loc="center left", bbox_to_anchor=(0.98, 0.5)),
                 # 0.20 rather than 0: the circle does not reach the axes' left edge, so a key
                 # flush to that edge sits in open space and reads as the neighbouring panel's.
                 "left": dict(loc="center right", bbox_to_anchor=(0.20, 0.5))}.get(
                     key, dict(loc="upper center", bbox_to_anchor=(0.5, -0.02)))
    axis.legend(wedges,
                [f"{name}  {fmt.format(value)} ({share:.{decimals}f}%)"
                 for (name, value), share in zip(series.items(), percent)],
                **placement, frameon=False,
                fontsize=5.4, labelcolor=INK, title=title or None,
                title_fontproperties=dict(size=6.2),
                handlelength=0.85, handleheight=0.85, handletextpad=0.5,
                labelspacing=0.42, borderpad=0.0, borderaxespad=0.0,
                ncol=ncol or (1 if len(series) < 4 else 2), columnspacing=1.0)

    # A square aspect that leaves the axes box alone: adjustable="box" shrinks the box to
    # satisfy the aspect, and the panel letter is anchored to the box, so the letter drifted out
    # of line with its neighbours. Only the y limit is set -- with datalim the x limit is
    # derived from it and the box, and setting one anyway is what printed "Ignoring fixed x
    # limits" on every build. There is no side room to reserve now that the legend replaced the
    # outside labels.
    # axis.pie() fixes both limits itself, and apply_aspect() with adjustable="datalim" then
    # has to discard one and says so on every build. Both are handed back to autoscale: the
    # circle is centred by its own geometry, so there was nothing for a fixed limit to do, and
    # the output is byte-identical without them.
    axis.autoscale(enable=True)
    axis.set_aspect("equal", adjustable="datalim")
    return axis


def overlap(axis, first, second, *, enclose=0.9, grid=220, view, pad=0.10):
    """Where two 2-D distributions sit, and where they sit on top of each other.

    Two shapes, both drawn whole and both see-through, so the reader can follow either one
    where the other crosses it. The first is a pale wash in the page's own teal, the second is
    hatched over the top of it -- lay a hatch on a wash and both layers are still legible
    underneath, which is the one thing a pair of solid fills can never do. The hatch is what
    tells the two apart, which is why they can share a hue: an accent colour was carried here
    for a while, and it was the only mark in the manuscript that was not a step of the ramp.

    Cutting the two distributions into three solid patches -- "only the first", "only the
    second", "both" -- was the version before this one, and it hid what it was drawn to show:
    neither shape is ever actually drawn, so the reader has to reassemble two distributions
    from three pieces and there is nothing on the page to follow where one runs on beneath
    the other.

    Each shape is the smallest area enclosing `enclose` of that set's own observations, taken
    from the kernel density evaluated at the real points rather than from a share of peak
    density, so the same fraction means the same thing for both however differently they spread.

    `view` is the range the data occupies, not the axis limits. The grid runs past it and keeps
    widening until every ring closes: a kernel-smoothed 90% region reaches well beyond its own
    observations, and a fixed margin left the lower boundary running off the bottom of the grid,
    where the ring came back as an open line whose stroke simply stopped in mid-air. The frame
    the caller should set is handed back as "bounds", for the same reason -- how far a smoothed
    region reaches is not a thing to guess at twice.
    """
    from scipy.stats import gaussian_kde
    from contourpy import contour_generator
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path

    kernels = []
    for values_x, values_y in (first, second):
        sample = np.vstack([np.asarray(values_x, float), np.asarray(values_y, float)])
        kernel = gaussian_kde(sample)
        kernels.append((kernel, np.percentile(kernel(sample), 100 * (1 - enclose))))

    (view_x, view_y) = view
    width, height = view_x[1] - view_x[0], view_y[1] - view_y[0]
    for reach in (pad, 0.25, 0.45, 0.75):
        mesh_x, mesh_y = np.meshgrid(
            np.linspace(view_x[0] - reach * width, view_x[1] + reach * width, grid),
            np.linspace(view_y[0] - reach * height, view_y[1] + reach * height, grid))
        flat = np.vstack([mesh_x.ravel(), mesh_y.ravel()])
        fields = [kernel(flat).reshape(mesh_x.shape) - level for kernel, level in kernels]
        # contourpy rather than axis.contour(): the rings are wanted before anything is drawn,
        # and a ring cut by the edge of the grid comes back with its ends apart, which is the
        # test. Drawing first and looking afterwards is how the open one reached the page.
        rings = [contour_generator(mesh_x, mesh_y, field, line_type="Separate").lines(0.0)
                 for field in fields]
        if all(np.allclose(ring[0], ring[-1]) for shape in rings for ring in shape):
            break
    else:
        raise AssertionError("a region still runs off the grid at three quarters of the view")

    # The boundary is drawn by hand as a patch: contourf() will hatch a region but gives no say
    # over the hatch's colour or weight, and its default is a black scribble at the full
    # linewidth that buries a panel this size.
    styles = (dict(facecolor=RAMP[4], edgecolor=RAMP[2], hatch=None, zorder=1),
              dict(facecolor="none", edgecolor=RAMP[0], hatch="//////", zorder=2))
    for shape, style in zip(rings, styles):
        for ring in shape:
            axis.add_patch(PathPatch(Path(ring), linewidth=0.9, **style))

    corners = np.vstack([ring for shape in rings for ring in shape])
    low, high = corners.min(axis=0), corners.max(axis=0)
    margin = (high - low) * 0.03
    bounds = ((low[0] - margin[0], high[0] + margin[0]),
              (low[1] - margin[1], high[1] + margin[1]))

    seen = ((mesh_x >= bounds[0][0]) & (mesh_x <= bounds[0][1])
            & (mesh_y >= bounds[1][0]) & (mesh_y <= bounds[1][1]))
    alone = lambda mine, theirs: (mesh_x[(mine > 0) & (theirs < 0) & seen],
                                  mesh_y[(mine > 0) & (theirs < 0) & seen])
    return {"bounds": bounds,
            "first alone": alone(*fields),
            "second alone": alone(fields[1], fields[0])}


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
            colour = (palette or {}).get(name, RAMP[0])
            marker = marker_for(colour)
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
              color=DIM, lw=1.0, zorder=3)


def box(axis, frame, group, value, *, order=None, xlabel="", ylabel="", title=None, rotate=0):
    """Distribution of `value` per category, outliers hidden so the boxes stay readable."""
    order = order or list(frame[group].value_counts().index)
    axis.boxplot([frame[frame[group] == name][value].dropna() for name in order],
                 # full names: a label cut to six characters turns "methanolysis" into "methan"
                 tick_labels=[str(name) for name in order],
                 showfliers=False, widths=0.6, medianprops=dict(color=EMPHASIS))
    if rotate:
        axis.tick_params(axis="x", labelrotation=rotate)
    _finish(axis, xlabel, ylabel, title)


def bars(axis, series, *, colour=DATA, horizontal=False, xlabel="", ylabel="", title=None,
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


def note(axis, text, *, colour=DIM, x=0.03, y=0.04, ha="left"):
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
# which is the only honest definition of a stale figure: scripts/derive.sh --check used to pass
# over figure PDFs three days older than the macros beside them, because nothing compared them
# to anything.
STALE = []


def save(figure, name: str, *, legend_room=False):
    # x (and y) labels share a baseline across each row, which they do not by default: each one
    # sits under its own tick labels, so a panel whose ticks are taller pushes its label lower
    # than the panel beside it.
    figure.align_xlabels()
    figure.align_ylabels()
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


def histogram(axis, frame, column, *, bins=30, logx=False, clip=None, xlabel="", ylabel="records",
              colour=None, split=None, palette=None, order=None):
    """Distribution of one column, optionally stacked by a categorical.

    Stacking rather than overlaying: with three routes an overlay hides whichever is drawn first,
    and the question here is usually what the corpus as a whole looks like.
    """
    values = frame[column].dropna()
    if clip is not None:
        # a linear axis over six decades is a spike at zero, so the tail is cut at a stated
        # percentile. The count in the label stays the count of every record reporting the
        # field; what is excluded is said once, in the caption.
        ceiling = values.quantile(clip)
        frame = frame[frame[column] <= ceiling]
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
        # a hairline between stacked fills, so a step boundary is visible without a texture
        axis.hist(data, bins=edges, stacked=True, color=colours, label=groups,
                  edgecolor="white", linewidth=0.25)
    else:
        axis.hist(values, bins=edges, color=colour or DATA)

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


def grouped_bars(axis, frame, *, xlabel="", ylabel="", palette=None, rotate=0, errors=None,
                 names=None):
    """One cluster per row of `frame`, one bar per column -- for comparing a few measures across
    a few models, where a heatmap would be overkill and a line would imply an ordering.

    `names` replaces the legend with a label under every bar: pass a dict abbreviating each row,
    and each bar is named for its row and its series at once -- "P luna", "R luna" -- on the
    slant, one line, no second row of labels and no key. A legend above a cluster chart asks the
    reader to hold three or four swatches of one hue in their head and match them across the
    panel, which is the one thing this ramp is not built to support; a name under the bar is
    read where the eye already is and survives greyscale, a bad printer and any kind of colour
    blindness. Without `names` the panel falls back to a legend, since an unnamed series has to
    be identified somehow.

    `errors` is an optional frame of the same shape. Pass it whenever the numbers are means over
    repeats: four runs of one model at identical settings span 0.05 in F1 here, wider than the
    gap between two of the models, and a bare bar asserts a precision the data does not have.
    """
    rows, measures = list(frame.index), list(frame.columns)
    pitch = len(measures) + CLUSTER_GAP
    width = 0.84 if names else GROUP / len(measures)
    for offset, measure in enumerate(measures):
        positions = [i * pitch + offset for i in range(len(rows))] if names else \
            [i + offset * width - GROUP / 2 + width / 2 for i in range(len(rows))]
        colour = (palette or {}).get(measure, SHADES[offset % len(SHADES)])
        axis.bar(positions, frame[measure].values, width=width, label=str(measure),
                 color=colour, edgecolor="white", linewidth=0.25)
        if errors is not None and measure in errors:
            axis.errorbar(positions, frame[measure].values, yerr=errors[measure].values,
                          # fmt="none" still creates the data line, and with no colour given
                          # it takes the default cycle -- which put matplotlib's tab10 blue
                          # into the PDF's colour stream and off the palette. Named explicitly.
                          fmt="none", color=INK, ecolor=INK, elinewidth=0.7,
                          capsize=1.8, capthick=0.7, zorder=4)

    if names:
        _named_axis(axis, rows, measures, names)
    else:
        axis.set_xticks(range(len(rows)), [str(n) for n in rows])
        axis.legend(frameon=False, fontsize=6)
    if rotate:
        axis.tick_params(axis="x", labelrotation=rotate)
    _finish(axis, xlabel, ylabel)
    return axis


def _named_axis(axis, rows, measures, short, *, size=5.5):
    """One tilted label under each bar, naming its row and its series: "P luna", "F1 terra".

    The row's abbreviation rides on every label rather than sitting on a second row of ticks
    underneath, so the axis is one line deep and a reader never has to carry a bar up to a
    cluster heading to find out which measure it belongs to. The caption glosses the letters.

    The labels are drawn rather than hung on the minor ticks, because matplotlib drops a minor
    tick that lands on a major one -- and the middle bar of a three-bar cluster lands exactly on
    the cluster centre, which silently cost the middle series its name. No tick marks either:
    nine tick marks under nine bars is a row of ink saying what the bars already say.
    """
    pitch = len(measures) + CLUSTER_GAP
    labels = {(row, measure): f"{short.get(name, name)} {measure}"
              for row, name in enumerate(rows) for measure in measures}
    for (row, measure), label in labels.items():
        axis.annotate(label, (row * pitch + measures.index(measure), 0),
                      xycoords=axis.get_xaxis_transform(), textcoords="offset points",
                      xytext=(0, -3), rotation=TILT, rotation_mode="anchor", ha="right",
                      va="top", fontsize=size, color=DIM, annotation_clip=False)

    # Tilted labels hang down and to the left, and tight_layout does not know they are there,
    # so the left margin is opened by however far the longest of them reaches: without this the
    # first bar's label runs out under the y axis and lands on its bottom tick label.
    span = (len(rows) - 1) * pitch + len(measures) - 1
    wide = axis.get_position().width * axis.figure.get_figwidth() * 72      # axes width, points
    reach = max(len(label) for label in labels.values()) * size * 0.62
    axis.set_xticks([])
    axis.set_xlim(-max(0.9, reach * np.cos(np.radians(TILT)) / (wide / (span + 1.8))),
                  span + 0.9)
    return axis


def bracket(axis, left, right, y, text, *, drop=0.035, colour=DIM, size=5.8):
    """A significance bracket spanning two bars, with the p-value on it.

    The conventional mark for a paired test, and the only place in the panel where a p-value
    points at the comparison it is about. It used to be a line of grey text across the top of
    the panel, where it read as a title and belonged to nothing.
    """
    tick = drop * (axis.get_ylim()[1] - axis.get_ylim()[0])
    axis.plot([left, left, right, right], [y - tick, y, y, y - tick], color=colour, lw=0.6,
              solid_joinstyle="miter", zorder=4)
    axis.annotate(text, ((left + right) / 2, y), textcoords="offset points", xytext=(0, 2),
                  ha="center", va="bottom", fontsize=size, color=colour)
    return axis


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
    colour = colour or DATA
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


def step_hist(axis, values, *, bins=30, colour=DATA, xlabel="", ylabel="records", logx=False,
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


def _lightness(hexc: str) -> float:
    """CIE L* of a hex colour. The one number that decides whether two fills are separable in
    greyscale and under every kind of colour blindness."""
    channels = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y


if __name__ == "__main__":
    # The palette rule, asserted rather than described. Separability is not asserted here --
    # _palette.py computes it, and this defers to that rather than restating a threshold.
    from _palette import oklab, report

    problems = report(CATEGORICAL)
    assert not problems, "CATEGORICAL fails _palette.py:\n  " + "\n  ".join(problems)

    assert list(CATEGORICAL) == ["blue", "red", "yellow", "purple"], "slot order is fixed"
    assert DATA == CATEGORICAL["blue"], "one series is blue, everywhere"
    assert ROUTE == dict(zip(ROUTES, SLOTS[:3])) | {OTHER_ROUTE: DIM}
    assert SHADES == RAMP[:4] and CYCLE == SLOTS[:3]
    assert EMPHASIS in RAMP, "emphasis is weight within the ramp, not a new hue"

    # a ramp is for ordered data, so it has to run one way and be readable step to step
    levels = [oklab(colour)[0] for colour in RAMP]
    gaps = [b - a for a, b in zip(levels, levels[1:])]
    assert levels == sorted(levels), "the ramp must run dark to light"
    assert min(gaps) >= 10, f"ramp steps too close in lightness: {[round(g, 1) for g in gaps]}"

    # nothing that encodes no category carries a marker shape
    assert marker_for(DIM) == "o" and marker_for(RULE) == "o"
    assert len({marker_for(c) for c in SLOTS[:3]}) == 3, "two routes share a marker"

    # drawn at the width it is printed at, so nothing is scaled
    assert canvas(1, 1)[0].get_figwidth() == DOUBLE_COLUMN
    plt.close("all")
    print(f"_style self-check ok  (4 categorical hues pass _palette.py; "
          f"ramp L* gaps {[round(g, 1) for g in gaps]})")
