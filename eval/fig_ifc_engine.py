"""Section 2.3 figure: the IFC parse engine — from a linear file to a query-ready graph.

Three stages, left to right:
  (1) RAW IFC: a flat STEP file whose only navigable structure is the spatial-containment
      hierarchy (storey -> element). Shown as a text snippet + a sparse containment tree.
  (2) ENRICH: the engine mines the spatial topology the address needs. One card per derived
      relationship, each naming its IFC source rule and the edge count on the studied project.
  (3) ENRICHED GRAPH: the dense, query-ready property graph, edges coloured by relation type.

Self-contained: edge counts from output/depth_saturation.json; the two graphs are
representative layouts (fixed seed), the relation rules are the real derivation rules.

Run:  .venv/bin/python eval/fig_ifc_engine.py
Out:  output/ifc_engine.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
GREEN = "#2ca02c"
BLUE = "#1f7bc0"
RED = "#d62728"
PURPLE = "#9467bd"
TEAL = "#2A9D8F"
GOLD = "#E9C46A"

REL_COL = {
    "ON_STOREY": "#9aa3ad",
    "FILLS": ORANGE,
    "CONNECTS_TO": BLUE,
    "ADJACENT_TO": TEAL,
    "NEXT_TO": PURPLE,
}


def load_counts():
    d = json.load(open(OUT / "depth_saturation.json"))
    return d["edge_counts"]


def stage_raw(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.5, 0.97, "(1)  Raw IFC file", ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(0.5, 0.925, "linear STEP records — containment only", ha="center", fontsize=8.2, color=MUTED, style="italic")

    # text snippet
    ax.add_patch(FancyBboxPatch((0.04, 0.60), 0.92, 0.28, boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc="#1f2530", ec="none"))
    snippet = ("#142=IFCWINDOW('3kQ8c..',$,'Window_XL',...);\n"
               "#143=IFCWALLSTANDARDCASE('0aFb2..',...);\n"
               "#150=IFCRELFILLSELEMENT(#143,#142);\n"
               "#161=IFCRELCONTAINEDINSPATIAL\n"
               "       STRUCTURE(#9,(#142,#143),...);")
    ax.text(0.075, 0.74, snippet, fontsize=6.6, color="#d7e0ea", family="monospace", va="center", linespacing=1.35)

    # sparse containment tree
    storey = (0.5, 0.45)
    leaves = [(0.16, 0.16), (0.32, 0.16), (0.5, 0.16), (0.68, 0.16), (0.84, 0.16)]
    for lf in leaves:
        ax.plot([storey[0], lf[0]], [storey[1], lf[1]], color="#c2c8d0", lw=1.2, zorder=1)
    ax.add_patch(Circle(storey, 0.045, fc=GOLD, ec=INK, lw=1.2, zorder=3))
    ax.text(storey[0], storey[1] + 0.085, "IfcBuildingStorey", ha="center", fontsize=7.2, color=INK)
    for lf in leaves:
        ax.add_patch(Circle(lf, 0.030, fc="#dfe6ef", ec="#8a93a0", lw=1.0, zorder=3))
    ax.text(0.5, 0.045, "elements isolated — no spatial topology", ha="center", fontsize=7.6,
            color=RED, style="italic")


def _relcard(ax, x, y, w, h, name, rule, count):
    col = REL_COL[name]
    ax.add_patch(FancyBboxPatch((x + 0.012, y), w - 0.012, h,
                                boxstyle="round,pad=0.002,rounding_size=0.012",
                                fc="#ffffff", ec=col, lw=1.4, zorder=2))
    # left color strip
    ax.add_patch(plt.Rectangle((x, y), 0.012, h, color=col, zorder=3))
    ax.text(x + 0.03, y + h * 0.64, name, fontsize=8.8, fontweight="bold", color=col, ha="left", va="center", family="monospace")
    ax.text(x + 0.03, y + h * 0.30, rule, fontsize=6.6, color=MUTED, ha="left", va="center")
    ax.text(x + w - 0.025, y + h * 0.62, f"{count}", fontsize=9.4, fontweight="bold", color=INK, ha="right", va="center")
    ax.text(x + w - 0.025, y + h * 0.32, "edges", fontsize=6.2, color=MUTED, ha="right", va="center")


def stage_enrich(ax, counts):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.5, 0.97, "(2)  Enrich: mine spatial topology", ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(0.5, 0.925, "one derived relation per address need — schema rule + project edge count",
            ha="center", fontsize=8.2, color=MUTED, style="italic")
    cards = [
        ("ON_STOREY", "from IfcRelContainedInSpatialStructure", "—"),
        ("FILLS", "from IfcRelFills/VoidsElement chains", counts["FILLS"]),
        ("CONNECTS_TO", "from IfcRelConnectsPathElements", counts["CONNECTS_TO"]),
        ("NEXT_TO", "openings ordered along host wall", counts["NEXT_TO"]),
        ("ADJACENT_TO", "centroid distance < 1500 mm", counts["ADJACENT_TO"]),
    ]
    y0, h, gap = 0.745, 0.118, 0.028
    for i, (name, rule, cnt) in enumerate(cards):
        y = y0 - i * (h + gap)
        _relcard(ax, 0.05, y, 0.90, h, name, rule, cnt)


def stage_graph(ax, counts):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.5, 0.97, "(3)  Query-ready graph", ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(0.5, 0.925, "dense property graph (Neo4j) — zero-error, day-one", ha="center", fontsize=8.2,
            color=MUTED, style="italic")

    rng = np.random.default_rng(7)
    n = 22
    pos = rng.uniform(0.10, 0.90, size=(n, 2))
    pos[:, 1] = pos[:, 1] * 0.66 + 0.12  # keep within drawing band
    # build edges of varied types
    edges = []
    rel_types = ["FILLS", "CONNECTS_TO", "NEXT_TO", "ADJACENT_TO", "ON_STOREY"]
    for i in range(n):
        # connect each node to 1-2 nearby nodes
        d = np.hypot(pos[:, 0] - pos[i, 0], pos[:, 1] - pos[i, 1])
        order = np.argsort(d)
        for j in order[1:3]:
            t = rel_types[(i + j) % len(rel_types)]
            edges.append((i, int(j), t))
    for i, j, t in edges:
        ax.plot([pos[i, 0], pos[j, 0]], [pos[i, 1], pos[j, 1]], color=REL_COL[t], lw=1.1,
                alpha=0.75, zorder=1)
    # nodes; one highlighted target
    tgt = 5
    for k in range(n):
        if k == tgt:
            ax.add_patch(Circle(pos[k], 0.032, fc=RED, ec=INK, lw=1.4, zorder=4))
        else:
            ax.add_patch(Circle(pos[k], 0.020, fc="#5b9bd5", ec="white", lw=0.8, zorder=3))
    ax.text(pos[tgt, 0], pos[tgt, 1] + 0.055, "target", ha="center", fontsize=7.2, color=RED, fontweight="bold")

    # legend
    yL = 0.085
    items = ["FILLS", "CONNECTS_TO", "NEXT_TO", "ADJACENT_TO", "ON_STOREY"]
    for i, t in enumerate(items):
        xL = 0.06 + (i % 3) * 0.32
        row = i // 3
        yy = yL - row * 0.045
        ax.plot([xL, xL + 0.04], [yy, yy], color=REL_COL[t], lw=2.2)
        ax.text(xL + 0.05, yy, t, fontsize=6.6, color=INK, va="center", family="monospace")


def build(out_path: Path):
    counts = load_counts()
    fig = plt.figure(figsize=(12.6, 4.6))
    fig.text(0.5, 0.975, "IFC parse engine:  a linear file  →  a query-ready spatial graph",
             ha="center", fontsize=14.5, fontweight="bold", color=INK)

    axL = fig.add_axes([0.015, 0.02, 0.285, 0.86])
    axM = fig.add_axes([0.350, 0.02, 0.300, 0.86])
    axR = fig.add_axes([0.700, 0.02, 0.290, 0.86])
    stage_raw(axL)
    stage_enrich(axM, counts)
    stage_graph(axR, counts)

    # big arrows between stages
    for x0 in (0.312, 0.662):
        fig.add_artist(FancyArrowPatch((x0, 0.46), (x0 + 0.032, 0.46), transform=fig.transFigure,
                                       arrowstyle="-|>", mutation_scale=20, lw=2.4, color="#444"))

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "ifc_engine.png")
