"""Intro figure: what multi-hop depth means, and why the address stays shallow (corrected mechanism).

Left  : a worked depth-expansion sample around one target node. Depth 0 is the node's own
        attributes; each added hop pulls in neighbours one more edge away.
Right : the CORRECTED depth law, from measured quantities (output/remeasure_2026-06-14.json):
        - the oracle confusable set |C| is already a SINGLETON at one hop (13 -> 1), so deeper hops
          add nothing in principle;
        - the deployed G8 model READS deep relation types reliably (96.7 / 93.9 / 69.6% at hop 1/2/3
          on AP held-out) -- recovery does NOT collapse with depth;
        - yet realized discrimination saturates at one hop because those relation types are
          type-homogeneous (every window FILLS a wall, every wall CONNECTS a wall) -> non-discriminative.
        The depth law is informational, not an extraction-reliability cascade.

Self-contained: oracle |C| from output/depth_saturation.json; per-hop recovery is the measured
held-out value (eval/realized_extracted_coarse.py / remeasure_2026-06-14.json).

Run:  .venv/bin/python eval/fig_depth_sample.py
Out:  output/depth_sample.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
RED = "#d62728"
BLUE = "#56B4E9"
GREEN = "#2ca02c"
PURPLE = "#9467bd"
GREY = "#b9bec6"

HOP_COL = [RED, ORANGE, BLUE, GREY]  # target, hop1, hop2, hop3
# measured G8 per-hop relation-type recovery on AP held-out (exact predicate+object+direction)
RECOVERY = {1: 96.7, 2: 93.9, 3: 69.6}
REL_COL = {"FILLS": ORANGE, "NEXT_TO": PURPLE, "CONNECTS_TO": BLUE, "ADJACENT_TO": GREEN}


def load_oracle():
    with open(OUT / "depth_saturation.json") as f:
        return json.load(f)["oracle_median_pool_by_depth"]


def load_neighborhood():
    with open(OUT / "depth_neighborhood.json") as f:
        return json.load(f)


def _flat_node(ax, x, y, r, fc, ec=INK, lw=1.1, z=3):
    # standard flat circle (no halo / sphere shading)
    ax.add_patch(Circle((x, y), r, fc=fc, ec=ec, lw=lw, zorder=z))


def _radial_layout(nbh):
    """Parent-anchored radial layout: real BFS shells, children clustered near their parent angle."""
    nodes = nbh["nodes"]
    by_hop = {d: [n["guid"] for n in nodes if n["hop"] == d] for d in range(nbh["depth"] + 1)}
    adj = {}
    for e in nbh["edges"]:
        adj.setdefault(e["u"], []).append(e["v"])
        adj.setdefault(e["v"], []).append(e["u"])
    radii = {0: 0.0, 1: 0.16, 2: 0.30, 3: 0.43}
    ang = {nbh["target"]: 0.0}
    pos = {nbh["target"]: (0.0, 0.0)}
    for d in range(1, nbh["depth"] + 1):
        if d == 1:
            kids = by_hop[1]
            for i, g in enumerate(kids):
                ang[g] = 2 * math.pi * i / max(len(kids), 1)  # spread over full circle
        else:
            # group children by their parent in hop d-1
            parents = {}
            for g in by_hop[d]:
                par = next((v for v in adj.get(g, []) if v in ang and _hop_of(v, nodes) == d - 1),
                           nbh["target"])
                parents.setdefault(par, []).append(g)
            for par, kids in parents.items():
                base = ang.get(par, 0.0)
                spread = 1.4
                for j, g in enumerate(kids):
                    off = (j - (len(kids) - 1) / 2) * (spread / max(len(kids), 1))
                    ang[g] = base + off
        for g in by_hop[d]:
            rad = radii[d]
            pos[g] = (rad * math.cos(ang[g]), rad * math.sin(ang[g]))
    # fit to a centred [0.10, 0.90] box (keep aspect by using one scale)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    s = 0.74 / span
    return {g: (0.5 + (x - cx) * s, 0.46 + (y - cy) * s) for g, (x, y) in pos.items()}


def _hop_of(g, nodes):
    for n in nodes:
        if n["guid"] == g:
            return n["hop"]
    return 99


def left_panel(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")          # so flat circles are round, not ellipses
    ax.axis("off")
    nbh = load_neighborhood()
    pos = _radial_layout(nbh)
    hop = {n["guid"]: n["hop"] for n in nbh["nodes"]}
    typ = {n["guid"]: n["type"] for n in nbh["nodes"]}
    tgt = nbh["target"]

    # real edges, coloured by relation type
    for e in nbh["edges"]:
        if e["u"] in pos and e["v"] in pos:
            p, q = pos[e["u"]], pos[e["v"]]
            ax.plot([p[0], q[0]], [p[1], q[1]], color=REL_COL.get(e["rel"], MUTED),
                    lw=1.1, alpha=0.7, zorder=1, solid_capstyle="round")

    # flat-circle nodes coloured by hop
    for g, (x, y) in pos.items():
        if g == tgt:
            continue
        _flat_node(ax, x, y, 0.020, fc=HOP_COL[hop[g]], z=3)
    tx, ty = pos[tgt]
    _flat_node(ax, tx, ty, 0.032, fc=RED, ec=INK, lw=1.5, z=5)
    ax.text(tx, ty, "?", ha="center", va="center", fontsize=10, fontweight="bold",
            color="white", zorder=6)

    # legend: hops + a relation colour key
    hc = nbh["hop_counts"]
    ax.text(0.02, 0.95, f"real neighbourhood of one window (case {nbh['case']})",
            fontsize=8.6, color=INK, ha="left", fontweight="bold")
    for d, lab in [(0, "depth 0 (target)"), (1, f"+hop 1 ({hc['1']})"),
                   (2, f"+hop 2 ({hc['2']})"), (3, f"+hop 3 ({hc['3']})")]:
        yy = 0.90 - d * 0.045
        ax.add_patch(Circle((0.05, yy), 0.013, fc=HOP_COL[d], ec=INK, lw=1.0))
        ax.text(0.085, yy, lab, fontsize=7.8, va="center", color=INK)
    # relation key
    rx = 0.72
    for i, (r, c) in enumerate([("FILLS", ORANGE), ("NEXT_TO", PURPLE),
                                ("CONNECTS_TO", BLUE), ("ADJACENT_TO", GREEN)]):
        yy = 0.92 - i * 0.045
        ax.plot([rx, rx + 0.04], [yy, yy], color=c, lw=2.0)
        ax.text(rx + 0.05, yy, r, fontsize=7.2, va="center", color=INK, family="monospace")

    ax.text(0.5, 0.04,
            "depth-n = nodes within n edges; types are homogeneous (every window FILLS a wall)\n→ reading deeper relations adds no discrimination",
            ha="center", va="center", fontsize=8.0, color=MUTED, style="italic")


def right_panel(ax):
    oracle = load_oracle()
    depths = [0, 1, 2, 3]
    oc = [oracle[str(k)] for k in depths]

    # oracle |C| line (left axis)
    ax.plot(depths, oc, marker="o", color=PURPLE, lw=2.2, ms=7,
            label="oracle |C| (graph-side discrimination)", zorder=5)
    for x, y in zip(depths, oc):
        ax.annotate(f"{y:g}", (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8.4, color=PURPLE, fontweight="bold")
    ax.set_ylim(-0.6, 14.5)
    ax.set_xlim(-0.15, 3.15)
    ax.set_xticks(depths)
    ax.set_xlabel("relational depth (hops)", fontsize=9.5)
    ax.set_ylabel("oracle confusable-set size  |C|", fontsize=9.5, color=PURPLE)
    ax.tick_params(axis="y", labelcolor=PURPLE)
    ax.spines["top"].set_visible(False)
    ax.grid(axis="y", alpha=0.13)

    # G8 recovery bars (right axis)
    ax2 = ax.twinx()
    xs = [1, 2, 3]
    rec = [RECOVERY[k] for k in xs]
    ax2.bar(xs, rec, width=0.34, color=ORANGE, alpha=0.55, zorder=2, label="G8 reads relation type (%)")
    for x, v in zip(xs, rec):
        ax2.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8.0, color="#b5651d", fontweight="bold")
    ax2.set_ylim(0, 119)
    ax2.set_ylabel("G8 per-hop type-recovery (%)", fontsize=9.5, color="#b5651d")
    ax2.tick_params(axis="y", labelcolor="#b5651d")
    ax2.spines["top"].set_visible(False)

    ax.axvline(1, color=MUTED, lw=1.0, ls=(0, (2, 3)), zorder=1)
    ax.text(1.07, 12.4, "oracle already\nsingleton here", fontsize=8.0, color=MUTED, va="top", style="italic")

    # combined legend
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=7.8, frameon=False)
    ax.set_title("recovery is high, but recovered relations don't discriminate", fontsize=10,
                 fontweight="bold", color=INK, pad=6)


def build(out_path: Path):
    fig = plt.figure(figsize=(11.2, 4.4))
    fig.suptitle("RQ3 — what “depth” means, and why the address stays shallow (depth ≤ 1)",
                 fontsize=14, fontweight="bold", y=0.99)
    axl = fig.add_axes([0.015, 0.04, 0.50, 0.86])
    axr = fig.add_axes([0.60, 0.17, 0.34, 0.64])
    left_panel(axl)
    right_panel(axr)
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "depth_sample.png")
