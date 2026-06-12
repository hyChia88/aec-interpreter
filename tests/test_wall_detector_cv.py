"""M2b wall detector v0 — documents the non-recoverability finding (regression)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv
import wall_detector_cv as wd
import wall_extractor_m1 as m2
from wall_extractor_m1 import gt_fp
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def _ctx():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    return idx, m2.wall_cases(cases, pos), pos


def test_walls_are_mostly_findable():
    """The poché IS present at the wall centroid for most walls — finding the wall is not the issue."""
    idx, walls, _ = _ctx()
    pred = wd.make_predictor(idx, walls)
    cov = sum(pred(c)[0] is not None for c in walls)
    assert cov >= 14                       # ~17/22


def test_length_band_is_not_recoverable():
    """The load-bearing fields are NOT image-recoverable: collinear IfcWall instances merge in the
    poché, so length_band recovery stays poor (≤ ~50% on covered) — the documented finding."""
    idx, walls, _ = _ctx()
    pred = wd.make_predictor(idx, walls)
    cov = lb = 0
    for c in walls:
        fp, _ = pred(c)
        if fp is None:
            continue
        cov += 1
        lb += (fp["length_band"] == gt_fp(c)["length_band"])
    assert cov >= 14
    assert lb / cov < 0.55                  # measured 5/17 ≈ 0.29 — non-recoverable


def test_downstream_stays_near_floor():
    """Because the recoverable fields are weak/non-recoverable, realized wall Top-1 ≈ floor (3.4)."""
    idx, walls, pos = _ctx()
    d = m2.downstream(wd.make_predictor(idx, walls), walls, idx, pos)
    assert d["top1"] < 12.0                 # measured 3.3 ≈ floor 3.4 (vs oracle 64.2)
