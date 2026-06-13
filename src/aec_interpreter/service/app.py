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

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "eval"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

SITE = REPO_ROOT / "site"
TAU = 0.40

# Lazy/once-loaded heavy state (Neo4j + parsed IFC engine + held-out cases).
_STATE: dict = {}


def _load_state():
    """Build engine+backend once, load held-out cases + the demo manifest."""
    import json
    from live_runner import build_engine_backend, CASES, _load_jsonl

    if "engine" in _STATE:
        return _STATE
    engine, backend = build_engine_backend("p0_union_p1")
    cases = {c["case_id"]: c for c in _load_jsonl(CASES)}
    manifest_path = SITE / "assets" / "3d" / "cases.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    _STATE.update(engine=engine, backend=backend, cases=cases,
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

    imgs = li._case_images(case, li.DEFAULT_DATA_ROOT)
    vlm = await li.call_modal_vlm(imgs, li._chat_text(case), li._metadata_text(case))
    constraints = li.parsed_to_constraints(vlm.get("parsed") or {})

    row = await li.run_case_live(case, constraints, st["engine"], st["backend"])
    rank, gt, shortlist = li._rank(row)
    conf = float(constraints.confidence)
    decision = "ANSWER" if conf >= TAU else "DEFER"
    top1 = shortlist[0] if shortlist else None

    return {
        "case_id": req.case_id,
        "live": True,
        "valid_json": vlm.get("valid_json"),
        "constraints": {
            "storey_name": constraints.storey_name,
            "ifc_class": constraints.ifc_class,
            "position_context": constraints.position_context,
            "n_relations": len(constraints.spatial_relations),
        },
        "confidence": round(conf, 2),
        "tau": TAU,
        "decision": decision,
        "top1_guid": top1,
        "rank": rank,
        "pool_size": row.get("final_pool_size"),
        "shortlist": shortlist[:10],
        "gt_guid": gt,
        "correct": bool(rank == 1),
        # viewer scaffold reused from the precomputed manifest (storey GLB + look-alikes)
        "glb": scaffold.get("glb"),
        "storey": scaffold.get("storey"),
        "confusable_guids": scaffold.get("confusable_guids", []),
        "gt_slot": scaffold.get("gt_slot"),
    }


# ── static site (served same-origin so the browser can POST without CORS) ──────
@app.get("/")
def index():
    return FileResponse(SITE / "demo.html")


app.mount("/", StaticFiles(directory=str(SITE)), name="site")
