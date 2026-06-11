"""Pipeline spine figure — smoke test that the worked-example dataflow renders."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import slot_detector_cv as cv

pytestmark = pytest.mark.skipif(not cv.FULL.exists(),
                                reason="clean floorplans_full not present in this checkout")


def test_pipeline_figure_renders(tmp_path, monkeypatch):
    import build_pipeline_fig as bp
    from calibrate_rerank import fit_temperature
    from field_contract import collect_pairs
    from rerank_prize import load_index, load_cases, pool_candidates, DEFAULT_INDEX, DEFAULT_TRACES
    from reconstruct_position_index import load_position_index
    from wall_fingerprint import load_wall_fingerprint
    from spatial_address_ceiling import DEFAULT_POS, DEFAULT_WALL
    from depth_saturation import load_universe

    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    universe = load_universe(DEFAULT_INDEX)
    nbrs = bp.build_light_edges(pos)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in gslot]
    T = fit_temperature(collect_pairs(pred, fill, gslot))
    live = {"pred": pred, "gslot": gslot, "T": T, "tau": 0.40}

    case = next(c for c in fill if c["scenario"]["ground_truth"]["target_guid"] in pool_candidates(c))
    monkeypatch.setattr(bp, "OUT", tmp_path)
    out = bp.build(case, idx, universe, nbrs, pos, gslot, wallfp, live)
    assert out.exists() and out.stat().st_size > 0
