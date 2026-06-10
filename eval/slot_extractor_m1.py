"""M1a — position-slot extractor: intrinsic eval harness + floor/ceiling baselines.

The spec's M1 build (`docs/specs/position_slot_extractor.md`). Before building any
deterministic CV detector we need (a) the eval harness, (b) the baselines that fix the
*floor* and *ceiling*, and (c) the M-vs-i decomposition that says where detector effort
should go. This module is that scaffold; the actual image detector (Arm A on the marked
plan / Arm B mark-free) is M1b and plugs a new predictor into `PREDICTORS`.

Measured facts that motivate this (held-out, Tier-3, 35 fillers with a reconstructed
GT slot — = the thesis "pool=1 for 35 cases"):
  * G8 extracts `position_context` for 0/35 fillers  → realized slot info = none.
  * the NL query carries storey + class only, NO positional cue → text cannot recover
    the slot; it is a genuinely *visual* target (justifies the image detector in M1b).
So the whole oracle Top-1 gap (fillers 2.4 → 91.0) is the *unextracted* slot.

A predictor maps a case → (i_pred, M_pred, confidence); `None` = abstain. Intrinsic
metrics + the downstream filler Top-k (feed the predicted slot → soft rerank) are both
reported, so M1b is scored on the metric that matters (Top-k), not just slot accuracy.
"""
from __future__ import annotations
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

EVAL = Path(__file__).resolve().parent
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          realized_rank, _rank_stats, _topk, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

Slot = tuple[Optional[int], Optional[int], float]  # (i, M, confidence)


def gt_slot(case, pos) -> Optional[tuple[int, int]]:
    g = case["scenario"]["ground_truth"]["target_guid"]
    p = pos.get(g)
    return (p["wall_position_index"], p["wall_child_total"]) if p else None


# ── predictors ──────────────────────────────────────────────────────────────
def make_prior(fillers, pos) -> Callable:
    Ms = [gt_slot(c, pos)[1] for c in fillers]
    Is = [gt_slot(c, pos)[0] for c in fillers]
    mM, mI = Counter(Ms).most_common(1)[0][0], Counter(Is).most_common(1)[0][0]

    def f(case) -> Slot:
        return (mI, mM, 0.1)   # in-sample modal prior — the floor
    return f


def realized_g8(case) -> Slot:
    """Parse G8's own extracted position_context (free-text) → (i, M) if present."""
    pc = (case.get("internals", {}).get("constraints", {}) or {}).get("position_context")
    if not pc:
        return (None, None, 0.0)        # abstain (the measured reality: 0/35)
    m = re.search(r"(\d+)\D+(\d+)", str(pc))
    return (int(m.group(1)), int(m.group(2)), 0.5) if m else (None, None, 0.0)


def text_parse(case) -> Slot:
    """Deterministic Arm-0 on the honest NL query. Proven to recover nothing here
    (queries carry storey+class only) — kept to *measure* that, not to win."""
    q = case["scenario"].get("query_text", "").lower()
    m = re.search(r"(\d+)\w*\s+of\s+(\d+)", q) or re.search(r"(first|second|third|fourth|fifth)\b", q)
    if not m:
        return (None, None, 0.0)
    return (None, None, 0.0)            # storey ordinals only — never the slot


def make_oracle_M(fillers, pos) -> Callable:
    """Host-wall known ⇒ M = wall child_total is deterministic; i = prior. Isolates the
    *i*-ordering difficulty (the part a detector must actually solve)."""
    mI = Counter(gt_slot(c, pos)[0] for c in fillers).most_common(1)[0][0]

    def f(case) -> Slot:
        gt = gt_slot(case, pos)
        return (mI, gt[1], 0.5) if gt else (None, None, 0.0)
    return f


def make_oracle_i(fillers, pos) -> Callable:
    """Mirror: i known, M = prior. Isolates the *M*-counting difficulty."""
    mM = Counter(gt_slot(c, pos)[1] for c in fillers).most_common(1)[0][0]

    def f(case) -> Slot:
        gt = gt_slot(case, pos)
        return (gt[0], mM, 0.5) if gt else (None, None, 0.0)
    return f


def oracle_full(pos) -> Callable:
    def f(case) -> Slot:
        gt = gt_slot(case, pos)
        return (gt[0], gt[1], 1.0) if gt else (None, None, 0.0)
    return f


# ── evaluation ──────────────────────────────────────────────────────────────
ADDR_W = {"storey": 1.0, "ifc_class": 1.0, "position_slot": 1.0}


def intrinsic(pred: Callable, fillers, pos) -> dict:
    n = len(fillers)
    cov = ei = eM = joint = w1 = 0
    for c in fillers:
        gi, gM = gt_slot(c, pos)
        pi, pM, _ = pred(c)
        if pi is None and pM is None:
            continue
        cov += 1
        ei += (pi == gi)
        eM += (pM == gM)
        joint += (pi == gi and pM == gM)
        w1 += (pi is not None and abs(pi - gi) <= 1)
    return {"coverage": cov / n, "exact_i": ei / n, "exact_M": eM / n,
            "joint": joint / n, "within1_i": w1 / n}


def downstream(pred: Callable, fillers, idx, pos) -> dict:
    """Feed the *predicted* slot as the search key → soft rerank → filler Top-1/Top-10.
    Each candidate (incl. GT) scores +1 on the slot only if ITS OWN true slot equals the
    prediction — so a wrong prediction gives GT no slot credit (no self-match artefact)."""
    t1 = t10 = 0.0
    n = 0
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        pi, pM, _ = pred(c)
        gf = cand_feats(gt, pool[gt], idx, pos)          # target's true storey + class
        key_slot = (pi, pM) if pi is not None else None  # the predicted search key
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, pos)
            s = float(cf.get("storey") == gf.get("storey")) + float(cf.get("ifc_class") == gf.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += 1.0
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        t1 += _topk(h, t, 1); t10 += _topk(h, t, 10)
    return {"n": n, "top1": 100 * t1 / n, "top10": 100 * t10 / n}


def run(idx, cases, pos) -> dict:
    fillers = [c for c in cases if gt_slot(c, pos)]
    preds = {
        "prior (modal i,M) — FLOOR": make_prior(fillers, pos),
        "text-parse (honest query)": text_parse,
        "G8 realized position_context": realized_g8,
        "oracle M (host known), prior i": make_oracle_M(fillers, pos),
        "oracle i, prior M": make_oracle_i(fillers, pos),
        "oracle full (i,M) — CEILING": oracle_full(pos),
    }
    out = {"n_fillers": len(fillers), "rows": {}}
    for name, p in preds.items():
        out["rows"][name] = {**intrinsic(p, fillers, pos), **downstream(p, fillers, idx, pos)}
    return out


def make_figure(r: dict, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = r["rows"]
    names = list(rows)
    short = ["floor\n(prior)", "text", "G8\nrealized", "oracle M\n+prior i",
             "oracle i\n+prior M", "oracle\nfull"]
    t1 = [rows[n]["top1"] for n in names]
    colors = ["#cccccc", "#1f77b4", "#1f77b4", "#7fb3d5", "#ff7f0e", "#9467bd"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(names)), t1, color=colors)
    for b, v in zip(bars, t1):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(range(len(names))); ax.set_xticklabels(short, fontsize=9)
    ax.set_ylabel("filler Top-1 (%)"); ax.set_ylim(0, 100)
    ax.set_title("M1a position-slot harness — the 2.4→91 gap is the unextracted slot\n"
                 "(i-ordering is the bigger, harder lever: oracle-i 29.5 > oracle-M 18.8)", fontsize=11)
    ax.axhline(2.4, ls="--", c="#999", lw=1); ax.text(0.1, 4, "realized floor 2.4", fontsize=8, color="#777")
    fig.tight_layout(); fig.savefig(out_path, dpi=120); plt.close(fig)


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    r = run(idx, cases, pos)
    figp = REPO / "output" / "slot_extractor_m1.png"
    figp.parent.mkdir(parents=True, exist_ok=True)
    make_figure(r, figp)
    print(f"\n=== M1a position-slot harness — {r['n_fillers']} held-out fillers (Tier-3) ===")
    h = f"{'predictor':<32}{'cov':>6}{'exact_i':>8}{'exact_M':>8}{'joint':>7}{'±1_i':>6}{'Top-1':>8}{'Top-10':>8}"
    print(h); print("-" * len(h))
    for name, m in r["rows"].items():
        print(f"{name:<32}{m['coverage']*100:>5.0f}%{m['exact_i']*100:>7.0f}%"
              f"{m['exact_M']*100:>7.0f}%{m['joint']*100:>6.0f}%{m['within1_i']*100:>5.0f}%"
              f"{m['top1']:>7.1f}{m['top10']:>8.1f}")
    print("\nfiller refs: realized G8 Top-1≈2.4 / oracle slot Top-1 91.0 (spatial_address_ceiling)")
    print("read: floor=prior, realizable-now=G8 (slot empty), ceiling=oracle. M1b (image "
          "detector) must beat the floor on exact_i — M is ~free once the host wall is known.")


if __name__ == "__main__":
    main()
