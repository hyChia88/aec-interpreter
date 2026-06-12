"""M2b — wall-fingerprint CV detector (Arm-A: anchored on the target wall's known centroid).

Recovers the wall address `(connection_degree, hosted_opening_count, length_band, is_external)`
from the clean floorplan, the wall analogue of `slot_detector_cv.py`. Built incrementally:

  v0 (this cut): the fields one would expect to be recoverable —
     - length_band            : trace the wall poché along its axis to the endpoints → world length
     - hosted_opening_count   : count colour-detected openings (window/door) lying on the wall axis
     - is_external            : True (all held-out walls are external — the M2a "dead field")
     - connection_degree      : MODAL prior (junction counting needs endpoints — see finding below)

  ⚠️ **FINDING (2026-06-11) — the wall fingerprint is largely NOT image-recoverable.** v0 measured
  length_band at only 5/17 and downstream Top-1 3.3 ≈ floor. The failure is not a tuning bug: short
  `<2m` IFC junction-stub walls trace to 5-7m because **collinear adjacent IfcWall instances merge
  into one continuous poché** — the rendered floorplan does not encode IFC wall-*instance*
  boundaries. Both load-bearing fields (`length_band`, and `connection_degree` which needs the
  endpoints) therefore depend on a modelling segmentation invisible in the image. Only
  `hosted_opening_count` is recoverable (the openings render), and per M2a it is too weak alone
  (Top-1 5.5). ⇒ The wall address is oracle-discriminative (64.2) but **realization is blocked by
  non-recoverability** — the wall analogue of, and evidence for, the image-recoverability constraint
  that the filler position-slot satisfies (under the GLOBAL_REF convention) and the wall does not.
  This is why the MVP correctly scoped realization to ONE extractor (fillers). v1 junction-counting
  is NOT pursued: the endpoints it needs are themselves non-recoverable.

Reuses `slot_detector_cv` for plan loading / world↔pixel / opening detection. Scored on the M2a
harness (`wall_extractor_m1`). Run:  .venv/bin/python eval/wall_detector_cv.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import slot_detector_cv as cv
from wall_extractor_m1 import FIELDS, gt_fp, wall_cases

DARK = 330            # wall-poché threshold (sum of RGB < DARK)
WIN = 26              # window (px) for the local wall-axis PCA
PERP = 7              # perpendicular tolerance (px) for "on the wall line"
STEP_MAX = 1400       # max px to walk from the centroid along each axis direction
GAP = 9               # consecutive non-dark steps that end the wall


def length_band(mm: float) -> Optional[str]:
    if not mm:
        return None
    return "<2m" if mm < 2000 else "2-5m" if mm < 5000 else "5-10m" if mm < 10000 else ">10m"


def _px_per_m(j) -> float:
    """Pixels per world-metre from two world points through the plan's affine."""
    a = cv._world_to_px(j, 0.0, 0.0)
    b = cv._world_to_px(j, 1.0, 0.0)
    c = cv._world_to_px(j, 0.0, 1.0)
    return (np.hypot(*(b - a)) + np.hypot(*(c - a))) / 2.0


def _dark(im):
    return im.astype(int).sum(2) < DARK


def _local_axis(dark, px):
    ys, xs = np.where(dark[max(0, px[1] - WIN):px[1] + WIN, max(0, px[0] - WIN):px[0] + WIN])
    if len(xs) < 6:
        return None
    pts = np.column_stack([xs, ys]).astype(float)
    v = np.linalg.svd(pts - pts.mean(0))[2][0]
    return v / np.linalg.norm(v)


def _trace_end(dark, start, axis):
    """Walk from `start` along +axis until the poché breaks; return the last on-wall point."""
    H, W = dark.shape
    nrm = np.array([-axis[1], axis[0]])
    last = start.astype(float); gap = 0
    for t in range(1, STEP_MAX):
        p = start + axis * t
        xi, yi = int(round(p[0])), int(round(p[1]))
        if not (0 <= xi < W and 0 <= yi < H):
            break
        hit = any(0 <= int(p[1] + nrm[1] * s) < H and 0 <= int(p[0] + nrm[0] * s) < W
                  and dark[int(p[1] + nrm[1] * s), int(p[0] + nrm[0] * s)]
                  for s in range(-PERP, PERP + 1))
        if hit:
            last = p; gap = 0
        else:
            gap += 1
            if gap >= GAP:
                break
    return last


def detect_wall(centroid_world, storey_name) -> Optional[dict]:
    """-> fingerprint dict (v0 fields) or None if the wall can't be found on the plan."""
    j = cv._plan_for_storey(storey_name)
    if not j:
        return None
    im = np.asarray(Image.open(cv.FULL / Path(j["png_path"]).name).convert("RGB"))
    px = cv._world_to_px(j, centroid_world[0], centroid_world[1]).astype(int)
    dark = _dark(im)
    axis = _local_axis(dark, px)
    if axis is None:
        return None
    hi = _trace_end(dark, px.astype(float), axis)
    lo = _trace_end(dark, px.astype(float), -axis)
    length_px = float(np.hypot(*(hi - lo)))
    length_mm = length_px / _px_per_m(j) * 1000.0

    # hosted openings: colour-detected opening centroids lying on the wall line within the span
    cents, _, _ = cv._components(im)
    hoc = 0
    if len(cents):
        nrm = np.array([-axis[1], axis[0]])
        along = (cents - px) @ axis
        perp = np.abs((cents - px) @ nrm)
        lo_a, hi_a = (lo - px) @ axis, (hi - px) @ axis
        hoc = int(np.sum((perp < PERP + 4) & (along >= min(lo_a, hi_a) - 6) & (along <= max(lo_a, hi_a) + 6)))

    return {"length_band": length_band(length_mm), "hosted_opening_count": hoc,
            "is_external": True, "_length_mm": round(length_mm), "_length_px": round(length_px)}


def make_predictor(idx, walls):
    """case → (fingerprint dict, confidence). v0 fills connection_degree with the modal prior."""
    modal_cd = Counter(gt_fp(c).get("connection_degree") for c in walls).most_common(1)[0][0]

    def f(case):
        g = case["scenario"]["ground_truth"]["target_guid"]
        e = idx.get(g, {}); cc = e.get("centroid", {})
        r = detect_wall((cc.get("x", 0) / 1000.0, cc.get("y", 0) / 1000.0), e.get("storey_name", ""))
        if r is None:
            return (None, 0.0)
        fp = {"connection_degree": modal_cd, **r}
        # crude confidence: a clean trace with a definite length band
        conf = 0.6 if r["length_band"] else 0.3
        return (fp, conf)
    return f


def main():
    import wall_extractor_m1 as m2
    from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
    from reconstruct_position_index import load_position_index
    from spatial_address_ceiling import DEFAULT_POS

    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    walls = m2.wall_cases(cases, pos)
    pred = make_predictor(idx, walls)

    # per-field intrinsic accuracy (length_band, hosted_opening_count) on covered walls
    cov = lb = hoc = 0
    for c in walls:
        fp, _ = pred(c)
        if fp is None:
            continue
        cov += 1; g = gt_fp(c)
        lb += (fp["length_band"] == g["length_band"])
        hoc += (fp["hosted_opening_count"] == g["hosted_opening_count"])
    print(f"M2b v0 — covered {cov}/{len(walls)};  length_band {lb}/{cov}  hosted_opening_count {hoc}/{cov}")
    print(f"intrinsic exact-tuple / downstream:")
    print("  ", m2.intrinsic(pred, walls))
    print("  ", m2.downstream(pred, walls, idx, pos))
    print(f"  (floor 3.4 · drop-cd oracle 17.3 · oracle 64.2)")


if __name__ == "__main__":
    main()
