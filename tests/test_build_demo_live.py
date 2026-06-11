"""Demo LIVE arm — smoke test that the M1b calibrated prediction wires into a case card."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def test_live_arm_renders_a_filler_card(tmp_path, monkeypatch):
    import build_demo as bd
    from calibrate_rerank import fit_temperature
    from field_contract import collect_pairs
    from rerank_prize import load_index, load_cases, pool_candidates, DEFAULT_INDEX, DEFAULT_TRACES
    from reconstruct_position_index import load_position_index
    from spatial_address_ceiling import DEFAULT_POS, DEFAULT_WALL
    from wall_fingerprint import load_wall_fingerprint
    from depth_saturation import load_universe

    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    universe = load_universe(DEFAULT_INDEX)
    nbrs = bd.build_light_edges(pos)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in gslot]
    T = fit_temperature(collect_pairs(pred, fill, gslot))
    live = {"pred": pred, "gslot": gslot, "T": T, "tau": bd.LIVE_TAU}

    # a filler whose GT is in the pool and addressable
    case = next(c for c in fill if c["scenario"]["ground_truth"]["target_guid"] in pool_candidates(c))
    monkeypatch.setattr(bd, "OUT", tmp_path)
    out = bd.render_case(case, idx, universe, nbrs, pos, wallfp, live)
    assert out is not None and out.exists() and out.stat().st_size > 0


def test_live_disabled_when_no_full(monkeypatch):
    """render_case still works (no LIVE block) when live=None — graceful degrade."""
    import build_demo as bd
    from rerank_prize import load_index, load_cases, pool_candidates, DEFAULT_INDEX, DEFAULT_TRACES
    from reconstruct_position_index import load_position_index
    from spatial_address_ceiling import DEFAULT_POS, DEFAULT_WALL
    from wall_fingerprint import load_wall_fingerprint
    from depth_saturation import load_universe
    import tempfile

    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    universe = load_universe(DEFAULT_INDEX)
    nbrs = bd.build_light_edges(pos)
    case = next(c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pool_candidates(c))
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(bd, "OUT", Path(d))
        out = bd.render_case(case, idx, universe, nbrs, pos, wallfp, None)
        assert out is not None and out.exists()
