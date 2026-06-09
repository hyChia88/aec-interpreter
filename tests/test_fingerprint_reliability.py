"""Guard the Idea-3a SECOND-cut numbers: topology saturation + reliability bind + 3b gate."""
from pathlib import Path

import fingerprint_reliability as fr

REPO_ROOT = Path(__file__).resolve().parent.parent


def _universe():
    uni = fr.load_universe(REPO_ROOT / "data" / "references" / "element_index.jsonl")
    fr.add_topology_features(uni)
    return uni


def test_universe_dedup_and_topology_built():
    uni = _universe()
    assert len(uni) == 852  # deduped by GUID (raw index = 1233 with Wall double-counts)
    # topology fields are attached; adjacency is sparse (most elements have no neighbour)
    with_adj = sum(1 for e in uni if e.get("adjacency_sig"))
    assert 0 < with_adj < len(uni) // 2  # sparse, but present


def test_topology_saturation_and_3b_gate():
    """Topology adds almost nothing over attributes → Idea-3b (learned selector) = SKIP."""
    uni = _universe()
    targets = fr.load_targets(uni, REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl")
    assert len(targets) == 60
    res = fr.analyze(uni, targets)
    assert res["coarse_pool_median"] == 46.0
    assert res["attribute_optimal_median"] == 13.0
    assert res["full_oracle_median"] == 12.0
    # topology buys <=2 elements of extra shrinkage → feature space saturated
    assert res["topology_feature_prize"] <= 2
    assert res["idea_3b_gate"]["decision"] == "SKIP"


def test_reliability_bind():
    """No hard filter sustains the recall floor; calibrated object_type is the one lever."""
    uni = _universe()
    targets = fr.load_targets(uni, REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl")
    res = fr.analyze(uni, targets)
    # ∏r collapses well below the floor even at the coarse pair
    assert res["recall_floor_reachable_by_hard_filter"] is False
    assert res["full_oracle_recall_if_hard"] < 0.05
    # object_type is the only single feature whose calibrated routing beats the coarse pool
    calib = res["calibrated_single_feature_pool"]
    assert res["best_calibrated_feature"] == "object_type"
    assert calib["object_type"] < res["coarse_pool_median"]
    assert all(calib[f] == res["coarse_pool_median"] for f in calib if f != "object_type")
