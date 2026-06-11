"""Step A — wire detector outputs into the per-field {value, confidence, source} contract.

This is the P1 *enabling substrate* (enhanced-module §Phase-0 "contract invariant", L133):
every routable field must carry `{value, confidence, source}` so the policy can route it.
Here we bridge a slot predictor (case → (i, M, conf)) onto `schema.contract.FieldValue`,
and collect per-case `(confidence, correct)` pairs that Steps B/C (calibrate → ECE →
soft-rerank → selective prediction) consume.

CLASS-AGNOSTIC by construction: nothing here is filler-specific. The position-slot detector
(M1b) is the first client (`source="opencv"`, the OpenCV color-segmentation score per L133);
the wall-fingerprint detector plugs in later by emitting its own FieldValue with the same
shape — calibration/routing operate on `FieldValue.confidence` per `source`, not per class.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from aec_interpreter.schema.contract import FieldValue  # noqa: E402

# A predictor maps case → (i, M, confidence); (None, None, 0.0) = abstain.
Slot = tuple[Optional[int], Optional[int], float]


def slot_field(i: Optional[int], M: Optional[int], conf: float,
               source: str = "opencv", i_mirror: Optional[int] = None) -> FieldValue:
    """Wrap a position-slot prediction into the uniform contract field.

    `value` carries the structured slot (the downstream search key derives (i, M) from it);
    `confidence` is the raw, *uncalibrated* detector score (Step B calibrates it);
    `role` stays "unset" until the P1 policy routes it (Step C).
    Abstain (i is None) → an empty FieldValue (present=False), so routing skips it.
    """
    if i is None and M is None:
        return FieldValue(value=None, confidence=None, source=source)
    return FieldValue(value={"i": i, "M": M, "i_mirror": i_mirror},
                      confidence=max(0.0, min(1.0, conf)), source=source)


def field_to_key(fv: FieldValue) -> Optional[tuple[int, int]]:
    """The (i, M) search key the M1a downstream matcher consumes, or None on abstain."""
    if not fv.present:
        return None
    return (fv.value["i"], fv.value["M"])


@dataclass
class CalibrationPair:
    """One (confidence, correct) observation for reliability/ECE/temperature fitting."""
    case_id: str
    confidence: float          # raw detector confidence in [0,1]
    correct: bool              # predicted (i, M) == GT (i, M) — the event conf should predict
    i_correct: bool            # i alone (the harder lever); diagnostic only
    M_correct: bool            # M alone; diagnostic only


def collect_pairs(pred: Callable[[dict], Slot], fillers, gslot) -> list[CalibrationPair]:
    """Run a predictor over the held-out fillers → calibration pairs (abstentions dropped).

    `gslot` MUST be the convention-consistent GT (`slot_detector_cv.build_global_slot`,
    relabelled under the same GLOBAL_REF orientation the detector uses) — NOT the raw
    wdir-based `position_index`, whose i-sign is an arbitrary modelling artefact the image
    cannot recover (the two disagree on ~16/35 fillers, which would spuriously halve `correct`).

    `correct` is the *exact joint* (i, M) match — the same event the downstream matcher
    rewards (`position_slot == (pi, pM)`), so a calibrated confidence here predicts exactly
    the signal the soft-rerank will weight. The mirror index is NOT credited (downstream
    uses (pi, pM) verbatim), keeping the calibration target honest.
    """
    pairs: list[CalibrationPair] = []
    for c in fillers:
        g = c["scenario"]["ground_truth"]["target_guid"]
        row = gslot.get(g)
        if row is None:
            continue
        gi, gM = row["wall_position_index"], row["wall_child_total"]
        pi, pM, conf = pred(c)
        if pi is None and pM is None:
            continue                       # abstain — not a confidence observation
        cid = c["scenario_id"]  # noqa: F841 (kept for traceability)
        pairs.append(CalibrationPair(
            case_id=cid,
            confidence=max(0.0, min(1.0, float(conf))),
            correct=(pi == gi and pM == gM),
            i_correct=(pi == gi),
            M_correct=(pM == gM),
        ))
    return pairs


def contract_field_for(pred: Callable[[dict], Slot], case) -> FieldValue:
    """The `position_context` FieldValue this predictor produces for one case (the live arm)."""
    pi, pM, conf = pred(case)
    return slot_field(pi, pM, conf)
