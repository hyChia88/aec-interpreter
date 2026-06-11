"""Step C — calibrated soft-rerank + selective prediction (RQ2 mechanism)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv
from calibrate_rerank import apply_T, downstream_soft, fit_temperature, selective_curve
from field_contract import collect_pairs
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def _ctx():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    return idx, fill, cv.build_global_slot(idx, pos)


def test_apply_T_monotone_and_bounded():
    assert 0.0 < apply_T(0.5, 1.0) < 1.0
    assert apply_T(0.9, 1.0) > apply_T(0.5, 1.0) > apply_T(0.1, 1.0)   # monotone in conf
    assert abs(apply_T(0.5, 1.0) - 0.5) < 1e-6                         # T=1 identity at p=0.5


def test_fit_temperature_positive():
    idx, fill, gslot = _ctx()
    T = fit_temperature(collect_pairs(cv.make_predictor(idx), fill, gslot))
    assert T >= 0.05


def test_soft_equals_hard_finding():
    """Continuous reweighting of the (finest) slot term cannot reorder: any positive weight
    boosts a slot-match equally within the storey/class bucket → soft == hard. The calibration's
    value is in deferral (selective), not reweighting. (Documented RQ2 finding.)"""
    idx, fill, gslot = _ctx()
    pred = cv.make_predictor(idx)
    hard = downstream_soft(pred, fill, idx, gslot, weight=lambda c: 1.0)
    soft = downstream_soft(pred, fill, idx, gslot, weight=lambda c: c)
    assert abs(hard["top1"] - soft["top1"]) < 1e-6
    assert hard["top1"] > 50                          # slot evidence itself lifts floor 6.6 → ~68


def test_selective_prediction_lifts_accuracy():
    """Deferring the least-confident cases lifts Top-1 on the answered subset above the
    full-coverage number (selective prediction, L183)."""
    idx, fill, gslot = _ctx()
    T = fit_temperature(collect_pairs(cv.make_predictor(idx), fill, gslot))
    cur = selective_curve(cv.make_predictor(idx), fill, idx, gslot, T)
    full = next(p for p in cur if p["coverage"] == 1.0)["top1_answered"]
    best_partial = max(p["top1_answered"] for p in cur if p["coverage"] <= 0.85)
    assert best_partial > full + 5                    # ~80.6 vs 67.6
