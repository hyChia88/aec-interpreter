#!/usr/bin/env python3
"""
Idea 3a — THIRD CUT: the SOFT-RERANK prize on Top-k / MRR (offline, from traces).

The first two cuts measured the confusable-set size |C(e)| — a *recall/discrimination*
proxy. But the live system's binding metric is not pool size: GT-in-pool is already 100%,
yet Top-1 is 6.7% and Top-10 30%. The bottleneck is RANKING inside the pool. Hard filtering
can't help (it evicts GT → recall loss; see `fingerprint_reliability.py`); SOFT
confidence-weighted rerank can, because it keeps GT in the pool and only reorders.

This cut sizes that prize directly on Top-k / MRR, fully offline:
  - Real candidate pools come from the frozen G8 traces (median 76, GT-in-pool 60/60).
  - Each pool guid is joined to `element_index.jsonl` for its full feature vector.
  - We rerank by feature agreement and report expected Top-1/5/10 + MRR (analytic tie
    handling: GT shares a tied score with its confusable set → expected reciprocal rank
    over the tie group).

Rows (all from REAL data + oracle; no simulation of wrong-value distributions):
  realized            G8's actual ranking (parity check vs ledger: Top-10 30%, MRR 0.110).
  blind soft-rerank   rerank by the model's ACTUAL extracted storey+class (from the trace),
                      every extracted field weighted equally — even when extraction is wrong.
  calibrated          same, but a field's weight is zeroed when the model's extraction was
                      actually wrong (oracle calibration = perfect knowledge of correctness).
                      → calibrated − blind = the CALIBRATION PRIZE P1 chases.
  oracle storey+class perfect extraction of the coarse fields (extraction ceiling, coarse).
  oracle +object_type adds the cut-2 dominant discriminator under perfect extraction → what a
                      future object_type specialist + P1 would unlock on Top-k.

Real data only: the model genuinely extracts storey+ifc_class (G8); object_type is the
oracle/hypothetical row (the pipeline does not extract it yet — that's a P2 specialist).
No GPU, no Neo4j.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "data" / "references" / "element_index.jsonl"
DEFAULT_TRACES = REPO_ROOT / "eval" / "fixtures" / "traces" / "g8_posctx_dim.jsonl"


def _storey_key(v: Any) -> Optional[str]:
    """Normalise storey to its leading integer ('1' and '1 - First Floor' → '1')."""
    if v in (None, ""):
        return None
    m = re.match(r"\s*(\d+)", str(v))
    return m.group(1) if m else str(v).strip()


def load_index(path: Path) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for l in path.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            idx[r["global_id"]] = r
    return idx


def load_cases(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ── candidate feature accessors (mix trace-taxonomy + element_index) ──

def cand_feats(guid: str, trace_cand: dict, idx: dict, pos: dict | None = None) -> dict:
    """Feature vector for a pool candidate. storey/ifc_class use the trace's own taxonomy
    (ref_storey/ref_type — consistent with the extractor's vocabulary); object_type comes
    from element_index; position_slot comes from the offline-reconstructed NEXT_TO table
    (ifc_engine enrichment that is NOT in element_index — see reconstruct_position_index.py).
    """
    e = idx.get(guid, {})
    p = (pos or {}).get(guid)
    return {
        "storey": _storey_key(trace_cand.get("ref_storey") or e.get("storey_name")),
        "ifc_class": trace_cand.get("ref_type") or trace_cand.get("type") or e.get("ifc_class"),
        "object_type": e.get("object_type"),
        # position_context = "Nth filler of M on the host wall" (the thesis L4 unlock):
        "position_slot": (p["wall_position_index"], p["wall_child_total"]) if p else None,
    }


def pool_candidates(case: dict) -> dict[str, dict]:
    """guid → shallow trace candidate dict over the full retrieved pool (dedup by guid)."""
    out: dict[str, dict] = {}
    for r in case["internals"].get("retrieval_results") or []:
        for c in r.get("candidates") or []:
            out.setdefault(c["guid"], c)
    return out


# ── expected Top-k / MRR with analytic tie handling ──

def _rank_stats(scores: dict[str, float], gt: str) -> tuple[int, int]:
    """Return (h, t): h = #candidates strictly above GT, t = #tied with GT (excl GT)."""
    g = scores[gt]
    h = sum(1 for k, s in scores.items() if s > g)
    t = sum(1 for k, s in scores.items() if s == g and k != gt)
    return h, t


def _topk(h: int, t: int, k: int) -> float:
    """P(GT lands in top-k) under uniform random tie-breaking."""
    if h >= k:
        return 0.0
    return min(1.0, (k - h) / (t + 1))


def _mrr(h: int, t: int) -> float:
    """E[1/rank] over the tie group [h+1 .. h+t+1]."""
    return sum(1.0 / i for i in range(h + 1, h + t + 2)) / (t + 1)


def score_pool(pool: dict[str, dict], idx: dict, gt: str,
               weights: dict[str, float], pos: dict | None = None) -> dict[str, float]:
    """score(c) = Σ_f w_f · [feature_f(c) == feature_f(GT)]. Weights select which fields
    (and how strongly) participate; the 'target value' is GT's own feature value (oracle
    extraction). For realistic rows the caller zeroes/sets weights per the scheme."""
    gf = cand_feats(gt, pool[gt], idx, pos)
    out: dict[str, float] = {}
    for guid, tc in pool.items():
        cf = cand_feats(guid, tc, idx, pos)
        out[guid] = sum(w * (cf.get(f) is not None and cf.get(f) == gf.get(f))
                        for f, w in weights.items())
    return out


def realized_rank(case: dict, gt: str) -> tuple[int, int]:
    """GT's rank in G8's actual top-10 shortlist (h = rank-1, t = 0; absent → h huge)."""
    cands = case["interpreter_output"].get("candidates") or []
    order = [c["guid"] for c in cands]
    if gt in order:
        return order.index(gt), 0
    return 10_000, 0  # not in shortlist → contributes 0 to Top-10 and ~0 MRR


def aggregate(rows: list[tuple[int, int]]) -> dict:
    n = len(rows)
    return {
        "top1": round(100 * sum(_topk(h, t, 1) for h, t in rows) / n, 1),
        "top5": round(100 * sum(_topk(h, t, 5) for h, t in rows) / n, 1),
        "top10": round(100 * sum(_topk(h, t, 10) for h, t in rows) / n, 1),
        "mrr": round(sum(_mrr(h, t) for h, t in rows) / n, 3),
    }


def run(idx: dict, cases: list[dict], pos: dict | None = None) -> dict:
    schemes: dict[str, list[tuple[int, int]]] = {
        "realized_g8": [], "blind_storey_class": [], "calibrated_storey_class": [],
        "oracle_storey_class": [], "oracle_plus_object_type": [],
        "oracle_plus_position": [], "oracle_all": [],
    }
    n_storey_wrong = n_class_wrong = 0
    n_addressable_position = 0

    for case in cases:
        gt = case["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(case)
        if gt not in pool:
            continue
        con = case["internals"].get("constraints") or {}
        gf = cand_feats(gt, pool[gt], idx, pos)
        n_addressable_position += gf["position_slot"] is not None

        # was the model's extraction correct for this case? (real reliability)
        ext_storey = _storey_key(con.get("storey_name"))
        ext_class = con.get("ifc_class")
        storey_ok = ext_storey is not None and ext_storey == gf["storey"]
        class_ok = ext_class is not None and ext_class == gf["ifc_class"]
        n_storey_wrong += (con.get("storey_name") is not None and not storey_ok)
        n_class_wrong += (ext_class is not None and not class_ok)

        # realized
        schemes["realized_g8"].append(realized_rank(case, gt))
        # blind: rerank by extracted storey+class, equal weight regardless of correctness.
        # We score agreement with the EXTRACTED value (not GT), so a wrong extraction
        # rewards the wrong cohort and demotes GT.
        ef = {"storey": ext_storey, "ifc_class": ext_class}
        blind = _score_vs_extracted(pool, idx, ef, {"storey": 1.0, "ifc_class": 1.0})
        schemes["blind_storey_class"].append(_rank_stats(blind, gt))
        # calibrated (oracle): zero the weight of a field the model got wrong.
        cw = {"storey": 1.0 if storey_ok else 0.0, "ifc_class": 1.0 if class_ok else 0.0}
        calib = _score_vs_extracted(pool, idx, ef, cw)
        schemes["calibrated_storey_class"].append(_rank_stats(calib, gt))
        # oracle extraction: perfect storey+class.
        osc = score_pool(pool, idx, gt, {"storey": 1.0, "ifc_class": 1.0}, pos)
        schemes["oracle_storey_class"].append(_rank_stats(osc, gt))
        # oracle + object_type (the cut-2 attribute discriminator under perfect extraction).
        oot = score_pool(pool, idx, gt, {"storey": 1.0, "ifc_class": 1.0, "object_type": 1.0}, pos)
        schemes["oracle_plus_object_type"].append(_rank_stats(oot, gt))
        # oracle + position_context (the ifc_engine NEXT_TO slot — the thesis L4 unlock that
        # the earlier cuts OMITTED because it isn't in element_index).
        opp = score_pool(pool, idx, gt, {"storey": 1.0, "ifc_class": 1.0, "position_slot": 1.0}, pos)
        schemes["oracle_plus_position"].append(_rank_stats(opp, gt))
        # oracle all (both discriminators).
        oal = score_pool(pool, idx, gt,
                         {"storey": 1.0, "ifc_class": 1.0, "object_type": 1.0, "position_slot": 1.0}, pos)
        schemes["oracle_all"].append(_rank_stats(oal, gt))

    n = len(schemes["realized_g8"])
    pool_sizes = [len(pool_candidates(c)) for c in cases
                  if c["scenario"]["ground_truth"]["target_guid"] in pool_candidates(c)]
    metrics = {k: aggregate(v) for k, v in schemes.items()}

    # Realistic object_type specialist: object_type oracle reliability r=1 is a ceiling; a
    # real photo specialist extracts the Revit family-type ~0.625 (cut-2 r). Under SOFT
    # rerank with calibration, a correct extraction lands GT near the +object_type rank and a
    # wrong one falls back to the coarse rank (no recall loss). Expected (per metric):
    #   E = r·oracle_plus_object_type + (1-r)·oracle_storey_class.
    R_OBJ = 0.625
    o, c = metrics["oracle_plus_object_type"], metrics["oracle_storey_class"]
    metrics["realistic_object_type_r0.625"] = {
        m: round(R_OBJ * o[m] + (1 - R_OBJ) * c[m], 3 if m == "mrr" else 1)
        for m in ("top1", "top5", "top10", "mrr")
    }

    return {
        "n_cases": n,
        "pool_median": statistics.median(pool_sizes),
        "n_addressable_position": n_addressable_position,
        "note": "blind/calibrated rows use ONLY storey+class (2 fields) to isolate the "
                "calibration effect; they sit below realized_g8 (full pipeline). The two "
                "discriminators are object_type (attribute) and position_context (the "
                "ifc_engine NEXT_TO slot, reconstructed offline — the thesis L4 unlock).",
        "extraction_reliability_observed": {
            "storey_correct": round(1 - n_storey_wrong / n, 3),
            "ifc_class_correct": round(1 - n_class_wrong / n, 3),
        },
        "metrics": metrics,
    }


def _score_vs_extracted(pool: dict[str, dict], idx: dict, ext: dict,
                        weights: dict[str, float]) -> dict[str, float]:
    """score(c) = Σ_f w_f · [feature_f(c) == EXTRACTED value_f] (used for blind/calibrated:
    the target value is what the model extracted, which may be wrong)."""
    out: dict[str, float] = {}
    for guid, tc in pool.items():
        cf = cand_feats(guid, tc, idx)
        out[guid] = sum(w * (ext.get(f) is not None and cf.get(f) == ext.get(f))
                        for f, w in weights.items())
    return out


def make_figure(metrics: dict, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = ["realized_g8", "oracle_storey_class", "oracle_plus_object_type",
             "oracle_plus_position", "oracle_all"]
    labels = ["realized\n(G8)", "oracle\nstorey+class", "oracle\n+object_type",
              "oracle\n+position\n(L4 unlock)", "oracle\nall"]
    top1 = [metrics[k]["top1"] for k in order]
    top10 = [metrics[k]["top10"] for k in order]
    x = range(len(order))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(x, top10, "o-", color="tab:blue", label="Top-10")
    ax.plot(x, top1, "s-", color="tab:green", label="Top-1")
    for xi, (a, b) in enumerate(zip(top1, top10)):
        ax.annotate(f"{b:.0f}", (xi, b), textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center")
        ax.annotate(f"{a:.0f}", (xi, a), textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("accuracy (%)")
    ax.set_title("Idea 3a 3rd cut — soft-rerank prize on Top-k (real pools, GT-in-pool 100%)")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    ap.add_argument("--position", type=Path, default=REPO_ROOT / "data" / "references" / "position_index.jsonl",
                    help="offline-reconstructed NEXT_TO slot table (reconstruct_position_index.py)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "output" / "rerank_prize.json")
    ap.add_argument("--fig", type=Path, help="save the Top-k prize figure (PNG)")
    args = ap.parse_args()

    idx = load_index(args.index)
    cases = load_cases(args.traces)
    from reconstruct_position_index import load_position_index
    pos = load_position_index(args.position)
    res = run(idx, cases, pos)

    m = res["metrics"]
    print(f"\n=== Idea 3a THIRD CUT — soft-rerank prize on Top-k/MRR "
          f"({res['n_cases']} cases, pool median {res['pool_median']}, GT-in-pool 100%) ===")
    rel = res["extraction_reliability_observed"]
    print(f"observed extraction reliability (from traces): storey {rel['storey_correct']}, "
          f"ifc_class {rel['ifc_class_correct']}")
    print(f"  position_context addressable (multi-filler-wall targets): {res['n_addressable_position']}/{res['n_cases']}")
    print(f"\n  {'scheme':<30}{'Top-1':<9}{'Top-5':<9}{'Top-10':<9}{'MRR'}")
    print("  " + "-" * 58)
    for k in ["realized_g8", "blind_storey_class", "calibrated_storey_class",
              "oracle_storey_class", "realistic_object_type_r0.625", "oracle_plus_object_type",
              "oracle_plus_position", "oracle_all"]:
        d = m[k]
        print(f"  {k:<30}{d['top1']:<9}{d['top5']:<9}{d['top10']:<9}{d['mrr']}")
    obj = round(m["oracle_plus_object_type"]["top10"] - m["oracle_storey_class"]["top10"], 1)
    posp = round(m["oracle_plus_position"]["top1"] - m["oracle_storey_class"]["top1"], 1)
    print(f"\n  object_type prize (oracle, Top-10)   : +{obj} pp over coarse")
    print(f"  position_context prize (oracle, Top-1): +{posp} pp over coarse "
          f"(thesis L4 'pool=1 for 35 cases' unlock)")
    print(f"  oracle_all (both discriminators) Top-1 {m['oracle_all']['top1']} / Top-10 {m['oracle_all']['top10']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"\nwrote {args.out}")
    if args.fig:
        make_figure(m, args.fig)


if __name__ == "__main__":
    main()
