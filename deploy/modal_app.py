"""Modal deployment of the AEC Interpreter live-grounding backend.

Serves the SAME FastAPI app the local `uvicorn` build serves (src/aec_interpreter/service/app.py)
as a public HTTPS endpoint, so the static GitHub Pages demo can POST to it cross-origin:

    GitHub Pages  https://hychia88.github.io/aec-interpreter/demo.html   (static: HTML + GLBs)
        │  fetch POST  →  https://<ws>--aec-demo-fastapi-app.modal.run/api/ground_freeform
        ▼
    THIS Modal web app  (@modal.asgi_app, warm container)
        ├─ startup: parse IFC (Volume) + connect Neo4j Aura (Secret) + build rerank context
        ├─ calls the deployed VLM app (mscd-vlm-lora3-inference) — Modal→Modal, same workspace
        └─ returns small JSON; the browser loads the heavy GLBs from Pages

Deploy:  modal deploy deploy/modal_app.py        (see deploy/README.md for the full runbook)
Prereqs: (1) Neo4j Aura Free built via scripts/graph_build 01->02 against the Aura bolt URI,
         (2) Modal Secret `aec-neo4j-aura` = {NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD},
         (3) Modal Volume `aec-assets` populated by deploy/stage_assets.py + `modal volume put`.
"""
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent.parent
APP_NAME = "aec-demo"

# Big gitignored / irrelevant trees are NOT baked into the image (assets ride a Volume instead).
_IGNORE = [
    ".git", ".git/**", ".venv", ".venv/**", "**/__pycache__", "**/*.pyc",
    "node_modules", "**/node_modules/**", "models", "models/**",
    "data/ifc_models/**", "data/datasets/**", "output/**", "paper/**",
    "site/assets/3d/*.glb",          # GLBs are served by GitHub Pages, not Modal
    "site/assets/video/**", "site/assets/pdfs/**", "site/assets/portfolio/**",
]

# Runtime deps for the SERVICE path (no GPU here — the VLM runs on its own GPU app).
# opencv-python-headless avoids needing a GL stack for the slot detector.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgomp1")
    .pip_install(
        "pydantic>=2.0", "pyyaml>=6.0", "python-dotenv>=1.0", "numpy>=1.24,<2.0",
        "jsonschema>=4.0.0",
        "pillow>=10.0.0",
        "ifcopenshell>=0.7", "py2neo>=2021.2",
        "transformers>=4.30.0", "torch>=2.0.0", "opencv-python-headless>=4.8.0",
        "langchain-core>=0.1.0", "networkx>=3.0",
        "fastapi>=0.110", "uvicorn[standard]>=0.29", "python-multipart>=0.0.9",
        "modal>=1.5",
    )
    # Asset locations on the mounted Volume + the allowed browser origin. These env vars are
    # read by the env-overridable path constants (eval/live_runner.py, live_infer.py,
    # slot_detector_cv.py) and the service CORS middleware.
    .env({
        "AEC_IFC_PATH": "/assets/ifc/AdvancedProject.ifc",
        "AEC_DATA_ROOT": "/assets/data_curation",
        "AEC_SYNTH_DATASET": "/assets/data_curation/datasets/synth_v0.5_ap",
        "ALLOWED_ORIGINS": "https://hychia88.github.io,http://localhost:8000,http://127.0.0.1:8000",
    })
    # Repo code + committed small data (references, test_sets, traces, cases.json) at /root/aec.
    .add_local_dir(str(REPO), "/root/aec", ignore=_IGNORE)
)

app = modal.App(APP_NAME)
assets = modal.Volume.from_name("aec-assets", create_if_missing=True)
neo4j_secret = modal.Secret.from_name("aec-neo4j-aura")   # NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD


@app.function(
    image=image,
    volumes={"/assets": assets},
    secrets=[neo4j_secret],
    # Scale to zero: pay ~nothing when idle. The first request after a quiet period
    # cold-starts (~30-60s: re-parse IFC + reconnect Aura); scaledown_window keeps the
    # container warm between requests during an active demo session so it doesn't re-parse
    # on every call. Bump min_containers back to 1 if you want a permanently warm endpoint.
    min_containers=0,
    scaledown_window=300,    # stay warm 5 min after the last request, then scale to zero
    timeout=900,             # cover the VLM A100 cold start (~1-2 min) per request
    memory=8192,
    cpu=2.0,
)
@modal.concurrent(max_inputs=8)
@modal.asgi_app()
def fastapi_app():
    """Return the shared FastAPI app; its lifespan warms engine + Neo4j + rerank context."""
    import sys

    sys.path.insert(0, "/root/aec/src")
    sys.path.insert(0, "/root/aec/eval")
    from aec_interpreter.service.app import app as fastapi   # noqa: E402

    return fastapi
