"""M1b color-based slot detector — regression tests (offline; needs the dataset clean plans)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv
import slot_extractor_m1 as m1
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def _ctx():
    return (load_index(DEFAULT_INDEX), load_cases(DEFAULT_TRACES), load_position_index(DEFAULT_POS))


def test_detects_clean_small_wall():
    """AP_SK_234: a clean 3-window wall, target at the end -> M=3, i (or mirror)=2."""
    idx, cases, pos = _ctx()
    e = idx[next(c for c in cases if c["scenario_id"] == "AP_SK_234")["scenario"]["ground_truth"]["target_guid"]]
    r = cv.detect((e["centroid"]["x"] / 1000.0, e["centroid"]["y"] / 1000.0), e["storey_name"])
    assert r is not None and r["M"] == 3
    assert 2 in (r["i"], r["i_mirror"])


def test_covers_only_clean_storeys():
    """Predictor detects on the 3 clean storeys, abstains elsewhere -> partial coverage."""
    idx, cases, pos = _ctx()
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    pred = cv.make_predictor(idx)
    cov = sum(pred(c)[0] is not None for c in fill)
    assert 0 < cov < len(fill)               # some covered, some abstain (17/35 today)


def test_orientation_resolution_lifts_downstream():
    """With orientation resolved (global-sign convention), the detected slot lifts filler
    Top-1 well above the realized floor (2.4) — measured ~9."""
    idx, cases, pos = _ctx()
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    down = m1.downstream(cv.make_predictor(idx), fill, idx, gslot)
    assert down["top1"] > 6.0


def test_global_relabel_preserves_oracle_ceiling():
    """The orientation convention is discrimination-neutral: oracle filler Top-1 stays 91."""
    idx, cases, pos = _ctx()
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    oracle = m1.oracle_full(gslot)
    assert m1.downstream(oracle, fill, idx, gslot)["top1"] > 88.0
