"""External retrieval baselines — regression (lexical always; dense gated on the model)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import external_baseline as eb
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES


def test_cand_text_and_tokens():
    idx = {"g1": {"ifc_class": "IfcWindow", "storey_name": "1 - First Floor",
                  "object_type": "Basic Window:Fixed", "name": "W:586778"}}
    t = eb.cand_text("g1", idx)
    assert "window" in t and "first floor" in t and "ifc" not in t
    assert "the" not in eb._tok("inspect the window")          # stopword removed


def test_lexical_ranks_token_overlap_higher():
    idx = {"a": {"ifc_class": "IfcDoor", "storey_name": "Garage", "object_type": "Steel", "name": "d1"},
           "b": {"ifc_class": "IfcWindow", "storey_name": "Second Floor", "object_type": "Fixed", "name": "w1"}}
    sc = eb.lexical_scores("a window on the second floor", {"a": {}, "b": {}}, idx)
    assert sc["b"] > sc["a"]                                   # the window/second-floor candidate wins


def test_lexical_baseline_is_weak():
    """An off-the-shelf lexical retriever cannot discriminate identical siblings → Top-1 far below
    the oracle address (78.5). This is the plan-mandated external comparator."""
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    r = eb.evaluate(lambda q, p, i: eb.lexical_scores(q, p, i), cases, idx)
    assert r["n"] >= 55
    assert r["top1"] < 15.0                                    # measured 1.7, vs oracle 78.5


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers not installed")
def test_dense_encodes():
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("all-MiniLM-L6-v2")
    v = m.encode(["a window", "a door"], normalize_embeddings=True)
    assert v.shape == (2, 384)
