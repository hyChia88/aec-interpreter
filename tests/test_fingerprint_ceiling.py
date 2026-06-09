"""Guard the Idea-3a attribute-fingerprint ceiling numbers (first cut, attribute-layer)."""
import json
from pathlib import Path

import fingerprint_ceiling as fc

REPO_ROOT = Path(__file__).resolve().parent.parent


def _universe():
    return fc.load_universe(REPO_ROOT / "data" / "references" / "element_index.jsonl")


def test_confusable_count_logic():
    uni = [
        {"global_id": "a", "storey_name": "1", "ifc_class": "IfcWall", "object_type": "X"},
        {"global_id": "b", "storey_name": "1", "ifc_class": "IfcWall", "object_type": "Y"},
        {"global_id": "c", "storey_name": "2", "ifc_class": "IfcWall", "object_type": "X"},
    ]
    a = uni[0]
    assert fc.confusable_count(uni, a, ("storey_name", "ifc_class")) == 2  # a,b
    assert fc.confusable_count(uni, a, ("storey_name", "ifc_class", "object_type")) == 1  # a


def test_attribute_ceiling_held_out_numbers():
    """Pin the first-cut headline: attributes compress coarse->optimal, but plateau."""
    uni = _universe()
    assert len(uni) == 1233
    targets = fc.load_targets(uni, REPO_ROOT / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl")
    assert len(targets) == 60
    res = fc.analyze(uni, targets)
    assert res["coarse_pool"]["median"] == 46.0
    assert res["attribute_optimal_pool"]["median"] == 13.0
    assert res["median_shrinkage_x"] >= 3.5
    # object_type is the dominant discriminator (coarse+object_type == full attr-optimal median)
    assert res["marginal_median_pool_coarse_plus"]["object_type"] == 13.0
    # attributes plateau: very few targets are uniquely identified by attributes alone
    uniq = int(res["targets_uniquely_identified_by_attributes"].split("/")[0])
    assert uniq <= 5
