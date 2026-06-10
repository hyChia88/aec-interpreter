"""Guard the Idea-3a THIRD-cut numbers: soft-rerank prize on Top-k/MRR (offline, real pools)."""
from pathlib import Path

import rerank_prize as rp

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run():
    idx = rp.load_index(REPO_ROOT / "data" / "references" / "element_index.jsonl")
    cases = rp.load_cases(REPO_ROOT / "eval" / "fixtures" / "traces" / "g8_posctx_dim.jsonl")
    from reconstruct_position_index import load_position_index
    pos = load_position_index(REPO_ROOT / "data" / "references" / "position_index.jsonl")
    return rp.run(idx, cases, pos)


def test_realized_parity():
    """The realized row must reproduce the ledger G8 ranking metrics from the same traces."""
    res = _run()
    assert res["n_cases"] == 60
    assert res["pool_median"] == 76.0
    r = res["metrics"]["realized_g8"]
    assert r["top10"] == 30.0
    assert r["top1"] == 6.7
    assert abs(r["mrr"] - 0.110) <= 0.005


def test_tie_math():
    """Expected Top-k and MRR under uniform tie-breaking."""
    assert rp._topk(0, 0, 1) == 1.0          # GT alone at top
    assert rp._topk(0, 1, 1) == 0.5          # GT tied with one other for rank 1
    assert rp._topk(2, 0, 1) == 0.0          # two strictly above → not top-1
    assert rp._topk(3, 5, 10) == 1.0         # 3 above, 5 ties, all fit in top-10
    assert abs(rp._mrr(0, 0) - 1.0) < 1e-9   # rank 1
    assert abs(rp._mrr(0, 1) - (1.0 + 0.5) / 2) < 1e-9  # ranks {1,2} averaged


def test_object_type_is_the_prize():
    """Coarse fields are tapped out (oracle storey+class ≈ realized); object_type is the
    discriminator that drives the soft-rerank prize — realistic (r=0.625) ~doubles Top-10."""
    m = _run()["metrics"]
    # coarse oracle does not beat the full realized pipeline by much (coarse is saturated)
    assert abs(m["oracle_storey_class"]["top10"] - m["realized_g8"]["top10"]) <= 5
    # object_type oracle is a large jump
    assert m["oracle_plus_object_type"]["top10"] >= 70
    assert m["oracle_plus_object_type"]["top10"] - m["oracle_storey_class"]["top10"] >= 30
    # realistic discount roughly doubles realized Top-10 (no recall cost — soft rerank)
    real = m["realistic_object_type_r0.625"]["top10"]
    assert 50 <= real <= 65
    assert real >= 1.7 * m["realized_g8"]["top10"]


def test_calibration_helps_in_controlled_setting():
    """With only storey+class, zeroing wrong-extraction weights (oracle calibration) beats
    the confidence-blind rerank — the calibration prize, isolated."""
    m = _run()["metrics"]
    assert m["calibrated_storey_class"]["top10"] > m["blind_storey_class"]["top10"]


def test_position_context_is_the_top1_prize():
    """CORRECTION (vs the element_index-only cuts): position_context — the ifc_engine NEXT_TO
    slot, omitted from element_index — is the dominant Top-1 discriminator (the thesis L4
    'pool=1 for 35 cases' unlock), complementary to object_type (which lifts Top-5/10)."""
    res = _run()
    assert res["n_addressable_position"] == 35  # multi-filler-wall targets
    m = res["metrics"]
    # position dominates Top-1 (far beyond object_type and coarse)
    assert m["oracle_plus_position"]["top1"] >= 50
    assert m["oracle_plus_position"]["top1"] > m["oracle_plus_object_type"]["top1"]
    assert m["oracle_plus_position"]["top1"] - m["oracle_storey_class"]["top1"] >= 40
    # the two discriminators are complementary → both together beat either alone
    assert m["oracle_all"]["top1"] >= m["oracle_plus_position"]["top1"]
    assert m["oracle_all"]["top10"] >= m["oracle_plus_object_type"]["top10"]
