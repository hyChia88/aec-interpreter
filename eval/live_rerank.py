"""The realized neuro-symbolic ranking, for the live route.

This is the mechanism behind the 67.6% filler Top-1 (eval/calibrate_rerank.py
`downstream_soft`), factored so the live service can apply it on a live Neo4j pool:

  score(candidate) = [storey matches VLM storey] + [class matches VLM class]
                     + calibrated_conf * [candidate position_slot == OpenCV-detected slot]

The VLM (Modal) supplies the coarse prefix (storey, ifc_class); the deterministic OpenCV
position-slot detector (local, no GPU) supplies the discriminating slot; temperature-scaled
confidence weights the slot term (recall-safe — it only adds, never prunes) and drives the
ANSWER/DEFER gate. Slot is scored against `gslot` (the image-recoverable GLOBAL_REF convention
— the ROADMAP convention lock), exactly as the offline eval does.

`build_rerank_context()` is called once (loads the element index + reconstructed slot table,
builds the detector, fits the temperature T on the held-out fillers). `rerank_live()` runs per
request on the live pool.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
from calibrate_rerank import apply_T, fit_temperature
from field_contract import collect_pairs
from rerank_prize import cand_feats, load_index, load_cases, _storey_key, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

TAU = 0.40


def _norm_class(s) -> str:
    return str(s or "").strip().lower().replace("ifc", "")


def build_rerank_context() -> dict:
    """Load index + slot table, build the OpenCV detector, fit temperature T (once)."""
    idx = load_index(DEFAULT_INDEX)
    pos = load_position_index(DEFAULT_POS)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fillers = [c for c in load_cases(DEFAULT_TRACES)
               if c["scenario"]["ground_truth"]["target_guid"] in pos]
    T = fit_temperature(collect_pairs(pred, fillers, gslot))
    print(f"[rerank] context ready — {len(idx)} elements, {len(gslot)} slots, T={T:.2f}")
    return {"idx": idx, "gslot": gslot, "pred": pred, "T": T}


def detect_slot(target_guid: str, idx: dict):
    """OpenCV position-slot for the MARKED target, read from its storey's plan.

    The marked plan crop is a designed human input (Arm-A): the mark gives the element's
    identity (its centroid), and the detector reads the ordinal slot from the plan layout.
    Returns (i, M, conf) or (None, None, 0.0) if the storey has no clean plan / no match.
    """
    e = idx.get(target_guid, {})
    c = e.get("centroid")
    if not c:
        return (None, None, 0.0)
    r = cv.detect((c["x"] / 1000.0, c["y"] / 1000.0), e.get("storey_name"))
    return (r["i"], r["M"], r["conf"]) if r else (None, None, 0.0)


def rerank_live(target_guid: str, pool_guids: list[str], vlm_storey, vlm_class, ctx: dict) -> dict:
    """Soft-rerank a live retrieval pool by VLM coarse prefix + OpenCV slot. Returns the
    grounded top-1, the calibrated confidence, the ANSWER/DEFER decision, and the slot.

    `target_guid` = the marked element (identity from the plan mark); its slot is read from
    layout. Recall-safe: the slot term only adds to a candidate's score; the pool is never pruned.
    """
    idx, gslot, T = ctx["idx"], ctx["gslot"], ctx["T"]
    pi, pM, conf = detect_slot(target_guid, idx)       # OpenCV slot from the marked target on the plan
    cconf = apply_T(conf, T) if pi is not None else 0.0
    key_slot = (pi, pM) if pi is not None else None

    want_storey = _storey_key(vlm_storey)
    want_class = _norm_class(vlm_class)
    scored = []
    for g in pool_guids:
        cf = cand_feats(g, {}, idx, gslot)
        s = float(cf.get("storey") == want_storey) + float(_norm_class(cf.get("ifc_class")) == want_class)
        slot_hit = key_slot is not None and cf.get("position_slot") == key_slot
        if slot_hit:
            s += cconf
        scored.append((s, g, slot_hit))
    # deterministic: score desc, then guid (stable tie-break among indistinguishable siblings)
    scored.sort(key=lambda t: (-t[0], t[1]))
    ranked = [g for _, g, _ in scored]
    return {
        "slot": [pi, pM] if pi is not None else None,
        "conf_raw": round(conf, 2),
        "conf_cal": round(cconf, 2),
        "tau": TAU,
        "decision": "ANSWER" if cconf >= TAU else "DEFER",
        "top1_guid": ranked[0] if ranked else None,
        "ranked": ranked,
        "n_slot_matches": sum(1 for _, _, hit in scored if hit),
    }
