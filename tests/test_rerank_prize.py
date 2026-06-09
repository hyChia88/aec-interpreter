"""Guard the Idea-3a THIRD-cut numbers: soft-rerank prize on Top-k/MRR (offline, real pools)."""
from pathlib import Path

import rerank_prize as rp

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run():
    idx = rp.load_index(REPO_ROOT / "data" / "references" / "element_index.jsonl")
    cases = rp.load_cases(REPO_ROOT / "eval" / "fixtures" / "traces" / "g8_posctx_dim.jsonl")
    return rp.run(idx, cases)


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
