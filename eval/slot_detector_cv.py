"""M1b — deterministic color-based position-slot detector on the clean storey plan.

Honest image extractor (no IFC answer). Pipeline per filler whose storey has a clean plan
(`floorplans_full/`, 17/35 — see `m1b_probe.py`):
  1. project the target's world centroid -> plan pixel (plan world_bbox affine).
  2. color-detect opening segments: window = blue, door = green (the plan's own coding).
  3. target opening = nearest opening to the projected pixel.
  4. host-wall axis = principal direction (PCA) of openings near the target.
  5. keep openings within a perpendicular band of the axis line through the target (= same
     wall), order by projection along the axis -> M = count, i = target's rank.
Outputs (i, M, confidence) for `slot_extractor_m1`. The 18 un-covered fillers (Floors 2-5,
no storey-contained walls) are out until the F2 multi-storey re-render (see STATUS).

`--viz <case_id>` saves an overlay to output/_probe for visual validation.
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

EVAL = Path(__file__).resolve().parent
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

DATASET = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap")
FULL = DATASET / "floorplans_full"

# tuning (pixels at the plans' ~1500px canvas)
NEAR_R = 320      # radius for estimating the wall axis (PCA of nearby openings)
PERP_TOL = 26     # max perpendicular distance from the axis line to count as same-wall
MATCH_MAX = 70    # max dist target-pixel -> nearest opening to accept a match


def _plan_for_storey(storey_name: str):
    for jf in glob.glob(str(FULL / "*.json")):
        j = json.load(open(jf))
        if j.get("storey_name") == storey_name:
            return j
    return None


def _world_to_px(j, wx, wy):
    bb = j["world_bbox"]; W = j["pixel_size"]["width"]; H = j["pixel_size"]["height"]
    px = (wx - bb["xmin"]) / (bb["xmax"] - bb["xmin"]) * W
    py = (bb["ymax"] - wy) / (bb["ymax"] - bb["ymin"]) * H
    return np.array([px, py])


def _opening_mask(im):
    R, G, B = im[..., 0].astype(int), im[..., 1].astype(int), im[..., 2].astype(int)
    win = (B > 150) & (R < 120) & (G < 180) & (B - R > 60)
    door = (G > 120) & (R < 120) & (B < 120) & (G - R > 50) & (G - B > 50)
    return (win | door).astype(np.uint8)


def _components(im):
    """(cents[N,2], labels, label_img) for window+door opening segments."""
    m = _opening_mask(im)
    n, lab, st, cent = cv2.connectedComponentsWithStats(m, 8)
    keep = [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > 25]
    cents = np.array([cent[k] for k in keep]) if keep else np.empty((0, 2))
    return cents, keep, lab


def _openings(im):
    cents, _, _ = _components(im)
    return [(c, None) for c in cents]


def _axis_from_pixels(lab, label_id):
    """Wall direction = principal axis of the target opening's own (elongated) pixels."""
    ys, xs = np.where(lab == label_id)
    pts = np.column_stack([xs, ys]).astype(float)
    if len(pts) < 4:
        return None
    _, _, vt = np.linalg.svd(pts - pts.mean(0))
    return vt[0] / np.linalg.norm(vt[0])


def detect(target_world, storey_name):
    """-> dict(i, M, conf, ...) or None if no plan / no match."""
    j = _plan_for_storey(storey_name)
    if not j:
        return None
    png = FULL / Path(j["png_path"]).name
    im = np.asarray(Image.open(png).convert("RGB"))
    tpx = _world_to_px(j, target_world[0], target_world[1])
    cents, keep, lab = _components(im)
    if len(cents) == 0:
        return None
    di = np.linalg.norm(cents - tpx, axis=1)
    ti = int(np.argmin(di))
    if di[ti] > MATCH_MAX:
        return None                                   # target not on a detected opening
    tc = cents[ti]
    # wall axis from the TARGET opening's own elongation (junction-robust); fall back to NN dir
    axis = _axis_from_pixels(lab, keep[ti])
    if axis is None:
        d = cents - tc; d = d[np.linalg.norm(d, axis=1) < NEAR_R]
        axis = (np.linalg.svd(d - d.mean(0))[2][0] if len(d) > 1 else np.array([1.0, 0.0]))
        axis = axis / np.linalg.norm(axis)
    # collect same-wall openings (near the axis line through target), refit axis to them once
    for _ in range(2):
        normal = np.array([-axis[1], axis[0]])
        perp = np.abs((cents - tc) @ normal)
        on_wall = np.where(perp < PERP_TOL)[0]
        if len(on_wall) > 2:
            pts = cents[on_wall]
            v = np.linalg.svd(pts - pts.mean(0))[2][0]
            axis = v / np.linalg.norm(v)
    proj = (cents[on_wall] - tc) @ axis
    order = on_wall[np.argsort(proj)]
    seq = list(order)
    i_pred = seq.index(ti)
    M_pred = len(seq)
    # orientation is arbitrary (axis sign): report both i and its mirror; caller picks min err.
    spread = float(np.ptp(proj)) if len(proj) > 1 else 0.0
    conf = min(1.0, len(seq) / max(spread / 40.0, 1.0)) if spread else 0.3
    return {"i": i_pred, "M": M_pred, "i_mirror": M_pred - 1 - i_pred, "conf": round(conf, 2),
            "match_px": float(di[ti])}


# ── predictor for the M1a harness ────────────────────────────────────────────
def make_predictor(idx):
    def f(case):
        gt = case["scenario"]["ground_truth"]["target_guid"]
        e = idx.get(gt, {})
        c = e.get("centroid")
        if not c:
            return (None, None, 0.0)
        r = detect((c["x"] / 1000.0, c["y"] / 1000.0), e.get("storey_name"))
        if r is None:
            return (None, None, 0.0)
        return (r["i"], r["M"], r["conf"])
    return f


def viz(case_id, idx, cases, pos):
    case = next(c for c in cases if c["scenario_id"] == case_id)
    gt = case["scenario"]["ground_truth"]["target_guid"]
    e = idx[gt]; c = e["centroid"]
    storey = e["storey_name"]
    j = _plan_for_storey(storey)
    if not j:
        print(f"{case_id}: no clean plan for storey {storey}"); return
    png = FULL / Path(j["png_path"]).name
    im = np.asarray(Image.open(png).convert("RGB")).copy()
    tpx = _world_to_px(j, c["x"] / 1000.0, c["y"] / 1000.0)
    ops = _openings(im)
    cents = np.array([cc for cc, _ in ops])
    r = detect((c["x"] / 1000.0, c["y"] / 1000.0), storey)
    g = pos[gt]
    for cc, kind in ops:
        cv2.circle(im, tuple(cc.astype(int)), 6, (0, 120, 255) if kind == "window" else (0, 200, 0), -1)
    cv2.drawMarker(im, tuple(tpx.astype(int)), (255, 0, 0), cv2.MARKER_CROSS, 50, 4)
    txt = f"GT i{g['wall_position_index']}/M{g['wall_child_total']}  pred " + (
        f"i{r['i']}(or {r['i_mirror']})/M{r['M']} conf{r['conf']}" if r else "NONE")
    cv2.putText(im, txt, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (200, 0, 0), 3)
    # crop around target
    x, y = tpx.astype(int); R = 360
    crop = im[max(0, y - R):y + R, max(0, x - R):x + R]
    out = REPO / "output" / "_probe" / f"{case_id}_detect.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(crop).save(out)
    print(f"{case_id}: {txt}  -> {out}")


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    if len(sys.argv) > 2 and sys.argv[1] == "--viz":
        for cid in sys.argv[2:]:
            viz(cid, idx, cases, pos)
        return
    # intrinsic check over covered fillers (exact with orientation-agnostic i)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    pred = make_predictor(idx)
    cov = ei = eM = 0
    n = 0
    for c in fill:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        g = pos[gt]
        e = idx[gt]
        cc = e["centroid"]
        r = detect((cc["x"] / 1000.0, cc["y"] / 1000.0), e["storey_name"])
        if r is None:
            continue
        n += 1
        ok_i = (r["i"] == g["wall_position_index"]) or (r["i_mirror"] == g["wall_position_index"])
        ei += ok_i; eM += (r["M"] == g["wall_child_total"])
    print(f"=== M1b CV detector — covered fillers with a detection: {n}/{len(fill)} ===")
    print(f"exact_M = {eM}/{n}   exact_i (orientation-agnostic) = {ei}/{n}")


if __name__ == "__main__":
    main()
