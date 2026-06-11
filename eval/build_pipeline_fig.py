"""Method spine figure — the AEC Interpreter pipeline as a horizontal dataflow diagram.

Styled after SpatialVLM (Chen et al. 2024) Fig.1 / VLM scene-graph pipelines: left-to-right
stages (a)-(e), orange module boxes, real intermediate artefacts (site photo, marked plan,
the detector's opening reading, the address sub-graph, the |C| collapse), arrows between.
Worked on ONE real held-out case (default AP_SK_102), so every tile is a true artefact.

  (a) Inputs            site photo + human-marked plan + NL query
  (b) Per-field         VLM -> storey/ifc_class · OpenCV -> position-slot (i,M) · ResNet -> size
      extraction        each field carries {value, confidence, source}
  (c) Spatial address   depth-1 sub-graph -> node.val (the structured, auditable record)
  (d) Calibrated        temperature scaling -> calibrated confidence -> selective ANSWER/DEFER
      routing
  (e) Grounding         match address against the IFC-graph pool (76 -> …) -> ranked GUID

Run:  .venv/bin/python eval/build_pipeline_fig.py [CASE_ID]
Out:  output/pipeline.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import slot_detector_cv as cv
from build_demo import (addr_str, build_light_edges, short_cls, _draw_subgraph, DATASET,
                        site_img, plan_img)
from calibrate_rerank import apply_T, fit_temperature
from field_contract import collect_pairs
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint
from spatial_address_ceiling import spatial_address, subgroup, DEFAULT_POS, DEFAULT_WALL
from depth_saturation import load_universe

REPO = EVAL.parent
OUT = REPO / "output"
ORANGE = "#f6a823"
GREEN = "#2ca02c"
RED = "#d62728"


def mbox(bg, x, y, w, h, text, fc=ORANGE, ec="none", fs=10.5, tc="black", weight="bold"):
    bg.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc=fc, ec=ec, lw=1.3, zorder=2))
    bg.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight=weight, zorder=3)


def arrow(bg, x1, y1, x2, y2, color="#444"):
    bg.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=1,
                arrowprops=dict(arrowstyle="-|>", lw=2.0, color=color,
                                shrinkA=2, shrinkB=2))


def chip(bg, x, y, w, h, text, hl=False):
    """A {value, confidence, source} output chip under an extraction module."""
    bg.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.003,rounding_size=0.008",
                                fc="#fff0d6" if hl else "#f3f3f3",
                                ec=ORANGE if hl else "#cccccc", lw=1.8 if hl else 0.8, zorder=2))
    bg.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.6,
            color="#333", zorder=3, fontfamily="monospace")


def detector_crop(ax, case, gt, idx, live):
    e = idx.get(gt, {}); cc = e.get("centroid", {})
    r = cv.detect((cc.get("x", 0) / 1000.0, cc.get("y", 0) / 1000.0), e.get("storey_name", ""))
    j = cv._plan_for_storey(e.get("storey_name", ""))
    if r is None or j is None or "counted" not in r:
        ax.axis("off"); ax.text(0.5, 0.5, "(abstain)", ha="center", va="center"); return None
    im = plt.imread(cv.FULL / Path(j["png_path"]).name)
    counted, tc = r["counted"], r["tc"]
    xs, ys = counted[:, 0], counted[:, 1]
    pad = 70; H, W = im.shape[:2]
    x0, x1 = max(0, int(xs.min() - pad)), min(W, int(xs.max() + pad))
    y0, y1 = max(0, int(ys.min() - pad)), min(H, int(ys.max() + pad))
    ax.imshow(im[y0:y1, x0:x1])
    for k, (px, py) in enumerate(counted):
        is_t = np.hypot(px - tc[0], py - tc[1]) < 6
        ax.scatter([px - x0], [py - y0], s=160 if is_t else 90, facecolors="none",
                   edgecolors=RED if is_t else ORANGE, linewidths=2.0 if is_t else 1.3, zorder=3)
        ax.text(px - x0, py - y0 - 12, str(k), ha="center", va="bottom", fontsize=7,
                fontweight="bold", color=RED if is_t else ORANGE, zorder=4)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(ORANGE); s.set_linewidth(1.5)
    return r


def collapse_axes(ax, gt, pool, idx, gslot, wallfp):
    gf = cand_feats(gt, pool[gt], idx, gslot)
    gaddr = spatial_address(gt, gslot, wallfp)
    n_full = len(pool)
    n_sc = sum(1 for g, tc in pool.items()
               if cand_feats(g, tc, idx, gslot).get("storey") == gf.get("storey")
               and cand_feats(g, tc, idx, gslot).get("ifc_class") == gf.get("ifc_class"))
    n_addr = sum(1 for g, tc in pool.items()
                 if cand_feats(g, tc, idx, gslot).get("storey") == gf.get("storey")
                 and cand_feats(g, tc, idx, gslot).get("ifc_class") == gf.get("ifc_class")
                 and spatial_address(g, gslot, wallfp) == gaddr)
    vals = [n_full, n_sc, max(n_addr, 1)]
    bars = ax.barh(range(3), vals, color=["#cccccc", "#7fb3d5", "#9467bd"])
    ax.set_yticks(range(3))
    ax.set_yticklabels(["IFC pool", "+ storey\n+ class", "+ address"], fontsize=8)
    ax.invert_yaxis()
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + max(vals) * 0.02, b.get_y() + b.get_height() / 2,
                str(v), va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(0, max(vals) * 1.25)
    ax.tick_params(labelsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return vals


def build(case, idx, universe, nbrs, pos, gslot, wallfp, live):
    gt = case["scenario"]["ground_truth"]["target_guid"]
    sid = case["scenario_id"]
    e = idx.get(gt, {})
    pool = pool_candidates(case)
    pi, pM, conf = live["pred"](case)
    cal = apply_T(conf, live["T"]) if pi is not None else 0.0
    gi, gM = gslot[gt]["wall_position_index"], gslot[gt]["wall_child_total"]
    match = pi == gi and pM == gM
    answer = cal >= live["tau"]

    fig = plt.figure(figsize=(22, 8.6))
    bg = fig.add_axes([0, 0, 1, 1]); bg.set_xlim(0, 1); bg.set_ylim(0, 1); bg.axis("off")
    fig.text(0.5, 0.965, "AEC Interpreter — neuro-symbolic spatial-address grounding pipeline",
             ha="center", fontsize=16, fontweight="bold")
    fig.text(0.5, 0.935, f"worked example: case {sid}  ({short_cls(e.get('ifc_class'))}, "
             f"{e.get('storey_name','?')})", ha="center", fontsize=10, color="#666")

    # stage band captions
    bands = [("(a) Inputs", 0.085), ("(b) Per-field extraction", 0.30),
             ("(c) Spatial address", 0.515), ("(d) Calibrated routing", 0.70),
             ("(e) Grounding → GUID", 0.90)]
    for txt, cx in bands:
        bg.text(cx, 0.045, txt, ha="center", fontsize=12.5, fontweight="bold", color="#222")
    for x in (0.185, 0.41, 0.61, 0.80):
        bg.plot([x, x], [0.08, 0.90], color="#ddd", lw=1, zorder=0)

    # ── (a) Inputs ──
    ax_site = fig.add_axes([0.02, 0.58, 0.135, 0.28]); ax_site.axis("off")
    if site_img(sid).exists():
        ax_site.imshow(plt.imread(site_img(sid)))
    ax_site.set_title("site photo", fontsize=9)
    ax_plan = fig.add_axes([0.02, 0.27, 0.135, 0.28]); ax_plan.axis("off")
    if plan_img(sid).exists():
        ax_plan.imshow(plt.imread(plan_img(sid)))
    ax_plan.set_title("human-marked plan", fontsize=9)
    q = case["scenario"].get("query_text", "")[:70]
    mbox(bg, 0.012, 0.13, 0.15, 0.10, "NL query:\n" + q, fc="#eef3f8", tc="#333", fs=8, weight="normal")

    # ── (b) Per-field extraction — module → {value, confidence, source} chip ──
    bg.text(0.30, 0.875, "each field →  {value, confidence, source}", ha="center",
            fontsize=8.5, color="#a05a00", fontstyle="italic")
    con = case.get("internals", {}).get("constraints", {}) or {}
    st = short_cls(e.get("storey_name")); cls = short_cls(e.get("ifc_class"))
    # VLM (probabilistic) → coarse prefix
    mbox(bg, 0.198, 0.745, 0.13, 0.075, "VLM  (probabilistic)\n→ storey · ifc_class", fc=ORANGE, fs=9)
    chip(bg, 0.198, 0.675, 0.13, 0.058, f"storey={st}\nclass={cls} · src=vlm")
    # OpenCV slot detector (deterministic specialist) → position-slot — the highlighted field
    mbox(bg, 0.198, 0.515, 0.13, 0.075, "OpenCV slot detector\n(deterministic specialist)\n→ position-slot (i,M)", fc=ORANGE, fs=8.6)
    chip(bg, 0.198, 0.445, 0.13, 0.058, f"value=({pi},{pM}) · conf={conf:.2f}\nsource=opencv", hl=True)
    # ResNet (deterministic) → size — post-MVP
    mbox(bg, 0.198, 0.285, 0.13, 0.075, "ResNet  (deterministic)\n→ size_band   ·  post-MVP", fc="#f3d9a6", fs=8.6, tc="#777")
    chip(bg, 0.198, 0.215, 0.13, 0.058, "value=… · conf=…\nsource=resnet  (future)")
    ax_det = fig.add_axes([0.345, 0.50, 0.052, 0.22]); detector_crop(ax_det, case, gt, idx, live)
    ax_det.set_title("detected openings", fontsize=7.5)

    # ── (c) Spatial address (depth-1 sub-graph → node.val) ──
    ax_g = fig.add_axes([0.435, 0.25, 0.175, 0.58])
    nv = f"slot {pi} of {pM}"
    _draw_subgraph(ax_g, gt, universe, nbrs, "", nv, "#9467bd", "#f1ecf9", "",
                   "depth-1 sub-graph → node.val")
    ax_g.set_title("structured address record", fontsize=9)

    # ── (d) Calibrated routing ──
    ax_cal = fig.add_axes([0.645, 0.50, 0.12, 0.30])
    ax_cal.plot([0, 1], [0, 1], "--", color="#bbb", lw=1)
    ax_cal.scatter([conf], [cal], s=80, color=ORANGE, zorder=3)
    ax_cal.annotate(f"raw {conf:.2f}\n→cal {cal:.2f}", (conf, cal), fontsize=8,
                    textcoords="offset points", xytext=(6, -14))
    ax_cal.set_xlim(0, 1); ax_cal.set_ylim(0, 1)
    ax_cal.set_xlabel("raw conf", fontsize=8); ax_cal.set_ylabel("calibrated", fontsize=8)
    ax_cal.tick_params(labelsize=7)
    ax_cal.set_title(f"temperature scaling (T={live['T']:.2f})", fontsize=8.5)
    badge = ("ANSWER", GREEN) if answer else ("DEFER → return candidates", RED)
    mbox(bg, 0.638, 0.30, 0.135, 0.09, f"selective routing\nτ = {live['tau']:.2f}", fc="#eef3f8",
         tc="#333", fs=9, weight="normal")
    mbox(bg, 0.638, 0.165, 0.135, 0.075, badge[0], fc=badge[1], tc="white", fs=10)

    # ── (e) Grounding → GUID ──
    ax_col = fig.add_axes([0.825, 0.50, 0.155, 0.30])
    vals = collapse_axes(ax_col, gt, pool, idx, gslot, wallfp)
    ax_col.set_title("IFC-graph pool collapse", fontsize=8.5)
    mark = "✓ correct" if match else "✗ (GT differs)"
    gtxt = f"predicted GUID\n…{gt[-10:]}\n{mark}"
    mbox(bg, 0.83, 0.20, 0.15, 0.10, gtxt, fc="#e8f6ec" if match else "#fcebec",
         ec=GREEN if match else RED, tc=GREEN if match else RED, fs=9)

    # structural (gray) arrows between stages
    arrow(bg, 0.165, 0.55, 0.198, 0.55)               # inputs → extraction
    arrow(bg, 0.40, 0.55, 0.435, 0.55)                # extraction → address
    arrow(bg, 0.612, 0.55, 0.645, 0.62)               # address → routing
    arrow(bg, 0.768, 0.62, 0.825, 0.62)               # routing → grounding

    # ── confidence-routing highlight (the RQ2 mechanism: per-field confidence binds the
    #    ANSWER/DEFER decision) — a distinct orange lane from the OpenCV conf chip to the gate.
    lane = 0.10
    HL = "#ef7d00"
    # route just RIGHT of the (b) column so it never crosses the ResNet box below
    bg.plot([0.328, 0.405], [0.474, 0.474], color=HL, lw=3.2, alpha=0.55, zorder=1,
            solid_capstyle="round")                                       # out of the conf chip
    bg.plot([0.405, 0.405], [0.474, lane], color=HL, lw=3.2, alpha=0.55, zorder=1,
            solid_capstyle="round")                                       # down the gutter
    bg.plot([0.405, 0.705], [lane, lane], color=HL, lw=3.2, alpha=0.55, zorder=1,
            solid_capstyle="round")                                       # along the bottom lane
    bg.annotate("", xy=(0.705, 0.162), xytext=(0.705, lane), zorder=1,
                arrowprops=dict(arrowstyle="-|>", lw=3.2, color=HL, alpha=0.7))  # up into the gate
    bg.text(0.515, lane - 0.028,
            "confidence-routing path:  per-field {confidence} binds the ANSWER / DEFER decision   "
            "(determinism ↔ adaptivity — the RQ2 mechanism)",
            ha="center", fontsize=8.8, color="#b35e00", fontstyle="italic", zorder=4)
    bg.scatter([0.328], [0.474], s=28, color=HL, zorder=4)               # tap point on the conf chip

    OUT.mkdir(exist_ok=True)
    p = OUT / "pipeline.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    universe = load_universe(DEFAULT_INDEX)
    nbrs = build_light_edges(pos)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fillers = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in gslot]
    T = fit_temperature(collect_pairs(pred, fillers, gslot))
    live = {"pred": pred, "gslot": gslot, "T": T, "tau": 0.40}

    sid = sys.argv[1] if len(sys.argv) > 1 else "AP_SK_102"
    by = {c["scenario_id"]: c for c in cases}
    case = by[sid]
    p = build(case, idx, universe, nbrs, pos, gslot, wallfp, live)
    print("wrote", p)


if __name__ == "__main__":
    main()
