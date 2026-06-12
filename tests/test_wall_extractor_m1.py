"""M2a wall-fingerprint harness — baselines + per-field oracle ablation (regression)."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import wall_extractor_m1 as m2
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS


def _ctx():
    return (load_index(DEFAULT_INDEX), load_cases(DEFAULT_TRACES), load_position_index(DEFAULT_POS))


def test_22_wall_targets():
    idx, cases, pos = _ctx()
    assert len(m2.wall_cases(cases, pos)) == 22


def test_oracle_reproduces_ceiling():
    """oracle-full wall Top-1 reproduces the spatial-address ceiling (64.2)."""
    idx, cases, pos = _ctx()
    walls = m2.wall_cases(cases, pos)
    d = m2.downstream(m2.oracle_full, walls, idx, pos)
    assert 60.0 < d["top1"] < 68.0


def test_connection_degree_is_the_lever():
    """Among single-field oracles, connection_degree gives the largest Top-1 lift; and dropping
    it costs the most — the diagnostic that makes junction-counting the make-or-break CV task."""
    idx, cases, pos = _ctx()
    walls = m2.wall_cases(cases, pos)
    only = {f: m2.downstream(m2.make_oracle_field(walls, f), walls, idx, pos)["top1"] for f in m2.FIELDS}
    assert only["connection_degree"] == max(only.values())
    drop_cd = m2.downstream(m2.make_oracle_drop(walls, "connection_degree"), walls, idx, pos)["top1"]
    full = m2.downstream(m2.oracle_full, walls, idx, pos)["top1"]
    assert (full - drop_cd) > 30          # 64.2 → 17.3


def test_is_external_is_dead():
    """All held-out walls are external → recovering is_external adds nothing over the floor."""
    idx, cases, pos = _ctx()
    walls = m2.wall_cases(cases, pos)
    floor = m2.downstream(m2.make_prior(walls), walls, idx, pos)["top1"]
    ext_only = m2.downstream(m2.make_oracle_field(walls, "is_external"), walls, idx, pos)["top1"]
    assert abs(ext_only - floor) < 1e-6
