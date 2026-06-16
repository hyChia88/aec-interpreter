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
import os
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

DATASET = Path(os.getenv(
    "AEC_SYNTH_DATASET",
    "/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap"))
FULL = DATASET / "floorplans_full"

# tuning (pixels at the plans' ~1500px canvas)
NEAR_R = 320      # radius for estimating the wall axis (PCA of nearby openings)
PERP_TOL = 26     # max perpendicular distance from the axis line to count as same-wall
MATCH_MAX = 70    # max dist target-pixel -> nearest opening to accept a match

# Orientation convention (resolves the arbitrary PCA/IFC sign). Order along the wall
# axis with the sign fixed by a GLOBAL world reference, so GT and the image detector
# agree without any per-wall IFC info. Validated to preserve the oracle ceiling (91.0).
GLOBAL_REF = np.array([1.0, 0.3])


def orient_axis_world(a):
    """Sign-fix a wall axis given in WORLD xy by the global reference (⊥ -> point -Y)."""
    a = np.asarray(a, float)
    d = float(a @ GLOBAL_REF)
    if abs(d) < 1e-9:
        return a if a[1] <= 0 else -a
    return a if d > 0 else -a


def build_global_slot(idx, pos):
    """Re-label every filler's (i, M) under the global-sign convention, offline from
    element_index world centroids (no ifcopenshell). Same groups/M as position_index,
    only i is reindexed consistently -> the detector can match it from the image."""
    from collections import defaultdict
    byw = defaultdict(list)
    for g, p in pos.items():
        e = idx.get(g)
        if e and e.get("centroid"):
            # group by (wall, storey) — matches position_index; stacked fillers on a
            # multi-storey wall are NOT neighbours (else M inflates across floors).
            byw[(p["wall_guid"], e.get("storey_name"))].append((g, e["centroid"]["x"], e["centroid"]["y"]))
    out = {}
    for items in byw.values():
        P = np.array([[x, y] for _, x, y in items], float)
        axis = np.linalg.svd(P - P.mean(0))[2][0]
        axis = orient_axis_world(axis)
        order = np.argsort(P @ axis)
        M = len(items)
        for ni, k in enumerate(order):
            out[items[k][0]] = {"wall_position_index": int(ni), "wall_child_total": M}
    return out


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
    # resolve orientation: sign-fix the (pixel) axis via the global rule applied in WORLD
    # xy (affine: world+X->pixel+x, world+Y->pixel-y, so flip y to go pixel<->world).
    aw = orient_axis_world(np.array([axis[0], -axis[1]]))
    axis_ord = np.array([aw[0], -aw[1]])             # back to pixel space, sign-fixed
    proj = (cents[on_wall] - tc) @ axis_ord
    order = on_wall[np.argsort(proj)]
    seq = list(order)
    # wall-continuity truncation: collinear != same wall. Keep only the run around the
    # target where consecutive openings are joined by continuous wall poche (a corridor /
    # junction gap = open floor between them = break). Kills the over-counting.
    dark = (im.astype(int).sum(2) < 330)            # wall poche (near-black lines)
    nrm = np.array([-axis_ord[1], axis_ord[0]])

    def joined(a, b):
        seg = b - a
        L = np.linalg.norm(seg)
        if L < 1:
            return True
        hit = tot = 0
        for t in np.linspace(0.2, 0.8, max(6, int(L / 12))):
            p = a + seg * t
            tot += 1
            # any wall pixel within a perpendicular window straddling the axis line?
            found = False
            for s in range(-14, 15, 2):
                q = (p + nrm * s).astype(int)
                if 0 <= q[1] < dark.shape[0] and 0 <= q[0] < dark.shape[1] and dark[q[1], q[0]]:
                    found = True
                    break
            hit += found
        return hit / tot >= 0.6
    pis = seq.index(ti)
    C = cents
    hi = pis
    while hi + 1 < len(seq) and joined(C[seq[hi]], C[seq[hi + 1]]):
        hi += 1
    lo = pis
    while lo - 1 >= 0 and joined(C[seq[lo]], C[seq[lo - 1]]):
        lo -= 1
    seq = seq[lo:hi + 1]
    order = np.array(seq)
    i_pred = seq.index(ti)
    M_pred = len(seq)
    # orientation is arbitrary (axis sign): report both i and its mirror; caller picks min err.
    spread = float(np.ptp(proj)) if len(proj) > 1 else 0.0
    conf = min(1.0, len(seq) / max(spread / 40.0, 1.0)) if spread else 0.3
    return {"i": i_pred, "M": M_pred, "i_mirror": M_pred - 1 - i_pred, "conf": round(conf, 2),
            "match_px": float(di[ti]), "counted": cents[order], "axis": axis_ord, "tc": tc}


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
    if r is not None:  # ring the COUNTED openings + draw the wall axis
        for cc in r["counted"]:
            cv2.circle(im, tuple(cc.astype(int)), 13, (230, 0, 230), 2)
        a = r["axis"]; p0 = (r["tc"] - a * 900).astype(int); p1 = (r["tc"] + a * 900).astype(int)
        cv2.line(im, tuple(p0), tuple(p1), (230, 0, 230), 1)
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
    import slot_extractor_m1 as m1
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = build_global_slot(idx, pos)              # global-sign convention (detector + GT agree)
    pred = make_predictor(idx)
    # covered-subset detail: exact_i now ORIENTATION-RESOLVED (vs global GT, no mirror)
    cov = ei = eM = ei_agn = 0
    for c in fill:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        e = idx[gt]; cc = e["centroid"]
        r = detect((cc["x"] / 1000.0, cc["y"] / 1000.0), e["storey_name"])
        if r is None:
            continue
        cov += 1
        gi = gslot[gt]["wall_position_index"]
        ei += (r["i"] == gi); eM += (r["M"] == gslot[gt]["wall_child_total"])
        ei_agn += (r["i"] == gi) or (r["i_mirror"] == gi)
    intr = m1.intrinsic(pred, fill, gslot)
    down = m1.downstream(pred, fill, idx, gslot)
    print(f"=== M1b CV detector (orientation-resolved) — {len(fill)} fillers ===")
    print(f"covered detections: {cov}/{len(fill)}   "
          f"exact_M {eM}/{cov}   exact_i RESOLVED {ei}/{cov}   (agnostic {ei_agn}/{cov})")
    print(f"over all fillers:  exact_i={intr['exact_i']*100:.0f}%  exact_M={intr['exact_M']*100:.0f}%"
          f"  joint={intr['joint']*100:.0f}%")
    print(f"downstream:  Top-1 {down['top1']:.1f}   Top-10 {down['top10']:.1f}"
          f"   (floor 2.4 / oracle 91.0)")


if __name__ == "__main__":
    main()
