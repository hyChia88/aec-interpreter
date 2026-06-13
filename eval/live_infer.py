"""Live end-to-end inference — the real system on a fresh case, no precomputed traces.

Pipeline:  site photo + floorplan + note
   -> Modal GPU VLM (deployed G8 adapter, mscd-vlm-lora3-inference / G8ModelPredictor)
   -> Constraints
   -> QueryPlanner -> live Neo4j RetrievalBackend -> ranked GUID shortlist
   -> ANSWER / DEFER.

This is the live counterpart of run_benchmark.py --live: that one replays the FROZEN
extraction against the live graph (retrieval-only); THIS one runs the VLM live on Modal, so
nothing is precomputed. Use it to demo the actual system and to sanity-check that live
extraction matches the frozen G8 constraints.

Prereqs:
  - Neo4j up (docker compose up -d) + graph built (scripts/graph_build 01->02).
  - Modal authed (modal token new) + app deployed (mscd-vlm-lora3-inference).
  - Image set present (default: master_thesis/data_curation, the synth_v0.5_ap photos/floorplans).

Run:  .venv/bin/python eval/live_infer.py --case AP_SK_022
      .venv/bin/python eval/live_infer.py --n 3          # first 3 held-out cases
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from live_runner import CASES, FROZEN, build_engine_backend, run_case_live, _load_jsonl

# Image set (gitignored, lives in the frozen data_curation tree). Override with --data-root.
DEFAULT_DATA_ROOT = Path("/home/hychi/projects/cmu/master_thesis/data_curation")
MODAL_APP = "mscd-vlm-lora3-inference"
MODAL_PREDICTOR = "G8ModelPredictor"   # canonical G8 adapter (volume /checkpoints/...g8.../best)


# ── case -> Modal inputs ──────────────────────────────────────────────────────
def _case_images(case: dict, data_root: Path) -> list[Path]:
    """Resolve [site photo, floorplan] absolute paths from a case's relative refs."""
    inp = case.get("inputs", {})
    rels = list(inp.get("images") or [])
    fp = inp.get("floorplan_patch")
    if fp:
        rels.append(fp)
    return [data_root / r for r in rels]


def _chat_text(case: dict) -> str:
    inp = case.get("inputs", {})
    msgs = inp.get("chat_history") or []
    joined = "\n".join((m.get("text") or "").strip() for m in msgs if m.get("text"))
    return joined or (case.get("query_text") or "")


def _metadata_text(case: dict) -> str:
    ctx = (case.get("inputs", {}).get("project_context") or {})
    bits = [f"[IFC Model] {ctx.get('model_code', 'AP')}"]
    for k in ("phase", "task_status", "location"):
        if ctx.get(k):
            bits.append(f"{k}: {ctx[k]}")
    return " ".join(bits)


# ── Modal VLM call ────────────────────────────────────────────────────────────
async def call_modal_vlm(image_paths: list[Path], chat_text: str, metadata_text: str) -> dict:
    """Invoke the deployed G8 predictor on Modal GPU. Returns {raw_output, parsed, valid_json}."""
    import modal

    image_bytes = [p.read_bytes() for p in image_paths if p.exists()]
    missing = [str(p) for p in image_paths if not p.exists()]
    if missing:
        print(f"  ⚠️  missing image(s): {missing}")
    predictor = modal.Cls.from_name(MODAL_APP, MODAL_PREDICTOR)()
    return await predictor.predict.remote.aio(
        image_bytes_list=image_bytes, chat_text=chat_text, metadata_text=metadata_text
    )


# ── parsed JSON -> Constraints (mirrors LoRAConstraintsExtractor post-parse) ──
def parsed_to_constraints(parsed: dict):
    from aec_interpreter.neurosym.types import Constraints, SpatialTriplet

    if not parsed:
        return Constraints(confidence=0.0, source="modal_parse_failed")
    sr_raw = parsed.get("spatial_relations") or []
    rels = []
    for r in sr_raw:
        if not isinstance(r, dict):
            continue
        d = r.get("direction")
        d = d.lower().strip() if isinstance(d, str) else None
        if d not in {"left", "right"}:
            d = None
        rels.append(SpatialTriplet(
            subject_type=parsed.get("ifc_class", ""),
            predicate=str(r.get("predicate", "ADJACENT_TO")).upper(),
            object_type=r.get("object_type", ""),
            object_subtype=r.get("object_subtype"),
            direction=d,
            object_material=r.get("object_material"),
            confidence=r.get("confidence", 0.0),
        ))
    conf = max((r.confidence for r in rels), default=0.85)
    return Constraints(
        storey_name=parsed.get("storey_name"),
        ifc_class=parsed.get("ifc_class"),
        space_name=parsed.get("space_name"),
        target_name_keyword=parsed.get("target_name_keyword"),
        position_context=parsed.get("position_context"),
        spatial_relations=rels,
        confidence=conf,
        source="modal_g8_live",
    )


def _rank(row: dict):
    gt = ((row.get("scenario") or {}).get("ground_truth") or {}).get("target_guid")
    sl = [c.get("guid") for c in (row.get("interpreter_output") or {}).get("candidates") or []]
    return (sl.index(gt) + 1 if gt in sl else None), gt, sl


async def _run(case_ids: list[str], data_root: Path, p0_strategy: str, defer_tau: float):
    cases = {c["case_id"]: c for c in _load_jsonl(CASES)}
    frozen = {r["scenario_id"]: (r.get("internals") or {}).get("constraints")
              for r in _load_jsonl(FROZEN)}
    engine, backend = build_engine_backend(p0_strategy)

    for cid in case_ids:
        case = cases.get(cid)
        if not case:
            print(f"\n[{cid}] not in held-out set — skipping"); continue
        imgs = _case_images(case, data_root)
        print(f"\n{'='*70}\n[{cid}]  images={[p.name for p in imgs]}")
        print(f"  note: {_chat_text(case)[:120]!r}")
        print("  → calling Modal G8 VLM (A100; cold start ~1-2 min)…", flush=True)
        vlm = await call_modal_vlm(imgs, _chat_text(case), _metadata_text(case))
        print(f"  VLM valid_json={vlm.get('valid_json')}  raw={vlm.get('raw_output','')[:160]!r}")
        constraints = parsed_to_constraints(vlm.get("parsed") or {})
        print(f"  live constraints: storey={constraints.storey_name!r} class={constraints.ifc_class!r} "
              f"pos={constraints.position_context!r} rels={len(constraints.spatial_relations)} conf={constraints.confidence:.2f}")

        row = await run_case_live(case, constraints, engine, backend)
        rank, gt, sl = _rank(row)
        answer = (constraints.confidence >= defer_tau)
        verdict = "ANSWER" if answer else f"DEFER (conf {constraints.confidence:.2f} < τ {defer_tau})"
        print(f"  GT={gt}")
        print(f"  rank={rank}  pool={row.get('final_pool_size')}  →  {verdict}")
        print(f"  top-5: {sl[:5]}")
        # sanity vs frozen extraction
        fc = frozen.get(cid) or {}
        print(f"  [frozen G8 extraction] storey={fc.get('storey_name')!r} class={fc.get('ifc_class')!r} "
              f"pos={fc.get('position_context')!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--case", action="append", help="held-out case id (repeatable)")
    g.add_argument("--n", type=int, help="run the first N held-out cases")
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT, help="image set root")
    ap.add_argument("--p0-strategy", default="p0_union_p1")
    ap.add_argument("--defer-tau", type=float, default=0.40, help="confidence threshold for ANSWER vs DEFER")
    a = ap.parse_args()

    if a.case:
        ids = a.case
    elif a.n:
        ids = [c["case_id"] for c in _load_jsonl(CASES)[: a.n]]
    else:
        ids = ["AP_SK_022"]
    asyncio.run(_run(ids, a.data_root, a.p0_strategy, a.defer_tau))


if __name__ == "__main__":
    main()
