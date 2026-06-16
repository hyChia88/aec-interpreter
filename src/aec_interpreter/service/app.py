"""FastAPI service for the live grounding demo.

Wires the browser demo (site/demo.html) to the REAL pipeline: a held-out case ->
Modal A100 VLM (deployed G8 adapter) -> Constraints -> live Neo4j retrieve -> ranked
GUID + ANSWER/DEFER. The same engine/backend the CLI uses (eval/live_runner), loaded
once at startup.

Run:
    docker compose up -d                                  # Neo4j
    # graph built once: scripts/graph_build 01->02
    modal token new                                       # once
    .venv/bin/uvicorn aec_interpreter.service.app:app --reload --port 8000
    open http://localhost:8000/                           # the demo, served same-origin

Endpoints:
    GET  /                  -> site/demo.html
    GET  /health            -> {status, neo4j_elements, modal_app}
    GET  /api/cases         -> the cases.json manifest (viewer scaffold)
    POST /api/ground {case_id} -> live result for that held-out case

NOTE: this runs the pure-VLM (G8) extraction. The OpenCV position-slot specialist +
calibrated soft-rerank (the 67.6% realized path) is not yet merged into the live route
— that is the documented next enhancement (see docs/STATUS.md).
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "eval"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

SITE = REPO_ROOT / "site"
TAU = 0.40

# Lazy/once-loaded heavy state (Neo4j + parsed IFC engine + held-out cases).
_STATE: dict = {}


def _load_state():
    """Build engine+backend + slot-rerank context once; load held-out cases + manifest."""
    import json
    from live_runner import build_engine_backend, CASES, _load_jsonl
    from live_rerank import build_rerank_context

    if "engine" in _STATE:
        return _STATE
    engine, backend = build_engine_backend("p0_union_p1")
    rerank_ctx = build_rerank_context()
    cases = {c["case_id"]: c for c in _load_jsonl(CASES)}
    manifest_path = SITE / "assets" / "3d" / "cases.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    _STATE.update(engine=engine, backend=backend, rerank_ctx=rerank_ctx, cases=cases,
                  manifest={m["id"]: m for m in manifest})
    return _STATE


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the (slow) engine/Neo4j once at startup so requests are fast.
    print("[service] warming engine + Neo4j (parses the IFC once)…", flush=True)
    _load_state()
    print("[service] ready.", flush=True)
    yield


app = FastAPI(title="AEC Interpreter — live grounding", lifespan=lifespan)

# When the page is hosted on GitHub Pages (static) and the backend on Modal, the browser
# POSTs cross-origin — allow the Pages origin. ALLOWED_ORIGINS is a comma-separated env
# override; default covers the Pages site + local dev. Same-origin (local uvicorn) is
# unaffected. Multipart upload (/api/ground_freeform) needs the preflight allowed too.
_default_origins = "https://hychia88.github.io,http://localhost:8000,http://127.0.0.1:8000"
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class GroundRequest(BaseModel):
    case_id: str


@app.get("/health")
def health():
    st = _load_state()
    n = st["engine"].neo4j_conn.run("MATCH (e:IFCElement) RETURN count(e)").evaluate()
    return {"status": "ok", "neo4j_elements": n, "modal_app": "mscd-vlm-lora3-inference",
            "cases_loaded": len(st["cases"]), "manifest_cases": len(st["manifest"])}


@app.get("/api/cases")
def api_cases():
    st = _load_state()
    return JSONResponse(list(st["manifest"].values()))


@app.post("/api/ground")
async def api_ground(req: GroundRequest):
    """Run the live pipeline on a held-out case and return a viewer-ready result."""
    import live_infer as li

    st = _load_state()
    case = st["cases"].get(req.case_id)
    if not case:
        raise HTTPException(404, f"unknown case_id {req.case_id!r}")
    scaffold = st["manifest"].get(req.case_id, {})

    from live_rerank import rerank_live

    # 1) VLM (Modal GPU) → coarse prefix (storey, class) + relations.
    imgs = li._case_images(case, li.DEFAULT_DATA_ROOT)
    vlm = await li.call_modal_vlm(imgs, li._chat_text(case), li._metadata_text(case))
    constraints = li.parsed_to_constraints(vlm.get("parsed") or {})

    # 2) live Neo4j retrieval → the recall-safe candidate pool.
    row = await li.run_case_live(case, constraints, st["engine"], st["backend"])
    gt = ((row.get("scenario") or {}).get("ground_truth") or {}).get("target_guid")
    pool_guids = [c["guid"] for r in (row.get("internals") or {}).get("retrieval_results") or []
                  for c in r.get("candidates") or [] if c.get("guid")]
    pool_guids = list(dict.fromkeys(pool_guids))   # dedup, keep order

    # 3) realized neuro-symbolic rerank: OpenCV slot specialist + calibrated soft-rerank
    #    (this is the 67.6% mechanism; VLM gives storey/class, OpenCV gives the slot).
    rr = rerank_live(gt, pool_guids, constraints.storey_name, constraints.ifc_class, st["rerank_ctx"])
    ranked = rr["ranked"]
    rank = (ranked.index(gt) + 1) if gt in ranked else None

    return {
        "case_id": req.case_id,
        "live": True,
        "valid_json": vlm.get("valid_json"),
        "vlm_output": vlm.get("parsed") or {},
        "constraints": {
            "storey_name": constraints.storey_name,
            "ifc_class": constraints.ifc_class,
            "position_context": constraints.position_context,
            "position_context_confidence": constraints.position_context_confidence,
            "position_context_source": constraints.position_context_source,
            "overall_confidence": round(float(constraints.confidence or 0.0), 2),
            "spatial_relations": [
                {
                    "predicate": rel.predicate,
                    "object_type": rel.object_type,
                    "object_subtype": rel.object_subtype,
                    "direction": rel.direction,
                    "object_material": rel.object_material,
                    "confidence": round(float(rel.confidence or 0.0), 2),
                }
                for rel in constraints.spatial_relations
            ],
        },
        # realized address: OpenCV slot + temperature-calibrated confidence
        "slot": rr["slot"],
        "conf_raw": rr["conf_raw"],
        "confidence": rr["conf_cal"],          # calibrated; drives the gate
        "tau": rr["tau"],
        "decision": rr["decision"],
        "top1_guid": rr["top1_guid"],
        "rank": rank,
        "pool_size": row.get("final_pool_size") or len(pool_guids),
        "n_slot_matches": rr["n_slot_matches"],
        "shortlist": ranked[:10],
        "gt_guid": gt,
        "correct": bool(rank == 1),
        # viewer scaffold reused from the precomputed manifest (storey GLB + look-alikes)
        "glb": scaffold.get("glb"),
        "storey": scaffold.get("storey"),
        "confusable_guids": scaffold.get("confusable_guids", []),
        "gt_slot": scaffold.get("gt_slot"),
    }


@app.post("/api/ground_freeform")
async def api_ground_freeform(
    image: UploadFile = File(...),
    floorplan: Optional[UploadFile] = File(None),
    text: str = Form(""),
    metadata: str = Form(""),
):
    """Run the REAL pipeline on a FREE-INPUT photo + note (no case id, no ground truth).

    Coarse path: Modal VLM -> Constraints -> live Neo4j retrieval (confidence-weighted,
    relation-aware) -> ranked pool + fingerprint level + ANSWER/DEFER. The OpenCV ordinal
    slot-rerank is NOT run here (it needs the target's plan location); identical-sibling
    cases therefore DEFER and return the shortlist. See eval/live_freeform.py.
    """
    import live_freeform as lf

    st = _load_state()
    image_bytes = [await image.read()]
    if floorplan is not None:
        image_bytes.append(await floorplan.read())
    return await lf.run_freeform(
        image_bytes_list=image_bytes,
        chat_text=text or "",
        metadata_text=metadata or "[IFC Model] AP",
        engine=st["engine"],
        backend=st["backend"],
        floorplan_present=floorplan is not None,
    )


# ── static site (served same-origin so the browser can POST without CORS) ──────
@app.get("/")
def index():
    return FileResponse(SITE / "demo.html")


app.mount("/", StaticFiles(directory=str(SITE)), name="site")
