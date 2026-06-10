"""M1a position-slot harness — regression tests (offline, frozen traces)."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS
import slot_extractor_m1 as m1


def _run():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    return m1.run(idx, cases, pos), idx, cases, pos


def test_filler_count_is_thesis_35():
    r, *_ = _run()
    assert r["n_fillers"] == 35          # = thesis "pool=1 for 35 cases"


def test_oracle_full_is_perfect_intrinsic_and_ceiling():
    r, *_ = _run()
    o = r["rows"]["oracle full (i,M) — CEILING"]
    assert o["joint"] == 1.0 and o["exact_i"] == 1.0 and o["exact_M"] == 1.0
    assert o["top1"] > 88.0               # canonical oracle filler Top-1 = 91.0


def test_g8_and_text_recover_no_slot():
    """The measured reality: G8 extracts position_context 0/35; the query has no slot cue."""
    r, *_ = _run()
    for name in ("G8 realized position_context", "text-parse (honest query)"):
        assert r["rows"][name]["coverage"] == 0.0
        assert r["rows"][name]["top1"] < 5.0   # ≈ realized floor 2.4


def test_i_is_the_bigger_lever_than_M():
    """Knowing the ordering i lifts Top-1 more than knowing the count M → tells M1b where to aim."""
    r, *_ = _run()
    assert r["rows"]["oracle i, prior M"]["top1"] > r["rows"]["oracle M (host known), prior i"]["top1"]


def test_abstain_matches_realized_floor():
    r, *_ = _run()
    # text-parse abstains on every case → downstream == G8 realized ranking (~2.4)
    assert abs(r["rows"]["text-parse (honest query)"]["top1"]
               - r["rows"]["G8 realized position_context"]["top1"]) < 1e-6
