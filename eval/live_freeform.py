"""Free-input live inference — the real system on an ARBITRARY photo + note (no case id).

This is the honest "free input" counterpart of live_infer.py. live_infer runs a known
held-out case (and the browser case-picker reranks with the ground-truth GUID via
live_rerank). HERE there is no ground truth and no plan-side pointer, so we run the
COARSE path only:

    site photo (+ optional floorplan) + note
      -> Modal GPU VLM (deployed G8 adapter)
      -> Constraints  (storey, ifc_class, position_context + conf, spatial_relations + conf)
      -> QueryPlanner -> live Neo4j RetrievalBackend  (confidence-weighted, relation-aware)
      -> ranked candidate pool + fingerprint level + ANSWER/DEFER.

What we DELIBERATELY do not run: the OpenCV ordinal-slot rerank (live_rerank.rerank_live).
That needs the target element's plan location (it reads the slot from the marked plan), which
free input does not provide. The ordinal slot among geometrically identical siblings is the
paper's documented image-unrecoverable signal, so those cases honestly DEFER and return the
shortlist. Everything the VLM CAN recover from the photo+note — storey, class, coarse
position_context, and the relational fingerprints (direction / object_subtype / material) — is
used by the planner to rank and, when discriminating, to converge on one element.

Used by:  service/app.py  POST /api/ground_freeform   (browser "Free input" tab).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

# Reuse the exact extraction post-parse the rest of the live stack uses.
from live_infer import parsed_to_constraints  # noqa: E402

TAU = 0.40
# fingerprint levels that are discriminating enough to commit on (vs. just narrowing the pool)
COMMIT_LEVELS = {"relation_fingerprint", "exact_slot"}
CASES_MANIFEST = REPO_ROOT / "site" / "assets" / "3d" / "cases.json"


def build_storey_glb_map(manifest_path: Path = CASES_MANIFEST) -> dict[str, str]:
    """storey_name -> GLB filename, derived from the precomputed viewer manifest.

    The 3D viewer ships one GLB per storey; the held-out manifest already pairs every
    storey with its GLB, so we reuse that mapping for free-input predictions instead of
    hardcoding it. Unknown storeys fall back to whole-model framing in the viewer.
    """
    if not manifest_path.exists():
        return {}
    out: dict[str, str] = {}
    for m in json.loads(manifest_path.read_text()):
        storey, glb = m.get("storey"), m.get("glb")
        if storey and glb:
            out.setdefault(storey, glb)
    return out


def _constraints_payload(c) -> dict:
    """Constraints -> per-field {value, confidence, source} for the details panel."""
    return {
        "storey_name": c.storey_name,
        "ifc_class": c.ifc_class,
        "space_name": c.space_name,
        "position_context": c.position_context,
        "position_context_confidence": c.position_context_confidence,
        "position_context_source": c.position_context_source,
        "overall_confidence": round(float(c.confidence or 0.0), 2),
        "spatial_relations": [
            {
                "predicate": r.predicate,
                "object_type": r.object_type,
                "object_subtype": r.object_subtype,
                "direction": r.direction,
                "object_material": r.object_material,
                "confidence": round(float(r.confidence or 0.0), 2),
            }
            for r in c.spatial_relations
        ],
    }


def _executed_plan(pipeline_trace):
    """The query plan that actually produced the candidates (first non-empty in priority order).

    run_pipeline_case appends one retrieval_result per attempted plan and breaks on the first
    with pool_size>0, so the executed plan is query_plans[len(retrieval_results)-1].
    """
    rr = pipeline_trace.retrieval_results or []
    qp = pipeline_trace.query_plans or []
    if not rr or not qp:
        return (qp[0] if qp else None), (rr[-1] if rr else None)
    idx = min(len(rr) - 1, len(qp) - 1)
    return qp[idx], rr[-1]


def _waterfall(pipeline_trace, initial_pool_size: int, final_pool_size: int) -> list[dict]:
    """Candidate-pool shrink: whole model -> retrieved pool -> ranked shortlist."""
    _, rr = _executed_plan(pipeline_trace)
    retrieved = (rr.raw_pool_size or rr.pool_size) if rr else final_pool_size
    pooled = rr.pool_size if rr else final_pool_size
    stages = [{"stage": "model", "n": int(initial_pool_size or 0)}]
    if retrieved:
        strat = (rr.strategy_actually_used or rr.query_plan_used.strategy) if rr else "retrieve"
        stages.append({"stage": strat, "n": int(retrieved)})
    stages.append({"stage": "ranked", "n": int(pooled or 0)})
    return stages


async def run_freeform(
    image_bytes_list: list[bytes],
    chat_text: str,
    metadata_text: str,
    engine,
    backend,
    *,
    floorplan_present: bool = False,
) -> dict:
    """Run the coarse free-input pipeline and return a viewer-ready dict.

    `engine`/`backend` are the once-built shared objects from the service (build_engine_backend).
    """
    from aec_interpreter.neurosym.pipeline import run_pipeline_case

    t0 = time.perf_counter()
    # 1) VLM (Modal GPU) — pass bytes straight through (no disk round-trip needed).
    import live_infer as li  # call_modal_vlm reads bytes; reuse its modal client
    import modal

    predictor = modal.Cls.from_name(li.MODAL_APP, li.MODAL_PREDICTOR)()
    vlm = await predictor.predict.remote.aio(
        image_bytes_list=image_bytes_list, chat_text=chat_text, metadata_text=metadata_text
    )
    vlm_ms = (time.perf_counter() - t0) * 1000

    constraints = parsed_to_constraints(vlm.get("parsed") or {})

    # 2) synthetic case (NO ground_truth) -> planner + live Neo4j retrieval.
    case = {
        "case_id": "freeform",
        "inputs": {
            "chat_history": [{"role": "Inspector", "text": chat_text}],
            "images": [],                       # use_images=False; retrieval is symbolic
            "project_context": {"model_code": "AP"},
        },
    }
    eval_trace, pipeline_trace = await run_pipeline_case(
        case=case,
        condition_overrides={"use_images": False},
        constraints_model="lora",
        retrieval_backend=backend,
        llm=None,
        run_id="freeform",
        image_dir="",
        engine=engine,
        image_parser=None,
        lora_extractor=None,
        precomputed_constraints={"freeform": constraints},
    )

    # 3) read the trace: fingerprint level, decision, pool, ranked shortlist.
    plan, _rr = _executed_plan(pipeline_trace)
    fp_level = (plan.params.get("fingerprint_level_requested") if plan else None) or "attribute_only"
    strategy = plan.strategy if plan else "fallback"

    cands = eval_trace.interpreter_output.candidates or []
    shortlist = [
        {"guid": c.guid, "name": c.name, "storey": c.storey, "type": c.element_type}
        for c in cands
    ]
    candidate_guids = [c["guid"] for c in shortlist if c["guid"]]

    conf = float(constraints.confidence or 0.0)
    committable = fp_level in COMMIT_LEVELS
    decision = "ANSWER" if (conf >= TAU and committable and candidate_guids) else "DEFER"
    if not candidate_guids:
        reason = "no candidates retrieved"
    elif conf < TAU:
        reason = f"confidence {conf:.2f} < τ {TAU}"
    elif not committable:
        reason = f"fingerprint level '{fp_level}' not discriminating (no slot/relation lock)"
    else:
        reason = f"confidence {conf:.2f} ≥ τ {TAU} and '{fp_level}' is discriminating"

    # 4) 3D scaffold: predicted storey -> GLB; highlight top-1 (ANSWER) or the pool (DEFER).
    storey = constraints.storey_name
    glb = build_storey_glb_map().get(storey or "")
    top1_guid = candidate_guids[0] if candidate_guids else None

    total_ms = (time.perf_counter() - t0) * 1000
    return {
        "mode": "freeform",
        "live": True,
        "valid_json": vlm.get("valid_json"),
        "vlm_output": vlm.get("parsed") or {},
        "constraints": _constraints_payload(constraints),
        "fingerprint_level": fp_level,
        "strategy": strategy,
        "decision": decision,
        "decision_reason": reason,
        "tau": TAU,
        "confidence": round(conf, 2),
        "slot_rerank_run": False,          # surfaced as a hint in the UI
        "floorplan_present": bool(floorplan_present),
        "waterfall": _waterfall(pipeline_trace, eval_trace.initial_pool_size,
                                eval_trace.final_pool_size),
        "pool_size": int(eval_trace.final_pool_size or len(candidate_guids)),
        "shortlist": shortlist,
        "candidate_guids": candidate_guids,
        "top1_guid": top1_guid,
        "storey": storey,
        "glb": glb,
        "timings_ms": {
            "vlm": round(vlm_ms),
            "extraction": round(pipeline_trace.constraints_extraction_ms),
            "planning": round(pipeline_trace.query_planning_ms),
            "retrieval": round(pipeline_trace.retrieval_ms),
            "total": round(total_ms),
        },
    }
