"""Trace-style system decomposition figure for the portfolio page.

This follows the visual language in the user's reference examples: real artifact thumbnails,
orange module boxes, compact arrows, and panel labels (a)-(e). It avoids a generic block diagram.

Run:
    .venv/bin/python eval/system_decomposition.py

Out:
    output/system_decomposition.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#f6a823"
ORANGE_DARK = "#ef7d00"
BLUE = "#56B4E9"
GREEN = "#2ca02c"
PURPLE = "#9467bd"


def _box(ax, x, y, w, h, title, body="", fc="#ffffff", ec=LINE, lw=1.2, title_size=9.8):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.006,rounding_size=0.012",
            fc=fc,
            ec=ec,
            lw=lw,
        )
    )
    ax.text(x + w / 2, y + h * 0.74, title, ha="center", va="center", fontsize=title_size + 1.2, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h * 0.37, body, ha="center", va="center", fontsize=9.0, color=MUTED, linespacing=1.15)


def _arrow(ax, x1, y1, x2, y2, color="#5f6670", lw=1.6):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=12,
            lw=lw,
            color=color,
            shrinkA=3,
            shrinkB=3,
        )
    )


def _img(ax, path: Path, x, y, w, h, title=None, crop=None):
    iax = ax.figure.add_axes([x, y, w, h])
    if path.exists():
        im = plt.imread(path)
        iax.imshow(im)
        if crop:
            iax.set_xlim(crop[0], crop[1])
            iax.set_ylim(crop[3], crop[2])
    else:
        iax.text(0.5, 0.5, path.name, ha="center", va="center", fontsize=8, color=MUTED)
    iax.set_xticks([])
    iax.set_yticks([])
    for s in iax.spines.values():
        s.set_edgecolor(LINE)
        s.set_linewidth(1.0)
    if title:
        iax.set_title(title, fontsize=7.6, pad=3, color=INK)
    return iax


def _mini_graph(ax, x, y, w, h):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012", fc="#ffffff", ec=LINE, lw=1.0))
    nodes = {
        "wall": (x + 0.18 * w, y + 0.58 * h, "#bdbdbd"),
        "target": (x + 0.50 * w, y + 0.40 * h, ORANGE_DARK),
        "prev": (x + 0.35 * w, y + 0.72 * h, "#9ecae1"),
        "next": (x + 0.70 * w, y + 0.66 * h, "#9ecae1"),
        "storey": (x + 0.78 * w, y + 0.28 * h, "#c9b5e3"),
    }
    edges = [("wall", "target", "FILLS"), ("target", "prev", "NEXT_TO"), ("target", "next", "NEXT_TO"), ("target", "storey", "ON_STOREY")]
    for a, b, lab in edges:
        xa, ya, _ = nodes[a]
        xb, yb, _ = nodes[b]
        ax.plot([xa, xb], [ya, yb], color="#aab3c0", lw=1.2)
        ax.text((xa + xb) / 2, (ya + yb) / 2 + 0.010, lab, fontsize=5.4, color=MUTED, ha="center")
    for name, (xx, yy, c) in nodes.items():
        ax.scatter([xx], [yy], s=150 if name == "target" else 95, color=c, edgecolor="white", lw=1.0, zorder=3)
        ax.text(xx, yy - 0.035, "target" if name == "target" else name, ha="center", fontsize=6.0, color=INK)
    ax.text(x + w / 2, y + 0.045 * h, "spatial address: Window · Second Floor · slot 2/17", ha="center", fontsize=7.0, color=PURPLE, fontweight="bold")


def build(out_path: Path):
    fig = plt.figure(figsize=(15.4, 8.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fig.text(0.5, 0.957, "AEC Interpreter: evidence trace through the system", ha="center", fontsize=18, fontweight="bold")
    fig.text(0.5, 0.925, "Raw input → module trace → typed field record → graph address → verified BIM element.",
             ha="center", fontsize=11.0, color=MUTED)

    xs = [0.035, 0.235, 0.445, 0.650, 0.815]
    labels = ["(a) Raw evidence", "(b) Cross-modal extraction", "(c) Spatial address", "(d) IFC graph retrieval", "(e) 3D verification"]
    for x, lab in zip(xs, labels):
        ax.text(x, 0.865, lab, fontsize=12.0, fontweight="bold", ha="left", color=INK)

    site_photo = REPO / "site/assets/dataset/AP_SK_102_site.png"
    case_panel = REPO / "site/assets/case_AP_SK_102.png"
    demo_hub = REPO / "site/assets/portfolio/fig-demo-hub.png"
    pipeline = REPO / "site/assets/pipeline.png"

    _img(ax, site_photo, 0.035, 0.605, 0.155, 0.205, "site photo")
    _img(ax, case_panel, 0.048, 0.365, 0.130, 0.175, "marked plan", crop=(735, 1125, 105, 480))
    _box(ax, 0.035, 0.215, 0.155, 0.090, "field note / query", "Which IFC window is shown\non Second Floor?", fc="#f7f9fc")

    # Program stack, orange like the reference examples.
    prog = [
        ("VLM.extract", "storey\nIFC class\nrelation"),
        ("OpenCV.slot", "count openings\nposition = 2 of 17"),
        ("Route", "confidence 0.57\nANSWER"),
    ]
    for i, (title, body) in enumerate(prog):
        y = 0.685 - i * 0.155
        _box(ax, 0.235, y, 0.155, 0.105, title, body, fc="#fff4e3", ec=ORANGE_DARK, lw=1.4)
        if i < 2:
            _arrow(ax, 0.312, y, 0.312, y - 0.045)

    _img(ax, case_panel, 0.405, 0.585, 0.070, 0.205, "opening count", crop=(250, 430, 1060, 1450))
    _box(ax, 0.405, 0.405, 0.150, 0.095, "typed field", "value=(2,17)\nconfidence=0.52\nsource=opencv", fc="#ffffff", ec=ORANGE_DARK)

    _mini_graph(ax, 0.445, 0.215, 0.165, 0.260)

    _box(ax, 0.650, 0.660, 0.135, 0.095, "Graph query", "Window\nSecond Floor\nhost wall", fc="#f3f0fa", ec=PURPLE)
    _box(ax, 0.650, 0.505, 0.135, 0.095, "Recall pool", "GT in pool\n100%", fc="#ffffff", ec=LINE)
    _box(ax, 0.650, 0.350, 0.135, 0.095, "Ranked result", "46 candidates\n→ 1 address", fc="#ffffff", ec=PURPLE)
    _arrow(ax, 0.718, 0.660, 0.718, 0.600, color=PURPLE)
    _arrow(ax, 0.718, 0.505, 0.718, 0.445, color=PURPLE)

    _img(ax, demo_hub, 0.815, 0.540, 0.145, 0.190, "BIM viewer")
    _img(ax, case_panel, 0.830, 0.290, 0.120, 0.155, "trace card", crop=(0, 820, 0, 760))
    _box(ax, 0.815, 0.160, 0.145, 0.085, "final output", "GUID returned with\n3D highlight for review", fc="#e8f6ec", ec=GREEN)

    # Stage arrows.
    _arrow(ax, 0.190, 0.640, 0.235, 0.735)
    _arrow(ax, 0.390, 0.735, 0.405, 0.690)
    _arrow(ax, 0.555, 0.450, 0.650, 0.705, color=PURPLE)
    _arrow(ax, 0.785, 0.390, 0.815, 0.205, color=GREEN)

    # Compact result strip.
    ax.add_patch(Rectangle((0.035, 0.055), 0.925, 0.045, fc="#f7f9fc", ec=LINE, lw=1.0))
    ax.text(0.052, 0.078, "Measured effect:", fontsize=8.5, fontweight="bold", color=INK, va="center")
    ax.text(0.150, 0.078, "VLM-only Top-1 6.7%  ·  + slot specialist 67.6%  ·  address ceiling 78.5% Top-1 / 98.1% Top-10",
            fontsize=9.2, color=MUTED, va="center")

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


def main():
    build(OUT / "system_decomposition.png")


if __name__ == "__main__":
    main()
