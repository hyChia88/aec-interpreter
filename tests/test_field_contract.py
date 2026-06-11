"""Step A — per-field contract bridge (class-agnostic substrate for P1 calibration)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv
from field_contract import CalibrationPair, collect_pairs, field_to_key, slot_field
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def _ctx():
    return (load_index(DEFAULT_INDEX), load_cases(DEFAULT_TRACES), load_position_index(DEFAULT_POS))


def test_slot_field_shape_and_key():
    fv = slot_field(2, 3, 0.7)
    assert fv.value == {"i": 2, "M": 3, "i_mirror": None}
    assert fv.confidence == 0.7 and fv.source == "opencv" and fv.role == "unset"
    assert field_to_key(fv) == (2, 3)


def test_abstain_is_absent():
    fv = slot_field(None, None, 0.0)
    assert not fv.present and field_to_key(fv) is None


def test_confidence_clamped():
    assert slot_field(1, 2, 1.5).confidence == 1.0
    assert slot_field(1, 2, -0.2).confidence == 0.0


def test_collect_pairs_covers_all_fillers():
    """The detector abstains on none of the 35 fillers (full coverage post-F2); scored against
    the convention-consistent GT (gslot), joint-correct is ~26/35 (74%)."""
    idx, cases, pos = _ctx()
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    pairs = collect_pairs(cv.make_predictor(idx), fill, gslot)
    assert all(isinstance(p, CalibrationPair) for p in pairs)
    assert len(pairs) >= 30                              # ~35, no abstentions
    assert sum(p.correct for p in pairs) >= 20           # ~26/35 joint-correct (gslot)


def test_collect_pairs_correct_matches_downstream_event():
    """`correct` is the exact-joint (i,M) match vs the convention-consistent GT — the same
    event the M1a matcher rewards, so calibrating this confidence calibrates the rerank signal.
    Must use gslot, NOT the wdir-based pos (arbitrary local-X sign differs on ~16/35)."""
    idx, cases, pos = _ctx()
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    pairs = {p.case_id: p for p in collect_pairs(pred, fill, gslot)}
    for c in fill:
        pi, pM, _ = pred(c)
        if pi is None:
            continue
        g = c["scenario"]["ground_truth"]["target_guid"]
        gi, gM = gslot[g]["wall_position_index"], gslot[g]["wall_child_total"]
        assert pairs[c["scenario_id"]].correct == (pi == gi and pM == gM)
