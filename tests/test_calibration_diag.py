"""Step B (diagnostic) — ECE gate on raw M1b confidence. Regression: confirm anti-correlation."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv
from calibration_diag import auroc, ece
from field_contract import CalibrationPair, collect_pairs
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def _pairs():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)        # convention-consistent GT (detector + GT agree)
    return collect_pairs(cv.make_predictor(idx), fill, gslot)


def test_auroc_positive_against_consistent_gt():
    """Against the convention-consistent GT (gslot), higher conf predicts a CORRECT slot —
    AUROC well above 0.5. (Scoring against the wdir-based `pos` spuriously inverts this:
    16/35 fillers differ by the arbitrary local-X sign — see field_contract.collect_pairs.)"""
    a = auroc(_pairs())
    assert a > 0.7                       # measured 0.80


def test_ece_moderate_recalibratable():
    """Raw confidence is moderately mis-calibrated (ECE > 0) but monotone-usable → temperature
    scaling is applicable (not the L188 anti-correlation failure)."""
    stats = ece(_pairs(), n_bins=5)
    assert 0.05 < stats["ece"] < 0.35    # measured 0.206


def test_auroc_synthetic_perfect():
    """Sanity: a perfectly-discriminating confidence scores AUROC 1.0."""
    pp = [CalibrationPair(case_id=str(i), confidence=0.9, correct=True,
                          i_correct=True, M_correct=True) for i in range(5)]
    pp += [CalibrationPair(case_id="w%d" % i, confidence=0.1, correct=False,
                           i_correct=False, M_correct=False) for i in range(5)]
    assert auroc(pp) == 1.0
