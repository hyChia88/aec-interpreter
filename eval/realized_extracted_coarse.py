"""#1 fix — REALIZED filler rerank using the model's EXTRACTED coarse fields (no oracle).

The published 67.6% (calibrate_rerank.py) scores each candidate's storey/ifc_class against the
TARGET'S OWN values (gf = cand_feats(gt,...)) — i.e. oracle coarse fields. This script re-runs the
identical soft-rerank but takes the coarse target value from the G8 trace's ACTUALLY-EXTRACTED
constraints (internals.constraints.storey_name / ifc_class). The position-slot is the same real
OpenCV detector. Result = genuinely end-to-end realized (slot AND coarse fields are real).

We report both so the gap is explicit, plus the per-field reliabilities that explain it.

Run:  .venv/bin/python eval/realized_extracted_coarse.py
Out:  output/realized_extracted_coarse.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          _rank_stats, _topk, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS
from calibrate_rerank import _bootstrap_top1_ci, fit_temperature, apply_T
from field_contract import collect_pairs

OUT = REPO / "output"


def _skey(v):
    if v is None:
        return None
    m = re.search(r"-?\d+", str(v))
    return m.group(0) if m else str(v).strip().lower()


def extracted_coarse(case) -> dict:
    """The model's actually-extracted coarse target value (NOT the GT)."""
    con = case["internals"]["constraints"]
    return {"storey": _skey(con.get("storey_name")), "ifc_class": con.get("ifc_class")}


def gt_class_of(case, gt) -> str | None:
    for rr in case["internals"].get("retrieval_results", []):
        for cd in rr.get("candidates", []):
            if cd.get("guid") == gt:
                return cd.get("ref_type") or cd.get("type")
    return None


def _rerank(pred, fillers, idx, gslot, weight, coarse_target: Callable[[dict, str], dict]):
    """Soft-rerank, but the coarse target value is supplied by `coarse_target` (oracle vs extracted)."""
    hits = []
    t10 = 0.0
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        pi, pM, conf = pred(c)
        ct = coarse_target(c, gt)
        key_slot = (pi, pM) if pi is not None else None
        w = weight(conf) if key_slot is not None else 0.0
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == ct.get("storey")) + float(cf.get("ifc_class") == ct.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += w
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        hits.append(_topk(h, t, 1))
        t10 += _topk(h, t, 10)
    n = len(hits)
    pt, ci = _bootstrap_top1_ci(hits)
    return {"n": n, "top1": pt, "top1_ci95": ci, "top10": round(100 * t10 / n, 1)}


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)

    def oracle_target(c, gt):
        return cand_feats(gt, pool_candidates(c)[gt], idx, gslot)

    oracle = _rerank(pred, fill, idx, gslot, lambda c: 1.0, oracle_target)
    extracted = _rerank(pred, fill, idx, gslot, lambda c: 1.0, lambda c, gt: extracted_coarse(c))

    # selective-prediction curve on the EXTRACTED-coarse rerank (end-to-end consistent)
    T = fit_temperature(collect_pairs(pred, fill, gslot))
    per = []
    for c in fill:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        pi, pM, conf = pred(c)
        cconf = apply_T(conf, T) if pi is not None else 0.0
        ct = extracted_coarse(c)
        key_slot = (pi, pM) if pi is not None else None
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == ct.get("storey")) + float(cf.get("ifc_class") == ct.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += cconf
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        per.append((cconf, _topk(h, t, 1)))
    N = len(per)
    sel = []
    for k in range(21):
        tau = k / 20
        ans = [hit for cc, hit in per if cc >= tau]
        if ans:
            sel.append({"tau": round(tau, 2), "coverage": round(len(ans) / N, 3),
                        "top1_answered": round(100 * sum(ans) / len(ans), 1)})
    # the defer-~20% operating point (coverage closest to 0.80)
    defer20 = min(sel, key=lambda p: abs(p["coverage"] - 0.80))

    # per-field reliability ON THE FILLER SUBSET (what actually feeds this rerank)
    st_ok = cl_ok = 0
    for c in fill:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        ec = extracted_coarse(c)
        gs = _skey(c["scenario"]["ground_truth"].get("target_storey"))
        gc = gt_class_of(c, gt)
        st_ok += (ec["storey"] == gs and ec["storey"] is not None)
        cl_ok += (ec["ifc_class"] is not None and gc is not None and ec["ifc_class"] == gc)
    nf = len(fill)

    out = {
        "n_fillers": nf,
        "note": "oracle = coarse target value is GT (the published 67.6 path); extracted = coarse "
                "target value is the G8 trace's actually-extracted storey_name/ifc_class. Slot is the "
                "real OpenCV detector in both. hard match (weight=1).",
        "oracle_coarse": oracle,
        "extracted_coarse": extracted,
        "filler_field_reliability": {
            "storey_normalized": round(100 * st_ok / nf, 1),
            "ifc_class": round(100 * cl_ok / nf, 1),
        },
        "selective_extracted_coarse": {"defer20_point": defer20, "curve": sel},
    }
    OUT.mkdir(exist_ok=True)
    json.dump(out, open(OUT / "realized_extracted_coarse.json", "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
