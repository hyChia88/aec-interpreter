"""Demo interface mock — the spatial-address grounding dashboard (offline, no GPU).

Renders one 3x3 "case card" per held-out target, mocking the live interface panel
(ROADMAP Sec.4). Every panel is labelled by epistemic status:
  REAL    raw inputs, GT spatial address, expected local graph, |C| collapse, Top-1
  ORACLE  the "predicted address" = perfect extraction (NOT a learned prediction yet)
  REALIZED  what G8 actually extracted, from the frozen trace (the honest contrast)
  PENDING  attention heatmap / segmentation tiles reserved for the P2 learned extractor

Drives entirely from data we already have: held-out traces + element_index +
position_index + wall_fingerprint + reconstructed IFC edges + dataset images.
"""
from __future__ import annotations
import json
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import networkx as nx

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          realized_rank, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint, wall_address
from spatial_address_ceiling import spatial_address, subgroup, DEFAULT_POS, DEFAULT_WALL
from depth_saturation import load_universe, DEFAULT_IFC
from collections import defaultdict


def build_light_edges(pos: dict) -> dict[str, list[tuple[str, str]]]:
    """Real FILLS + NEXT_TO edges from the reconstructed position_index (no ifcopenshell).
    CONNECTS_TO / ADJACENT_TO between walls live only in the enriched graph (see ROADMAP)."""
    nbrs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    by_wall: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for f, p in pos.items():
        w = p["wall_guid"]
        nbrs[f].append((w, "FILLS"))
        nbrs[w].append((f, "FILLS"))
        by_wall[w].append((p["wall_position_index"], f))
    for w, fills in by_wall.items():
        fills.sort()
        for (_, a), (_, b) in zip(fills, fills[1:]):
            nbrs[a].append((b, "NEXT_TO"))
            nbrs[b].append((a, "NEXT_TO"))
    return {k: list(dict.fromkeys(v)) for k, v in nbrs.items()}

REPO = EVAL.parent
DATASET = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap")
OUT = REPO / "output" / "demo"

EDGE_COLOR = {"FILLS": "#d62728", "CONNECTS_TO": "#1f77b4",
              "NEXT_TO": "#ff7f0e", "ADJACENT_TO": "#2ca02c"}


def short_cls(c: str | None) -> str:
    return (c or "?").replace("IfcWallStandardCase", "Wall").replace("Ifc", "")


def addr_str(guid, pos, wallfp):
    a = spatial_address(guid, pos, wallfp)
    if a is None:
        return "(no structured address)"
    if a[0] == "pos":
        return f"slot {a[1]} of {a[2]} along host wall"
    fp = wallfp.get(guid, {})
    ext = "external" if fp.get("is_external") else "internal"
    return (f"degree {a[1]} · {a[2]} openings\n{a[3]} length · {ext}")


def site_img(sid):
    return DATASET / "imgs" / f"{sid}_site.png"


def plan_img(sid):
    return DATASET / "floorplans" / f"{sid}_floorplan.png"


def _img_panel(ax, path, title, tag):
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left")
    if path.exists():
        ax.imshow(plt.imread(path))
    else:
        ax.text(0.5, 0.5, "(image not found)", ha="center", va="center")
    ax.set_xticks([]); ax.set_yticks([])
    _tag(ax, tag)


def _tag(ax, tag):
    colors = {"REAL": "#2ca02c", "ORACLE": "#9467bd",
              "REALIZED": "#1f77b4", "PENDING": "#999999"}
    ax.text(0.99, 1.018, tag, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8, fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.25", fc=colors.get(tag, "#555"), ec="none"))


def _text_panel(ax, title, lines, tag):
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left")
    ax.axis("off")
    y = 0.95
    for txt, kw in lines:
        kw = {"fontsize": 10, **kw}
        ax.text(0.02, y, txt, transform=ax.transAxes, va="top", **kw)
        y -= 0.085 * (1 + txt.count("\n"))
    _tag(ax, tag)


def graph_panel(ax, gt, universe, nbrs, pos, wallfp):
    ax.set_title("Spatial address — sub-graph (depth-1) → node.val", fontsize=11,
                 fontweight="bold", loc="left")
    ax.axis("off")
    edges = nbrs.get(gt, [])[:8]
    G = nx.Graph()
    G.add_node(gt)
    for other, et in edges:
        G.add_node(other)
        G.add_edge(gt, other, etype=et)
    if len(G) == 1:
        ax.text(0.5, 0.5, "(no reconstructed edges)", ha="center", va="center", transform=ax.transAxes)
        _tag(ax, "REAL"); return
    layout = nx.spring_layout(G, seed=3, k=1.2)
    for u, v, d in G.edges(data=True):
        x1, y1 = layout[u]; x2, y2 = layout[v]
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-",
                     color=EDGE_COLOR.get(d["etype"], "#555"), lw=2.2, alpha=.85,
                     connectionstyle="arc3,rad=0.05"))
        ax.text((x1+x2)/2, (y1+y2)/2, d["etype"], fontsize=7,
                color=EDGE_COLOR.get(d["etype"], "#555"), ha="center")
    for n, (x, y) in layout.items():
        is_t = n == gt
        ax.scatter([x], [y], s=1000 if is_t else 520,
                   c="#d62728" if is_t else "#cccccc",
                   edgecolors="black", zorder=3, linewidths=1.5)
        ax.text(x, y, short_cls(universe.get(n, {}).get("ifc_class")),
                ha="center", va="center", fontsize=8,
                fontweight="bold" if is_t else "normal", zorder=4)
    # node.val on the target = the distilled address (the matched form)
    tx, ty = layout[gt]
    nodeval = addr_str(gt, pos, wallfp).replace("\n", "  ")
    ax.annotate("node.val = " + nodeval, (tx, ty), textcoords="offset points",
                xytext=(0, -22), ha="center", fontsize=8.5, color="#9467bd",
                fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc="#f1ecf9", ec="#9467bd", lw=0.8))
    ax.text(0.0, -0.03, "● target   edges = depth-1 relations (FILLS/NEXT_TO…)",
            transform=ax.transAxes, color="#555", fontsize=8)
    ax.margins(0.22)
    _tag(ax, "REAL")


def collapse_panel(ax, gt, pool, idx, pos, wallfp):
    ax.set_title("Confusable set |C| collapse", fontsize=11, fontweight="bold", loc="left")
    gf = cand_feats(gt, pool[gt], idx, pos)
    gaddr = spatial_address(gt, pos, wallfp)
    n_full = len(pool)
    n_sc = sum(1 for g, tc in pool.items()
               if cand_feats(g, tc, idx, pos).get("storey") == gf.get("storey")
               and cand_feats(g, tc, idx, pos).get("ifc_class") == gf.get("ifc_class"))
    n_addr = sum(1 for g, tc in pool.items()
                 if cand_feats(g, tc, idx, pos).get("storey") == gf.get("storey")
                 and cand_feats(g, tc, idx, pos).get("ifc_class") == gf.get("ifc_class")
                 and spatial_address(g, pos, wallfp) == gaddr)
    vals = [n_full, n_sc, max(n_addr, 1)]
    labels = ["retrieved\npool", "+ storey\n+ class", "+ spatial\naddress"]
    bars = ax.barh(range(3), vals, color=["#cccccc", "#7fb3d5", "#9467bd"])
    ax.set_yticks(range(3)); ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + max(vals)*0.01, b.get_y()+b.get_height()/2,
                str(v), va="center", fontsize=10, fontweight="bold")
    ax.set_xlabel("# indistinguishable candidates", fontsize=9)
    ax.set_xlim(0, max(vals)*1.15)
    _tag(ax, "ORACLE")
    return n_full, n_sc, max(n_addr, 1)


def top1_panel(ax, case, gt, n_sc, n_addr):
    ax.set_title("Expected Top-1 (this case)", fontsize=11, fontweight="bold", loc="left")
    h, t = realized_rank(case, gt)
    realized = 100.0 / (h + t + 1) if (h + t + 1) else 0.0
    sc = 100.0 / n_sc
    addr = 100.0 / n_addr
    bars = ax.bar(range(3), [realized, sc, addr],
                  color=["#1f77b4", "#7fb3d5", "#9467bd"])
    ax.set_xticks(range(3))
    ax.set_xticklabels(["G8\nrealized", "storey\n+class", "+address\n(oracle)"], fontsize=9)
    for b, v in zip(bars, [realized, sc, addr]):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+2, f"{v:.0f}%",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 110); ax.set_ylabel("expected Top-1 %", fontsize=9)
    _tag(ax, "REAL")


def predicted_panel(ax, case, gt, idx, pos, wallfp):
    ax.set_title("Predicted vs GT (G8 realized extraction)", fontsize=11, fontweight="bold", loc="left")
    ax.axis("off")
    con = case.get("internals", {}).get("constraints", {}) or {}
    e = idx.get(gt, {})
    sg = subgroup(gt, pos, wallfp)
    if sg == "wall":  # discriminating field for walls = connection degree
        rels = con.get("spatial_relations") or [{}]
        pred_disc = str(rels[0].get("connection_degree"))
        gt_disc = f"degree {wallfp.get(gt, {}).get('connection_degree', '?')}"
        disc_field = "connection_degree"
    else:             # discriminating field for fillers = position slot
        pred_disc = str(con.get("position_context"))
        gt_disc = addr_str(gt, pos, wallfp).replace("\n", " ")[:22]
        disc_field = "position_context"
    rows = [
        ("field", "G8 predicted", "ground truth"),
        ("storey", str(con.get("storey_name")), short_cls(e.get("storey_name"))),
        ("ifc_class", short_cls(con.get("ifc_class")), short_cls(e.get("ifc_class"))),
        (disc_field, pred_disc, gt_disc),
    ]
    y = 0.92
    for i, (a, b, c) in enumerate(rows):
        head = i == 0
        miss = (not head) and a == disc_field and str(b).lower() in ("none", "null", "")
        ax.text(0.02, y, a, transform=ax.transAxes, fontsize=9,
                fontweight="bold" if head else "normal", va="top")
        ax.text(0.40, y, b, transform=ax.transAxes, fontsize=9, va="top",
                color="#d62728" if miss else "black",
                fontweight="bold" if head else "normal")
        ax.text(0.74, y, c, transform=ax.transAxes, fontsize=9, va="top",
                fontweight="bold" if head else "normal")
        y -= 0.12
    ax.text(0.02, y-0.02, "↑ G8 leaves the discriminating field empty —\nthat is the gap the extractor closes.",
            transform=ax.transAxes, fontsize=8.5, color="#d62728", va="top")
    _tag(ax, "REALIZED")


def pending_panel(ax, title, body):
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor("#f3f3f3")
    for s in ax.spines.values():
        s.set_linestyle((0, (4, 4))); s.set_color("#bbbbbb")
    ax.text(0.5, 0.5, body, ha="center", va="center", fontsize=10, color="#888888")
    _tag(ax, "PENDING")


def render_case(case, idx, universe, nbrs, pos, wallfp):
    sid = case["scenario_id"]
    gt = case["scenario"]["ground_truth"]["target_guid"]
    pool = pool_candidates(case)
    if gt not in pool:
        return None
    e = idx.get(gt, {})
    sg = subgroup(gt, pos, wallfp)
    query = case["scenario"].get("query_text", "")

    fig = plt.figure(figsize=(17, 14))
    fig.suptitle(f"AEC Interpreter — spatial-address grounding   |   case {sid}   "
                 f"({short_cls(e.get('ifc_class'))}, {sg})",
                 fontsize=15, fontweight="bold", y=0.985)
    gs = fig.add_gridspec(3, 3, hspace=0.32, wspace=0.18,
                          left=0.04, right=0.97, top=0.92, bottom=0.05)

    _img_panel(fig.add_subplot(gs[0, 0]), site_img(sid), "Raw input — site photo", "REAL")
    _img_panel(fig.add_subplot(gs[0, 1]), plan_img(sid),
               "Raw input — human-marked plan (designed input)", "REAL")
    _text_panel(fig.add_subplot(gs[0, 2]), "Ground truth — spatial address", [
        (textwrap.fill("query: " + query, 46), dict(style="italic", fontsize=8.5)),
        (f"GUID  {gt}", dict(fontsize=8)),
        (f"class  {short_cls(e.get('ifc_class'))}   storey  {short_cls(e.get('storey_name'))}",
         dict()),
        (f"object_type  {(e.get('object_type') or '?')[:34]}", dict(fontsize=8.5)),
        ("ADDRESS:", dict(fontweight="bold", color="#9467bd")),
        (addr_str(gt, pos, wallfp), dict(fontweight="bold", color="#9467bd")),
    ], "REAL")

    graph_panel(fig.add_subplot(gs[1, 0]), gt, universe, nbrs, pos, wallfp)
    n_full, n_sc, n_addr = collapse_panel(fig.add_subplot(gs[1, 1]), gt, pool, idx, pos, wallfp)
    top1_panel(fig.add_subplot(gs[1, 2]), case, gt, n_sc, n_addr)

    predicted_panel(fig.add_subplot(gs[2, 0]), case, gt, idx, pos, wallfp)
    pending_panel(fig.add_subplot(gs[2, 1]), "Attention heatmap",
                  "P2 — VLM cross-attention\n(pending learned extractor)")
    pending_panel(fig.add_subplot(gs[2, 2]), "Opening / element segmentation",
                  "P2 — segmentation overlay\n(pending learned extractor)")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"case_{sid}.png"
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    universe = load_universe(DEFAULT_INDEX)
    nbrs = build_light_edges(pos)

    by = {c["scenario_id"]: c for c in cases}
    # auto-pick: a filler with a slot + a wall with a fingerprint, prefer ones with edges
    picks = []
    for want in ("filler", "wall"):
        for c in cases:
            gt = c["scenario"]["ground_truth"]["target_guid"]
            if subgroup(gt, pos, wallfp) == want and gt in pool_candidates(c) and nbrs.get(gt):
                picks.append(c["scenario_id"]); break
    # allow CLI override
    if len(sys.argv) > 1:
        picks = sys.argv[1:]
    print("rendering:", picks)
    for sid in picks:
        if sid not in by:
            print("  skip (not in held-out):", sid); continue
        p = render_case(by[sid], idx, universe, nbrs, pos, wallfp)
        print("  wrote", p)


if __name__ == "__main__":
    main()
