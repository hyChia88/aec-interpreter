"""Fine-tuned VLM per-field re-evaluation — regression."""
import sys
from pathlib import Path
EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))
import vlm_profile as vp
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES


def test_vlm_nails_coarse_fails_discriminating():
    """The fine-tuned VLM extracts the coarse prefix at 100% but the discriminating structured
    fields at 0% (position-slot, size) — the architectural reason to delegate to specialists."""
    p = vp.profile(load_index(DEFAULT_INDEX), load_cases(DEFAULT_TRACES))
    assert p["storey_ex"] == 100.0 and p["class_ok"] == 100.0     # coarse: perfect
    assert p["slot_ex"] == 0.0 and p["size_ex"] == 0.0            # discriminating: not extracted
    assert 40 < p["dir"] < 75                                     # direction partial (~57%)
