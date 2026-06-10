"""Guard the depth-saturation finding: realizable discrimination saturates at depth-1."""
from pathlib import Path

import depth_saturation as ds

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run():
    uni = ds.load_universe(REPO_ROOT / "data" / "references" / "element_index.jsonl")
    nbrs = ds.build_edges(uni, REPO_ROOT / "data" / "ifc_models" / "AdvancedProject.ifc")
    targets = ds.load_targets(uni, REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl")
    return ds.analyze(uni, nbrs, targets, K=3)


def test_depth_saturates_at_one_hop():
    res = _run()
    assert res["n_targets"] == 60
    rea = res["realizable_median_pool_by_depth"]
    # depth-0 = attribute pool (cut-1 median 13)
    assert rea[0] == 13.0
    # depth-1 pays a real realizable cut...
    assert res["realizable_marginal_reduction"][1] >= 3.0
    # ...but depth>=2 adds essentially nothing (saturation)
    assert res["realizable_marginal_reduction"][2] < 1.0
    assert res["realizable_marginal_reduction"][3] < 1.0
    # oracle, by contrast, keeps "improving" (WL over-discriminates to ~1) — the scissors
    assert res["oracle_median_pool_by_depth"][1] <= 2
