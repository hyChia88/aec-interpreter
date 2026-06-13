"""#8 — robustness of the realized position-slot detector to its hardcoded pixel thresholds.

The detector (`slot_detector_cv.py`) has three tuned constants at the plan's ~1500px canvas:
NEAR_R (wall-axis PCA radius), PERP_TOL (same-wall perpendicular band), MATCH_MAX (target->opening
match distance). A reviewer will ask whether the realized 67.6% Top-1 is a knife-edge fit. This
script sweeps each constant +/-25% (one at a time, and a joint grid) and reports the realized
filler Top-1, so the stability is measured rather than asserted.

Run:  .venv/bin/python eval/slot_detector_sensitivity.py  ->  output/slot_detector_sensitivity.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
import slot_extractor_m1 as m1
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

OUT = REPO / "output"
BASE = {"NEAR_R": cv.NEAR_R, "PERP_TOL": cv.PERP_TOL, "MATCH_MAX": cv.MATCH_MAX}


def realized_top1(idx, fill, gslot) -> float:
    """Re-run the detector + downstream soft-rerank under the current cv.* globals."""
    pred = cv.make_predictor(idx)
    return m1.downstream(pred, fill, idx, gslot)["top1"]


def set_params(**kw):
    for k, v in kw.items():
        setattr(cv, k, v)


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)

    base_top1 = realized_top1(idx, fill, gslot)
    results = {"base_params": BASE, "base_top1": round(base_top1, 1), "n": len(fill), "one_at_a_time": {}}

    # one-at-a-time +/-25%
    for k, v0 in BASE.items():
        row = {}
        for f in (0.75, 0.9, 1.0, 1.1, 1.25):
            set_params(**BASE)                 # reset
            setattr(cv, k, type(v0)(round(v0 * f)))
            row[f"{f:.2f}x ({getattr(cv, k)})"] = round(realized_top1(idx, fill, gslot), 1)
        results["one_at_a_time"][k] = row
    set_params(**BASE)

    # joint grid corners (all three at +/-25%)
    corners = {}
    for fn in (0.75, 1.25):
        for fp in (0.75, 1.25):
            for fm in (0.75, 1.25):
                set_params(NEAR_R=int(BASE["NEAR_R"] * fn),
                           PERP_TOL=int(BASE["PERP_TOL"] * fp),
                           MATCH_MAX=int(BASE["MATCH_MAX"] * fm))
                corners[f"N{fn}_P{fp}_M{fm}"] = round(realized_top1(idx, fill, gslot), 1)
    set_params(**BASE)
    results["joint_grid_corners"] = corners
    vals = list(corners.values()) + [base_top1]
    results["summary"] = {"min_top1": min(vals), "max_top1": max(vals),
                          "base_top1": round(base_top1, 1),
                          "spread": round(max(vals) - min(vals), 1)}

    OUT.mkdir(exist_ok=True)
    json.dump(results, open(OUT / "slot_detector_sensitivity.json", "w"), indent=2)
    print(json.dumps(results, indent=2))
    s = results["summary"]
    print(f"\nrealized Top-1 over all perturbations: [{s['min_top1']}, {s['max_top1']}]  "
          f"(base {s['base_top1']}, spread {s['spread']} pts)")


if __name__ == "__main__":
    main()
