"""Figure 5 (rebuilt, REAL knowledge graph): module decomposition as graph reasoning.

Driven by one real held-out case (AP_SK_092, a window). The layout is the ACTUAL knowledge graph,
not a random scatter: the confusable windows (same storey+class) are clustered by their host wall via
real FILLS edges (window->wall hub) and NEXT_TO edges (consecutive openings along a wall). Positions
come from a force-directed (spring) layout on those real edges and are FIXED across all four stages,
so the same graph is progressively filtered and the target is tracked.

  (1) retrieved pool        76 candidates (recall-safe; GT in-pool), Top-1 ~5%
  (2) confusable set        46 share storey + class -> 6 wall-hub clusters; ontology can't separate
  (3) position-slot         the target's host wall is a 10-opening NEXT_TO chain; the slot (8 of 10) picks it
  (4) found                 target at rank 1 (oracle address Top-1 78.5%)

Counts/edges are real (rerank_prize.pool_candidates + position_index); accuracy from
spatial_address_ceiling.json.

Run:  .venv/bin/python eval/fig_graph_reasoning.py
Out:  output/graph_reasoning.png
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from rerank_prize import load_index, load_cases, pool_candidates, cand_feats, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

OUT = REPO / "output"
CASE = "AP_SK_092"

INK = "#1a1c20"
MUTED = "#5b6470"
LINE = "#d8dde5"
ORANGE = "#ef7d00"
GREEN = "#2ca02c"
BLUE = "#1f7bc0"
RED = "#d62728"
GREY = "#c7ccd3"
SIB = "#f4a261"
WALL = "#3a3f47"


def build_real_graph():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    c = next(x for x in cases if x["scenario_id"] == CASE)
    gt = c["scenario"]["ground_truth"]["target_guid"]
    pool = pool_candidates(c)
    gf = cand_feats(gt, pool[gt], idx, None)

    conf = [g for g in pool if cand_feats(g, pool[g], idx, None).get("storey") == gf.get("storey")
            and cand_feats(g, pool[g], idx, None).get("ifc_class") == gf.get("ifc_class")]
    conf_pos = [g for g in conf if g in pos]
    others = [g for g in pool if g not in conf]  # ontology already separates these (other class)

    G = nx.Graph()
    by_wall = defaultdict(list)
    for g in conf_pos:
        w = pos[g]["wall_guid"]
        by_wall[w].append((pos[g]["wall_position_index"], g))
        G.add_node(g, kind="window")
        G.add_node(w, kind="wall")
        G.add_edge(g, w, rel="FILLS")
    for w, lst in by_wall.items():
        lst.sort()
        for (_, a), (_, b) in zip(lst, lst[1:]):
            G.add_edge(a, b, rel="NEXT_TO")

    layout = nx.spring_layout(G, seed=7, k=0.9, iterations=200)
    # normalise to [0.08, 0.92]
    xy = np.array(list(layout.values()))
    mn, mx = xy.min(0), xy.max(0)
    span = (mx - mn).max() or 1.0
    P = {n: ((p[0] - mn[0]) / span * 0.78 + 0.11, (p[1] - mn[1]) / span * 0.78 + 0.11)
         for n, p in layout.items()}

    target_wall = pos[gt]["wall_guid"]
    ordered = sorted(by_wall[target_wall])         # (wall_position_index, guid) in NEXT_TO order
    chain = [g for _, g in ordered]
    chain_idx = [i for i, _ in ordered]            # the REAL wall_position_index of each opening
    return {
        "G": G, "pos2d": P, "gt": gt, "target_wall": target_wall, "chain": chain,
        "chain_idx": chain_idx,
        "windows": conf_pos, "walls": list(by_wall), "others": others,
        "n_pool": len(pool), "n_conf": len(conf),
        "slot": (pos[gt]["wall_position_index"], pos[gt]["wall_child_total"]),
    }


def _t1():
    m = json.load(open(OUT / "spatial_address_ceiling.json"))["metrics_overall"]
    return m["coarse_storey_class"]["top1"], m["plus_spatial_address"]["top1"]


def _draw(ax, D, stage, other_xy):
    if stage >= 3:
        _draw_zoom(ax, D, stage)
    else:
        _draw_overview(ax, D, stage, other_xy)


def _draw_overview(ax, D, stage, other_xy):
    """Stages 1-2: the whole knowledge graph (force-directed), progressively highlighted."""
    G, P, gt = D["G"], D["pos2d"], D["gt"]
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")
    chain, twall = D["chain"], D["target_wall"]

    o_alpha = 0.55 if stage == 1 else 0.12
    for (ox, oy) in other_xy:
        ax.add_patch(Circle((ox, oy), 0.011, fc=GREY, ec="none", alpha=o_alpha, zorder=1))

    for u, v, d in G.edges(data=True):
        if u not in P or v not in P:
            continue
        if stage == 2:
            col, lw, a = ("#c9b48f" if d["rel"] == "NEXT_TO" else "#d7dbe1"), 0.8, 0.7
        else:
            col, lw, a = LINE, 0.8, 0.7
        ax.plot([P[u][0], P[v][0]], [P[u][1], P[v][1]], color=col, lw=lw, alpha=a,
                zorder=2, solid_capstyle="round")

    for n in G.nodes:
        x, y = P[n]
        if n == gt:
            continue
        is_wall = G.nodes[n]["kind"] == "wall"
        if stage == 2:
            fc, r, z = (WALL, 0.020, 4) if is_wall else (SIB, 0.016, 3)
        else:
            fc, r, z = ((WALL if is_wall else GREY), (0.018 if is_wall else 0.013), 3)
        ax.add_patch(Circle((x, y), r, fc=fc, ec="white", lw=0.5, zorder=z))

    tx, ty = P[gt]
    ax.add_patch(Circle((tx, ty), 0.030, fc=RED, ec=INK, lw=1.4, zorder=6))
    # a dashed box around the target's cluster to cue the zoom in panels 3-4
    if stage == 2:
        cx = [P[n][0] for n in chain] + [P[twall][0]]
        cy = [P[n][1] for n in chain] + [P[twall][1]]
        from matplotlib.patches import Rectangle
        pad = 0.04
        ax.add_patch(Rectangle((min(cx) - pad, min(cy) - pad), max(cx) - min(cx) + 2 * pad,
                               max(cy) - min(cy) + 2 * pad, fill=False, ec=ORANGE, lw=1.2,
                               ls=(0, (3, 2)), zorder=7))


def _draw_zoom(ax, D, stage):
    """Stages 3-4: ZOOM into the target's host-wall cluster. The openings are laid out in their REAL
    NEXT_TO order (1..M) along the wall — a clean, physically-faithful chain (positions schematic,
    ordering real) so the position-slot reads directly."""
    gt, chain, chain_idx = D["gt"], D["chain"], D["chain_idx"]
    slot_i, slot_M = D["slot"]
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal"); ax.axis("off")
    r = 0.05
    M = len(chain)
    # openings on a gentle arc, ordered left->right by NEXT_TO; wall hub below
    xs = [0.10 + 0.80 * (i / max(M - 1, 1)) for i in range(M)]
    ys = [0.66 + 0.05 * math.sin(math.pi * i / max(M - 1, 1)) for i in range(M)]
    pos = {n: (xs[i], ys[i]) for i, n in enumerate(chain)}
    hub = (0.5, 0.30)

    # the wall (a bar) + FILLS spokes to each opening
    ax.plot([0.06, 0.94], [0.30, 0.30], color=WALL, lw=8, solid_capstyle="round", zorder=1)
    for n in chain:
        ax.plot([pos[n][0], pos[n][0]], [pos[n][1], 0.34], color="#cdb392", lw=1.0, alpha=0.7, zorder=1)
    ax.text(0.5, 0.205, "host wall  (each opening FILLS it)", ha="center", fontsize=7.4,
            color=WALL, fontweight="bold")

    # NEXT_TO chain (clean, ordered)
    for a, b in zip(chain, chain[1:]):
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color=ORANGE, lw=2.2, alpha=0.9,
                zorder=2, solid_capstyle="round")
    ax.text(0.5, 0.83, "NEXT_TO  (openings ordered along the wall)", ha="center", fontsize=7.4,
            color="#b5651d", fontweight="bold")

    # openings labelled by their REAL wall_position_index; highlight the slot
    for n, real_idx in zip(chain, chain_idx):
        x, y = pos[n]
        if n == gt:
            rcol = GREEN if stage == 4 else RED
            ax.add_patch(Circle((x, y), r * 1.25, fc=rcol, ec=INK, lw=1.6, zorder=6))
            ax.text(x, y, ("✓" if stage == 4 else str(real_idx)), ha="center", va="center",
                    fontsize=10, color="white", fontweight="bold", zorder=7)
        else:
            ax.add_patch(Circle((x, y), r, fc=SIB, ec="#c47d33", lw=0.8, zorder=4))
            ax.text(x, y, str(real_idx), ha="center", va="center", fontsize=7.6, color="#5a3c14", zorder=5)

    tx, ty = pos[gt]
    if stage == 3:
        ax.annotate(f"slot {slot_i} of {slot_M}", xy=(tx, ty + r), xytext=(tx, ty + 0.20),
                    ha="center", fontsize=9, color=RED, fontweight="bold",
                    arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.2), zorder=8)
    else:
        ax.annotate("ANSWER", xy=(tx, ty - r), xytext=(tx + 0.20, 0.50),
                    ha="center", va="center", fontsize=8.4, color="white", fontweight="bold", zorder=8,
                    arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.2),
                    bbox=dict(boxstyle="round,pad=0.3", fc=GREEN, ec="none"))


def _label(fig, x, top, bot, color=INK):
    fig.text(x, 0.205, top, ha="center", fontsize=10, fontweight="bold", color=color)
    fig.text(x, 0.075, bot, ha="center", fontsize=8.0, color=MUTED)


def _modulestrip(fig, x, text, color):
    fig.add_artist(FancyBboxPatch((x - 0.105, 0.86), 0.21, 0.066, transform=fig.transFigure,
                                  boxstyle="round,pad=0.004,rounding_size=0.02", fc="#ffffff",
                                  ec=color, lw=1.4))
    fig.text(x, 0.893, text, ha="center", va="center", fontsize=8.2, color=color, fontweight="bold")


def build(out_path: Path):
    D = build_real_graph()
    coarse_t1, addr_t1 = _t1()
    # fixed peripheral positions for the non-confusable pool elements (reproducible)
    rng = np.random.default_rng(3)
    ang = np.linspace(0, 2 * np.pi, len(D["others"]), endpoint=False)
    rad = 0.46 + 0.02 * rng.standard_normal(len(D["others"]))
    other_xy = [(0.5 + r * np.cos(a), 0.5 + r * np.sin(a)) for a, r in zip(ang, rad)]

    fig = plt.figure(figsize=(13.0, 4.8))
    fig.text(0.5, 0.965, f"Module decomposition as graph reasoning — the real knowledge graph (case {CASE})",
             ha="center", fontsize=13.5, fontweight="bold", color=INK)

    centers = [0.13, 0.385, 0.64, 0.895]
    _modulestrip(fig, centers[0], "symbolic: recall-safe pool", BLUE)
    _modulestrip(fig, centers[1], "ontology: storey + class", MUTED)
    _modulestrip(fig, centers[2], "topology: position-slot", ORANGE)
    _modulestrip(fig, centers[3], "routing: answer / defer", GREEN)

    w = 0.215
    for i, c in enumerate(centers, start=1):
        ax = fig.add_axes([c - w / 2, 0.25, w, 0.56])
        _draw(ax, D, i, other_xy)

    _label(fig, centers[0], "① retrieved pool", f"{D['n_pool']} candidates · GT in-pool 100% · Top-1 {coarse_t1:g}%")
    _label(fig, centers[1], "② confusable set", f"{D['n_conf']} share storey+class · {len(D['walls'])} wall clusters", color=INK)
    _label(fig, centers[2], "③ position-slot", f"target wall = {D['slot'][1]}-opening NEXT_TO chain", color=ORANGE)
    _label(fig, centers[3], "④ found", f"target at rank 1 · Top-1 {addr_t1:g}%", color=GREEN)

    for x0, x1 in zip([0.238, 0.493, 0.748], [0.278, 0.533, 0.788]):
        fig.add_artist(FancyArrowPatch((x0, 0.50), (x1, 0.50), transform=fig.transFigure,
                                       arrowstyle="-|>", mutation_scale=18, lw=2.2, color="#555"))

    # legend
    items = [(RED, "target"), (SIB, "same-class window"), (WALL, "host wall (FILLS hub)"),
             (GREY, "other pool element")]
    x0 = 0.31
    for col, lab in items:
        fig.add_artist(Circle((x0, 0.035), 0.008, transform=fig.transFigure, fc=col, ec="white"))
        fig.text(x0 + 0.013, 0.035, lab, va="center", fontsize=8, color=INK)
        x0 += 0.025 + 0.011 * len(lab)
    fig.text(0.895, 0.035, "edges: FILLS · NEXT_TO (real)", va="center", ha="right", fontsize=7.6,
             color=MUTED, style="italic")

    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figure →", out_path)


if __name__ == "__main__":
    build(OUT / "graph_reasoning.png")
