# Online deploy — live demo on GitHub Pages + Modal + Neo4j Aura

The demo page is **static** (GitHub Pages). The live backend (VLM → constraints → graph
retrieval → rerank) runs on **Modal** as a public HTTPS endpoint the page POSTs to; the BIM
graph lives in **Neo4j Aura Free**. The heavy 3D GLBs are served by Pages — Modal only returns
small JSON.

```
GitHub Pages  demo.html + GLBs + cases.json          (static)
     │  POST  https://<ws>--aec-demo-fastapi-app.modal.run/api/ground_freeform   (CORS)
     ▼
Modal web app (deploy/modal_app.py)  ── calls ──▶  Modal VLM app  mscd-vlm-lora3-inference
     └─ Neo4j Aura  (neo4j+s://…, 1257 nodes built once)
```

What runs where: **free-input** (`/api/ground_freeform`) and **held-out live**
(`/api/ground`) both work online. Local same-origin `uvicorn` is unaffected — `API_BASE`
is empty unless the page is on `*.github.io`.

---

## One-time setup

### 1. Neo4j Aura Free
1. Create a free instance at <https://console.neo4j.io> and **download its credentials file**
   (`Neo4j-<dbid>-Created-….txt`) — it has `NEO4J_URI` (`neo4j+s://…`), `NEO4J_USERNAME`,
   `NEO4J_PASSWORD`. (For some instances the username + database are the DBID, not `neo4j` —
   that's fine, use the file's values.)
2. Build the graph into Aura from your local machine (needs the IFC + `py2neo`). Put the
   creds in the **gitignored repo-root `.env`** (the build scripts auto-load it, so the
   password never touches the command line):
   **Paste Aura's downloaded credentials file (`Neo4j-<dbid>-Created-….txt`) values verbatim**
   into the gitignored repo-root `.env` — Aura's exported names (`NEO4J_URI`, `NEO4J_USERNAME`,
   `NEO4J_PASSWORD`) match what the code reads:
   ```bash
   cat >> .env <<'EOF'
   NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
   NEO4J_USERNAME=xxxx
   NEO4J_PASSWORD=<aura-pw>
   EOF

   .venv/bin/python scripts/graph_build/01_export_ifc_to_neo4j.py --ifc data/ifc_models/AdvancedProject.ifc
   .venv/bin/python scripts/graph_build/02_add_topology_edges.py  --ifc data/ifc_models/AdvancedProject.ifc \
       --index data/references/element_index.jsonl
   ```
   ⚠️ **Use Aura's `neo4j+s://` URI as-is — do NOT switch it to `bolt+s://`.** Aura is a routed
   cluster; the routing scheme `neo4j+s://` is what reliably reaches the database (direct
   `bolt+s://` hits the entry node and gives intermittent `Database … not found`). Also note
   **`NEO4J_USERNAME` and the database name are often the DBID, not `neo4j`** — just use whatever
   the Aura file says; py2neo's default DB routing handles the rest. (`--uri/--user/--password`
   still work as explicit overrides.) Verify: `MATCH (e:IFCElement) RETURN count(e)` → **1257**.
   (Do **not** run step 03.)

### 2. Modal Secret (Aura creds — reuse your .env)
```bash
set -a; source .env; set +a
modal secret create aec-neo4j-aura \
    NEO4J_URI="$NEO4J_URI" NEO4J_USERNAME="$NEO4J_USERNAME" NEO4J_PASSWORD="$NEO4J_PASSWORD"
```
> The service reads `NEO4J_USERNAME` (or `NEO4J_USER`) and connects with the same `neo4j+s://`
> routing URI — identical to the local build.

### 3. Modal Volume (gitignored assets — IFC + held-out images)
```bash
.venv/bin/python deploy/stage_assets.py  # stages ~183 MB into deploy/_volume_stage/
modal volume create aec-assets           # MUST exist before `put` (create_if_missing only fires at deploy)
modal volume put aec-assets deploy/_volume_stage/ifc /
modal volume put aec-assets deploy/_volume_stage/data_curation /
```
Remote layout (matches the `AEC_*` env in `modal_app.py`):
```
/assets/ifc/AdvancedProject.ifc
/assets/data_curation/datasets/synth_v0.5_ap/{imgs,floorplans,floorplans_full}/…
```

### 4. VLM app
The extraction model is the already-deployed `mscd-vlm-lora3-inference` (`G8ModelPredictor`).
Confirm it's live in the same workspace: `modal app list`. No redeploy needed.

---

## Deploy the backend
```bash
modal deploy deploy/modal_app.py
```
Modal prints the web URL, e.g. `https://<ws>--aec-demo-fastapi-app.modal.run`. Smoke-test:
```bash
curl https://<ws>--aec-demo-fastapi-app.modal.run/health
# {"status":"ok","neo4j_elements":1257,...}
```

## Point the page at it + publish
1. In `site/demo.html`, set `MODAL_URL` to the deployed URL (no trailing slash).
2. Publish `site/` to GitHub Pages so `https://hychia88.github.io/aec-interpreter/demo.html`
   serves it (e.g. push `site/` to the `gh-pages` branch or your Pages source dir).
3. Open the page → **Free input** tab → upload a photo + note → **Run**. First call cold-starts
   the VLM (~1–2 min); `min_containers=1` keeps the web container warm after that.

---

## Notes / cost
- **CORS**: `modal_app.py` sets `ALLOWED_ORIGINS` to the Pages origin + localhost. Add more
  origins there (comma-separated) if you serve the page elsewhere.
- **Cost / warm behavior**: the web app defaults to **`min_containers=0` + `scaledown_window=300`**
  — scales to zero so idle cost is ~$0; pay only while serving. The first request after a quiet
  period cold-starts (~30–60 s: re-parse IFC + reconnect Aura), then stays warm 5 min between
  requests. Set `min_containers=1` for a permanently warm endpoint (bills ~24/7). The GPU cost is
  only the separate A100 VLM app, billed per call (+ its 30-min idle keepalive). Aura Free + Pages
  + Actions are $0.
- **Trim the image**: deps in `modal_app.py` are a curated runtime subset. If `modal deploy`
  surfaces a missing import, add it to the `.pip_install(...)` list.
- **Re-upload assets** after changing them:
  ```bash
  modal volume put aec-assets deploy/_volume_stage/ifc / --force
  modal volume put aec-assets deploy/_volume_stage/data_curation / --force
  ```
