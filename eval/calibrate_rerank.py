"""Step C — calibrate (temperature) → recall-safe soft-rerank → selective prediction.

The RQ2 mechanism (enhanced module L170-188): the position-slot confidence passed Step B's
ECE gate (AUROC 0.80, ECE 0.206), so here we (1) temperature-scale it (report ECE before/after),
(2) use the *calibrated* confidence as a recall-safe SOFT weight on the slot-match term — never
a hard filter, so GT stays in the pool — and measure filler Top-1/Top-10 vs the floor and the
hard-match realized number, and (3) report the selective-prediction coverage-vs-accuracy curve
(L183: "clarify"/defer = first-class outcome). Lead with the soft-rerank, calibration supports
(L102). All scored against `gslot` (the convention-consistent GT — see ROADMAP glossary lock).

Run:  .venv/bin/python eval/calibrate_rerank.py
Out:  output/calibrate_rerank.{png,json} + ledger row (printed).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
from calibration_diag import ece
from field_contract import CalibrationPair, collect_pairs
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          _rank_stats, _topk, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

OUT = REPO / "output"
EPS = 1e-6


# ── temperature scaling (pure-python; no scipy) ──────────────────────────────
def _logit(p: float) -> float:
    p = min(1 - EPS, max(EPS, p))
    return math.log(p / (1 - p))


def apply_T(conf: float, T: float) -> float:
    """Recalibrated probability = sigmoid(logit(conf) / T)."""
    z = _logit(conf) / T
    return 1.0 / (1.0 + math.exp(-z))


def _nll(pairs: list[CalibrationPair], T: float) -> float:
    s = 0.0
    for p in pairs:
        q = apply_T(p.confidence, T)
        q = min(1 - EPS, max(EPS, q))
        s += -(math.log(q) if p.correct else math.log(1 - q))
    return s / len(pairs)


def fit_temperature(pairs: list[CalibrationPair]) -> float:
    """1-D search for T>0 minimising NLL (coarse grid + local refine)."""
    grid = [0.1 + 0.05 * k for k in range(79)]            # 0.10 .. 4.00
    best = min(grid, key=lambda T: _nll(pairs, T))
    fine = [best - 0.05 + 0.005 * k for k in range(21)]   # ±0.05 refine
    return min((T for T in fine if T >= 0.05), key=lambda T: _nll(pairs, T))


# ── recall-safe soft-rerank on the M1a downstream ────────────────────────────
def downstream_soft(pred: Callable, fillers, idx, gslot, weight: Callable[[float], float]) -> dict:
    """Like slot_extractor_m1.downstream but the slot-match term is scaled by `weight(conf)`
    (a per-case soft weight) instead of a hard +1. storey/class stay at +1 each. Recall-safe:
    the slot term only *adds*, never prunes, so GT never leaves the pool."""
    t1 = t10 = 0.0
    n = 0
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        n += 1
        pi, pM, conf = pred(c)
        gf = cand_feats(gt, pool[gt], idx, gslot)
        key_slot = (pi, pM) if pi is not None else None
        w = weight(conf) if key_slot is not None else 0.0
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == gf.get("storey")) + float(cf.get("ifc_class") == gf.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += w
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        t1 += _topk(h, t, 1); t10 += _topk(h, t, 10)
    return {"n": n, "top1": 100 * t1 / n, "top10": 100 * t10 / n}


def _bootstrap_top1_ci(per_case_hits: list[float], n_boot: int = 10000, seed: int = 0):
    """Percentile 95% CI for a Top-1 rate from per-case 0/1 hits (n=35 is small)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = np.asarray(per_case_hits, float)
    n = len(arr)
    boot = arr[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return round(100 * float(arr.mean()), 1), [round(100 * float(lo), 1), round(100 * float(hi), 1)]


def downstream_hits(pred, fillers, idx, gslot, weight) -> list[float]:
    """Per-case Top-1 0/1 list for the soft-rerank — feeds the bootstrap CI."""
    hits = []
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        pi, pM, conf = pred(c)
        gf = cand_feats(gt, pool[gt], idx, gslot)
        key_slot = (pi, pM) if pi is not None else None
        w = weight(conf) if key_slot is not None else 0.0
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == gf.get("storey")) + float(cf.get("ifc_class") == gf.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += w
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        hits.append(_topk(h, t, 1))
    return hits


# ── selective prediction (coverage vs accuracy) ──────────────────────────────
def selective_curve(pred, fillers, idx, gslot, T: float) -> list[dict]:
    """Sweep a calibrated-confidence threshold τ. A case is *answered* iff its calibrated
    confidence ≥ τ; otherwise the system DEFERS ('here are the candidates'). Accuracy = Top-1
    over answered cases only; coverage = answered / total. τ=0 ⇒ coverage 1.0 = the soft number."""
    per = []
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        pi, pM, conf = pred(c)
        cconf = apply_T(conf, T) if pi is not None else 0.0
        gf = cand_feats(gt, pool[gt], idx, gslot)
        key_slot = (pi, pM) if pi is not None else None
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == gf.get("storey")) + float(cf.get("ifc_class") == gf.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += cconf
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        per.append((cconf, _topk(h, t, 1)))
    N = len(per)
    curve = []
    for tau in [k / 20 for k in range(21)]:
        ans = [hit for cc, hit in per if cc >= tau]
        if not ans:
            continue
        curve.append({"tau": tau, "coverage": len(ans) / N, "top1_answered": 100 * sum(ans) / len(ans)})
    return curve


def make_figure(stats, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (axb, axs) = plt.subplots(1, 2, figsize=(13, 5))

    # (a) soft-rerank bars
    labels = ["floor\n(prior)", "hard\nmatch", "raw-soft\n(conf)", "calib-soft\n(T-scaled)"]
    t1 = [stats["floor"]["top1"], stats["hard"]["top1"], stats["raw_soft"]["top1"], stats["calib_soft"]["top1"]]
    t10 = [stats["floor"]["top10"], stats["hard"]["top10"], stats["raw_soft"]["top10"], stats["calib_soft"]["top10"]]
    x = range(len(labels))
    axb.bar([i - 0.2 for i in x], t1, width=0.4, label="Top-1", color="#1f77b4")
    axb.bar([i + 0.2 for i in x], t10, width=0.4, label="Top-10", color="#9ecae1")
    for i, v in enumerate(t1):
        axb.text(i - 0.2, v + 1, f"{v:.0f}", ha="center", fontsize=9, fontweight="bold")
    for i, v in enumerate(t10):
        axb.text(i + 0.2, v + 1, f"{v:.0f}", ha="center", fontsize=9)
    axb.set_xticks(list(x)); axb.set_xticklabels(labels, fontsize=9)
    axb.set_ylabel("filler accuracy (%)"); axb.set_ylim(0, 100)
    axb.set_title(f"Recall-safe soft-rerank (vs gslot, n={stats['hard']['n']})\n"
                  f"ECE {stats['ece_raw']:.3f} → {stats['ece_cal']:.3f} (T={stats['T']:.2f})", fontsize=11)
    axb.legend(fontsize=8)

    # (b) selective-prediction coverage vs accuracy
    cur = stats["selective"]
    cov = [p["coverage"] for p in cur]; acc = [p["top1_answered"] for p in cur]
    axs.plot(cov, acc, "o-", color="#d62728", lw=2)
    for p in cur:
        if abs(p["tau"] * 20 % 4) < 1e-9:   # label every 0.2
            axs.annotate(f"τ={p['tau']:.1f}", (p["coverage"], p["top1_answered"]),
                         fontsize=7, textcoords="offset points", xytext=(4, 4))
    axs.set_xlabel("coverage (fraction answered)"); axs.set_ylabel("Top-1 on answered (%)")
    axs.set_xlim(0, 1.02); axs.set_ylim(0, 105)
    axs.set_title("Selective prediction — defer below τ (L183)\nconfident subset is far more accurate", fontsize=11)
    axs.grid(alpha=0.3)

    fig.suptitle("Step C — calibrated soft-rerank + selective prediction (RQ2 mechanism)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=130)
    print(f"figure → {out_path}")


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)

    pairs = collect_pairs(pred, fill, gslot)
    T = fit_temperature(pairs)
    ece_raw = ece(pairs, 5)["ece"]
    ece_cal = ece([CalibrationPair(p.case_id, apply_T(p.confidence, T), p.correct,
                                   p.i_correct, p.M_correct) for p in pairs], 5)["ece"]

    import slot_extractor_m1 as m1
    floor = m1.downstream(m1.make_prior(fill, gslot), fill, idx, gslot)
    hard = downstream_soft(pred, fill, idx, gslot, weight=lambda c: 1.0)
    raw_soft = downstream_soft(pred, fill, idx, gslot, weight=lambda c: c)
    calib_soft = downstream_soft(pred, fill, idx, gslot, weight=lambda c: apply_T(c, T))
    selective = selective_curve(pred, fill, idx, gslot, T)

    # bootstrap 95% CI on the realized hard-match Top-1 (the headline 67.6, n=35)
    hard_hits = downstream_hits(pred, fill, idx, gslot, weight=lambda c: 1.0)
    hard_top1_pt, hard_top1_ci = _bootstrap_top1_ci(hard_hits)

    stats = {"T": T, "ece_raw": ece_raw, "ece_cal": ece_cal,
             "floor": floor, "hard": hard, "raw_soft": raw_soft, "calib_soft": calib_soft,
             "hard_top1_ci95": hard_top1_ci, "selective": selective}

    OUT.mkdir(exist_ok=True)
    make_figure(stats, OUT / "calibrate_rerank.png")
    json.dump(stats, open(OUT / "calibrate_rerank.json", "w"), indent=2)

    print(f"\nT={T:.2f}  ECE {ece_raw:.3f} → {ece_cal:.3f}")
    print(f"realized hard Top-1 = {hard_top1_pt:.1f}  95% CI {hard_top1_ci}  (n={hard['n']})")
    print(f"Top-1  floor={floor['top1']:.1f}  hard={hard['top1']:.1f}  "
          f"raw-soft={raw_soft['top1']:.1f}  calib-soft={calib_soft['top1']:.1f}")
    print(f"Top-10 floor={floor['top10']:.1f}  hard={hard['top10']:.1f}  "
          f"raw-soft={raw_soft['top10']:.1f}  calib-soft={calib_soft['top10']:.1f}")
    hi = max(stats["selective"], key=lambda p: p["top1_answered"])
    print(f"selective: at coverage {hi['coverage']:.2f} (τ={hi['tau']:.2f}) → Top-1 {hi['top1_answered']:.1f}")


if __name__ == "__main__":
    main()
