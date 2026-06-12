"""Triage-effort value-prop measurement — regression."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import triage_effort as te
from rerank_prize import load_index, load_cases, pool_candidates, _rank_stats, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint
from spatial_address_ceiling import score, DEFAULT_POS, DEFAULT_WALL


def test_inspections_formula():
    assert te.inspections(0, 0) == 0.5          # uniquely identified → found first try
    assert te.inspections(0, 75) == 38.0        # 76 tied (manual scan of the pool)


def test_address_cuts_triage_effort_far_below_manual():
    """Expected inspections to reach the element drops from ~manual scan to ~1 with the address;
    success@1 ties out with the oracle ceiling (≈78.5)."""
    idx = load_index(DEFAULT_INDEX); cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS); wallfp = load_wall_fingerprint(DEFAULT_WALL)
    man, addr, s1 = [], [], 0
    n = 0
    from rerank_prize import _topk
    for c in cases:
        gt = c["scenario"]["ground_truth"]["target_guid"]; pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        man.append(te.inspections(0, len(pool) - 1))
        h, t = _rank_stats(score(pool, idx, pos, wallfp, gt,
                                 {"storey": 1.0, "ifc_class": 1.0, "spatial_address": 1.0}), gt)
        addr.append(te.inspections(h, t)); s1 += _topk(h, t, 1)
    import statistics as st
    assert st.median(man) > 20                          # ~38
    assert st.median(addr) < 3                           # ~0.5
    assert st.median(man) / max(st.median(addr), 0.5) > 10   # large effort reduction
    assert 70 < 100 * s1 / n < 85                        # success@1 ≈ 78.5 (oracle ceiling)
