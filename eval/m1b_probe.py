"""M1b probe — what is actually detectable for an image-based slot detector?

Empirical characterization done *before* building the detector (the hard part of a CV
build is knowing the signal). Three findings, all reproducible here:

  1. MARKED PATCH OCCLUDES OPENINGS. `floorplans/<id>_floorplan.png` paints the target
     wall a SOLID red and the anchor wall solid orange — the individual window/door
     openings are covered. So the slot (i, M) cannot be read from the marked patch; it
     gives host-wall identity + target location only.
  2. CLEAN PLAN COLOR-CODES OPENINGS. `floorplans_full/` renders windows in BLUE and
     doors in GREEN as discrete segments → openings are directly color-segmentable (no
     fragile gap-detection). The detector is feasible here.
  3. COVERAGE = 3/7 STOREYS (17/35 fillers). Only First Floor / Garage / Level 1 have a
     clean plan — a *deliberate* 3-storey scope cut in the dataset renderer
     (`data_curation/scripts/synth/3c_render_full_storeys.py`, "Phase 6 T1 scope"),
     deferred as F2 future work, NOT a fundamental limit. Regenerating the other 4
     storeys unlocks all 35 fillers for the deterministic detector + the demo's honest arm.

⇒ M1b reshape: build a COLOR-based opening detector (blue=window/green=door) on the
clean plan, group collinear openings per host wall, order along the wall axis → (i, M).
Score on `slot_extractor_m1`'s harness. Coverage decision (regenerate plans vs build on
the 17-subset vs pivot to the learned/site-photo arm) is in STATUS / the ledger.
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
sys.path.insert(0, str(EVAL))
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

DATASET = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap")


def _rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def window_mask(im):  # blue segments
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    return ((B > 150) & (R < 120) & (G < 180) & (B - R > 60)).astype(np.uint8)


def door_mask(im):    # green segments
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    return ((G > 120) & (R < 120) & (B < 120) & (G - R > 50) & (G - B > 50)).astype(np.uint8)


def n_components(mask, min_area=25):
    n, _, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    return sum(1 for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > min_area)


def finding_1_marked_occlusion(sid="AP_SK_107"):
    im = _rgb(DATASET / "floorplans" / f"{sid}_floorplan.png")
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    red = ((R > 200) & (G < 60) & (B < 60)).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(red, 8)
    big = max((st[k, cv2.CC_STAT_AREA] for k in range(1, n)), default=0)
    print(f"[1] marked patch {sid}: largest red(target) component = {big} px (solid wall);")
    print(f"    window-glyphs visible inside marked patch: {n_components(window_mask(im))}"
          f"  door-glyphs: {n_components(door_mask(im))}  → openings OCCLUDED by the fill")


def finding_2_clean_colorcoded():
    print("[2] clean full plans — openings are color-coded (window=blue, door=green):")
    for png in sorted(glob.glob(str(DATASET / "floorplans_full" / "*.png"))):
        im = _rgb(Path(png))
        print(f"    {Path(png).name:32} windows={n_components(window_mask(im)):3d}  "
              f"doors={n_components(door_mask(im)):3d}")


def finding_3_coverage():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    have = set()
    for jf in glob.glob(str(DATASET / "floorplans_full" / "*.json")):
        s = json.load(open(jf)).get("storey_name")
        if s:
            have.add(s)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    covered = sum(1 for c in fill
                  if idx[c["scenario"]["ground_truth"]["target_guid"]]["storey_name"] in have)
    print(f"[3] clean-plan storeys: {sorted(have)}")
    print(f"    held-out fillers covered by a clean plan: {covered}/{len(fill)}"
          f"  ({len(fill) - covered} on un-rendered storeys)")


def main():
    print("=== M1b probe — detectability for the image slot detector ===")
    finding_1_marked_occlusion()
    finding_2_clean_colorcoded()
    finding_3_coverage()


if __name__ == "__main__":
    main()
