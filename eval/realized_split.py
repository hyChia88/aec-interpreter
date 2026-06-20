"""#1b fix — cluttered/sparse split for BOTH the oracle-coarse and the END-TO-END
(extracted-coarse) realized rerank.

tab:split in the paper reports the split only on the oracle-coarse path (cluttered 39.1).
The abstract/discussion/conclusion then attach 39.1 to the 58.9 end-to-end number, but the
end-to-end cluttered value was never measured. This script measures it, reusing the identical
soft-rerank from realized_extracted_coarse.py. The sparse-18 subset is the re-rendered upper
storeys (Floors 2-5, render_upper_storeys.py); the cluttered-17 are the originally clean-plan
storeys (First Floor / Garage / Level 1).

Run:  .venv/bin/python eval/realized_split.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
from rerank_prize import (load_index, load_cases, pool_candidates, cand_feats,
                          _rank_stats, _topk, DEFAULT_INDEX, DEFAULT_TRACES)
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS
from calibrate_rerank import _bootstrap_top1_ci
from realized_extracted_coarse import extracted_coarse

SPARSE_STOREYS = {"2 - Second Floor", "3 - Third Floor", "4 - Fourth Floor", "5 - Fifth Floor"}


def rerank_subset(pred, fillers, idx, gslot, coarse_target):
    hits, t10 = [], 0.0
    for c in fillers:
        gt = c["scenario"]["ground_truth"]["target_guid"]
        pool = pool_candidates(c)
        if gt not in pool:
            continue
        pi, pM, conf = pred(c)
        ct = coarse_target(c, gt)
        key_slot = (pi, pM) if pi is not None else None
        w = 1.0 if key_slot is not None else 0.0
        scores = {}
        for guid, tc in pool.items():
            cf = cand_feats(guid, tc, idx, gslot)
            s = float(cf.get("storey") == ct.get("storey")) + float(cf.get("ifc_class") == ct.get("ifc_class"))
            if key_slot is not None and cf.get("position_slot") == key_slot:
                s += w
            scores[guid] = s
        h, t = _rank_stats(scores, gt)
        hits.append(_topk(h, t, 1)); t10 += _topk(h, t, 10)
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

    def storey_of(c):
        return idx[c["scenario"]["ground_truth"]["target_guid"]]["storey_name"]

    cluttered = [c for c in fill if storey_of(c) not in SPARSE_STOREYS]
    sparse = [c for c in fill if storey_of(c) in SPARSE_STOREYS]

    def oracle_t(c, gt):
        return cand_feats(gt, pool_candidates(c)[gt], idx, gslot)

    def extr_t(c, gt):
        return extracted_coarse(c)

    out = {"_storeys_cluttered": sorted({storey_of(c) for c in cluttered}),
           "_storeys_sparse": sorted({storey_of(c) for c in sparse})}
    for name, subset in [("cluttered_realistic", cluttered), ("sparse_rerender", sparse), ("aggregate", fill)]:
        out[name] = {
            "oracle_coarse": rerank_subset(pred, subset, idx, gslot, oracle_t),
            "extracted_coarse_end_to_end": rerank_subset(pred, subset, idx, gslot, extr_t),
        }
    json.dump(out, open(REPO / "output" / "realized_split.json", "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
