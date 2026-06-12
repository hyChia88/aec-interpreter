"""External retrieval baselines — the plan-mandated comparators beyond our own ablations.

The thesis so far compares its structured spatial address only against own variants + zero-shot
Gemini. A reviewer needs an *established* method as a yardstick. Here we rank the SAME retrieved
candidate pool (GT-in-pool 100%) by two standard, off-the-shelf retrieval methods that do NOT use
the structured address:

  - dense   : sentence-transformer (all-MiniLM-L6-v2) cosine between the NL query and each
              candidate's textual description (class + storey + type + name).
  - lexical : pure-Python token-overlap (BM25-style idf-weighted) between query and candidate text.

Both are expected to land near the coarse storey+class ceiling — they can rank the right
class/floor but cannot discriminate visually-identical siblings, because the query text does not
carry the relational slot. That gap, measured against an *external* method, is the contribution.

Run:  .venv/bin/python eval/external_baseline.py
Out:  output/external_baseline.{png,json} + ledger row (printed).
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates, _rank_stats, _topk,
                          DEFAULT_INDEX, DEFAULT_TRACES)

REPO = EVAL.parent
OUT = REPO / "output"
_STOP = set("the a an on of in at to and is are please inspect where this that with for".split())


def _clean(s: str | None) -> str:
    return re.sub(r"[:_]+", " ", str(s or "")).strip()


def cand_text(guid: str, idx: dict) -> str:
    e = idx.get(guid, {})
    cls = _clean(e.get("ifc_class")).replace("Ifc", "")
    return f"{cls} on {_clean(e.get('storey_name'))}, type {_clean(e.get('object_type'))}, {_clean(e.get('name'))}".lower()


def _tok(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in _STOP and len(t) > 1]


def lexical_scores(query: str, pool: dict, idx: dict) -> dict:
    """BM25-style idf-weighted token overlap (no external dep)."""
    docs = {g: _tok(cand_text(g, idx)) for g in pool}
    N = len(docs)
    df = Counter()
    for toks in docs.values():
        df.update(set(toks))
    idf = {t: math.log(1 + N / (1 + df[t])) for t in df}
    q = _tok(query)
    scores = {}
    for g, toks in docs.items():
        tf = Counter(toks)
        scores[g] = sum(idf.get(t, 0.0) * (tf[t] / (1 + len(toks))) for t in set(q))
    return scores


def dense_scores(model, query: str, pool: dict, idx: dict, cache: dict) -> dict:
    import numpy as np
    texts, guids = [], []
    for g in pool:
        t = cand_text(g, idx)
        if t not in cache:
            texts.append(t); guids.append(t)
    if texts:
        embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        for t, v in zip(guids, embs):
            cache[t] = v
    qv = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    return {g: float(np.dot(qv, cache[cand_text(g, idx)])) for g in pool}


def evaluate(score_fn, cases, idx) -> dict:
    t1 = t10 = mrr = 0.0
    n = 0
    for c in cases:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        scores = score_fn(c["scenario"].get("query_text", ""), pool, idx)
        h, t = _rank_stats(scores, gt)
        t1 += _topk(h, t, 1); t10 += _topk(h, t, 10)
        mrr += 1.0 / (h + (t + 1) / 2)            # expected reciprocal rank under random tie-break
    return {"n": n, "top1": 100 * t1 / n, "top10": 100 * t10 / n, "mrr": mrr / n}


def make_figure(rows, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(rows); t1 = [rows[k]["top1"] for k in names]; t10 = [rows[k]["top10"] for k in names]
    colors = ["#999", "#bbb", "#7fb3d5", "#1f77b4", "#9467bd"][:len(names)]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(names))
    ax.bar([i - 0.2 for i in x], t1, width=0.4, label="Top-1", color="#1f77b4")
    ax.bar([i + 0.2 for i in x], t10, width=0.4, label="Top-10", color="#9ecae1")
    for i, v in enumerate(t1):
        ax.text(i - 0.2, v + 1, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
    for i, v in enumerate(t10):
        ax.text(i + 0.2, v + 1, f"{v:.0f}", ha="center", fontsize=9)
    ax.set_xticks(list(x)); ax.set_xticklabels(names, fontsize=9, rotation=12, ha="right")
    ax.set_ylabel("held-out accuracy (%)"); ax.set_ylim(0, 105)
    ax.set_title("External retrieval baselines vs the structured spatial address\n"
                 "off-the-shelf dense/lexical retrieval cannot discriminate identical siblings", fontsize=11)
    ax.legend(); fig.tight_layout(); fig.savefig(out_path, dpi=130)
    print("figure →", out_path)


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    cache: dict = {}

    rows = {}
    rows["lexical\n(BM25)"] = evaluate(lambda q, p, i: lexical_scores(q, p, i), cases, idx)
    rows["dense\n(MiniLM)"] = evaluate(lambda q, p, i: dense_scores(model, q, p, i, cache), cases, idx)
    # reference points (from the ledger) for the figure
    rows["our realized\n(G8)"] = {"top1": 6.7, "top10": 30.0, "mrr": 0.110, "n": 60}
    rows["+ address\n(oracle)"] = {"top1": 78.5, "top10": 98.1, "mrr": 0.854, "n": 60}

    OUT.mkdir(exist_ok=True)
    make_figure(rows, OUT / "external_baseline.png")
    json.dump(rows, open(OUT / "external_baseline.json", "w"), indent=2)
    print(f"\n{'method':<22}{'n':>4}{'Top-1':>8}{'Top-10':>8}{'MRR':>8}")
    for k, m in rows.items():
        print(f"{k.replace(chr(10),' '):<22}{m['n']:>4}{m['top1']:>8.1f}{m['top10']:>8.1f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
