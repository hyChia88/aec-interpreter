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
    """Cosine of query vs each candidate's text embedding. `cache` is keyed by candidate
    TEXT (siblings share text, so this dedupes encodes across cases)."""
    import numpy as np
    missing = list(dict.fromkeys(t for g in pool if (t := cand_text(g, idx)) not in cache))
    if missing:
        embs = model.encode(missing, normalize_embeddings=True, show_progress_bar=False)
        cache.update(zip(missing, embs))
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
    from matplotlib.patches import Patch
    names = list(rows); t1 = [rows[k]["top1"] for k in names]; t10 = [rows[k]["top10"] for k in names]
    # mark our own methods (fine-tuned extractor + structured address) vs external/zero-shot baselines
    is_ours = ["ours" in k.lower() or "address" in k.lower() for k in names]
    # baselines: steel blue/grey; ours: orange accent (matches the G8 colour in the per-field figure)
    BASE_T1, BASE_T10 = "#5b7796", "#aebfd0"
    OUR_T1, OUR_T10 = "#ef7d00", "#f6b366"
    c1 = [OUR_T1 if o else BASE_T1 for o in is_ours]
    c10 = [OUR_T10 if o else BASE_T10 for o in is_ours]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = list(range(len(names)))
    # light background band behind our own methods
    for i, o in enumerate(is_ours):
        if o:
            ax.axvspan(i - 0.5, i + 0.5, color="#fff3e6", zorder=0)
    ax.bar([i - 0.2 for i in x], t1, width=0.4, color=c1, zorder=3)
    ax.bar([i + 0.2 for i in x], t10, width=0.4, color=c10, zorder=3)
    for i, v in enumerate(t1):
        ax.text(i - 0.2, v + 1, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
    for i, v in enumerate(t10):
        ax.text(i + 0.2, v + 1, f"{v:.0f}", ha="center", fontsize=9)
    # "our methods" bracket over the shaded groups
    ours_idx = [i for i, o in enumerate(is_ours) if o]
    if ours_idx:
        ax.text(sum(ours_idx) / len(ours_idx), 102, "our methods", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color="#b35900")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9, rotation=12, ha="right")
    for i, lab in enumerate(ax.get_xticklabels()):
        if is_ours[i]:
            lab.set_fontweight("bold"); lab.set_color("#b35900")
    ax.set_ylabel("held-out accuracy (%)"); ax.set_ylim(0, 108)
    ax.set_title("External baselines, foundational/fine-tuned VLMs, and the structured spatial address\n"
                 "text retrieval, a zero-shot VLM, and zero-shot Gemini stay near chance; the address separates identical siblings", fontsize=10.5)
    ax.legend(handles=[Patch(color=BASE_T1, label="baseline Top-1"),
                       Patch(color=BASE_T10, label="baseline Top-10"),
                       Patch(color=OUR_T1, label="ours Top-1"),
                       Patch(color=OUR_T10, label="ours Top-10")],
              ncol=2, fontsize=8.5, loc="upper left")
    fig.tight_layout(); fig.savefig(out_path, dpi=130)
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
    # zero-shot VLM reranker (item #5) — base Qwen2.5-VL-7B, no adapter; pulled from its
    # own run so the figure stays in sync. Shuffled candidates → order-copying = chance.
    vlm_path = OUT / "vlm_reranker_baseline.json"
    if vlm_path.exists():
        vj = json.load(open(vlm_path)).get("scopes", {})
        for sc, lbl in (("full", "zero-shot VLM\n(full pool)"),
                        ("siblings", "zero-shot VLM\n(siblings)")):
            if sc in vj:
                a = vj[sc]["all"]
                rows[lbl] = {"top1": a["top1"], "top10": a["top10"], "mrr": a["mrr"], "n": a["n"]}
    else:
        print(f"[note] {vlm_path.name} not found — run eval/vlm_reranker_baseline.py to add the VLM rows")
    # zero-shot Gemini v2 (prompt-only extraction -> deterministic retrieval), from the frozen
    # fixture eval/fixtures/metrics/gemini_ap_v2.json (= mscd_demo results.md, Track-G): the
    # foundational-model comparator the thesis reports. Top-1 1.7 / Top-10 18.3 / MRR 0.0557.
    rows["zero-shot Gemini\n(prompt-only)"] = {"top1": 1.7, "top10": 18.3, "mrr": 0.0557, "n": 60}
    # reference points (from the ledger) for the figure
    rows["fine-tuned VLM\n(ours)"] = {"top1": 6.7, "top10": 30.0, "mrr": 0.110, "n": 60}
    # realized deployed end-to-end: VLM coarse + OpenCV slot, on the addressable filler subset (n=35).
    # NOT the same slice as the n=60 bars; its matching oracle is the filler 91.0% (see caption).
    rows["+ address\nrealized (n=35)"] = {"top1": 58.9, "top10": 67.1, "mrr": 0.0, "n": 35}
    rows["+ address\n(oracle)"] = {"top1": 78.5, "top10": 98.1, "mrr": 0.854, "n": 60}

    OUT.mkdir(exist_ok=True)
    make_figure(rows, OUT / "external_baseline.png")
    json.dump(rows, open(OUT / "external_baseline.json", "w"), indent=2)
    print(f"\n{'method':<22}{'n':>4}{'Top-1':>8}{'Top-10':>8}{'MRR':>8}")
    for k, m in rows.items():
        print(f"{k.replace(chr(10),' '):<22}{m['n']:>4}{m['top1']:>8.1f}{m['top10']:>8.1f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
