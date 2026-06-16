# AEC Interpreter

Neuro-symbolic interpreter middleware that grounds unstructured on-site evidence
(site photo + natural-language note + floorplan) to the correct **IFC element GUID**
in a building's BIM model.

> **System-proving-first / cold-start from raw BIM.** From a *raw BIM model alone* —
> zero real on-site labels at day-1 — the system answers *"where is this element?"*
> (image + NL → IFC GUID), delivers immediate human-triage value, and is **designed to
> improve as real on-site data flows in**.

**Pipeline:** fine-tuned VLM extracts typed spatial constraints → JSON contract →
deterministic Cypher templates over an enriched Neo4j IFC graph → Graph-RAG reranked
GUID pool, with a calibrated answer/defer gate.

📄 **[Paper (PDF)](site/assets/pdfs/paper.pdf)** · 🌐 **[Project page](site/index.html)** · 🎬 **[Demo video](site/assets/video/MSCD_demo_web.mp4)** · 📒 **[Results ledger](docs/results_ledger.md)**

> This is the clean development repo for the post-thesis **enhancement + paper phase**.
> The original thesis-submission code is frozen in `~/projects/cmu/master_thesis/`
> (3 separate components, read-only) — see [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the
> provenance + migration map.

---

## Headline results (AP held-out, n=60, `p0_union_p1` planner)

| Diagnostic / system | GT-in-pool | Top-1 | Top-10 | MRR@10 |
|---|---:|---:|---:|---:|
| Zero-shot Gemini (baseline) | 95.0% | 1.7% | 18.3% | 0.056 |
| Fine-tuned VLM G8 (realized end-to-end) | 100% | 6.7% | 30.0% | 0.110 |
| + realized position-slot specialist (n=35 fillers) | 100% | **58.9%** | 67.1% | — |
| + realized slot, oracle coarse (upper bound) | 100% | 67.6% | 80.9% | — |
| **Type-conditional spatial-address ceiling** | 100% | **78.5%** | 98.1% | 0.854 |

Three load-bearing findings (one per RQ):

- **Architecture is sound, perception is the bottleneck.** Under perfect extraction the
  symbolic layer keeps the correct element in **100%** of cases and compresses the candidate
  pool from a median **46 → 1**. The ceiling is bound by neural extraction quality, not graph logic.
- **The address is a *soft prior*, not a hard filter.** Hard-filtering on a noisy field deletes
  the answer; routing on a **calibrated** confidence (AUROC 0.80) recovers the gain and lets the
  system **abstain** — the answered subset reaches **73.4%**.
- **Discrimination saturates at one hop.** Deeper relations are more unique but less recoverable
  from a flat image, so the confusable set shrinks **13 → ~8** at depth-1 and then plateaus.
  Compile relations into the node; don't chase deep chains.

Every number is provenance-tracked in [`docs/results_ledger.md`](docs/results_ledger.md).

---

## Current implementation

```text
site photo + natural-language note + floorplan
  → VLM constraint extraction (Qwen2.5-VL + LoRA, G8)
  → typed Constraints JSON  {value, confidence, source} per field
  → query planner (fingerprint ladder L0–L7, priorities P0–P8)
  → Neo4j Cypher retrieval (enriched IFC graph)
  → Graph-RAG rerank + calibrated answer/defer gate
  → ranked IFC GUID pool (Top-1 answer, or DEFER + candidate pool)
```

### 1. Neural layer — constraint extraction
- Runtime extractor: [`src/aec_interpreter/neurosym/constraints_extractor_lora.py`](src/aec_interpreter/neurosym/constraints_extractor_lora.py)
- Prompt-only fallback: [`src/aec_interpreter/neurosym/constraints_extractor_prompt_only.py`](src/aec_interpreter/neurosym/constraints_extractor_prompt_only.py)
- Typed contract: [`src/aec_interpreter/neurosym/types.py`](src/aec_interpreter/neurosym/types.py) — `Constraints` carries
  `storey_name, ifc_class, space_name, target_name_keyword, target_width_mm, target_height_mm,
  position_context, spatial_relations[]`. The per-field `{value, confidence, source}` triple is
  live for `position_context` + `size_band` today; generalizing it to every field is **P1**.
- Base model: `Qwen2.5-VL-7B + LoRA` (G-series; canonical adapter **G8 PosCtx+Dim**).
- Prompts: [`prompts/constraints_extraction.yaml`](prompts/constraints_extraction.yaml), [`prompts/system_prompt.yaml`](prompts/system_prompt.yaml)

### 2. Symbolic layer — planner + retrieval
- Planner (priority rules P0–P8, fingerprint ladder): [`src/aec_interpreter/neurosym/constraints_to_query.py`](src/aec_interpreter/neurosym/constraints_to_query.py)
- Retrieval backend (best setting `p0_union_p1`): [`src/aec_interpreter/neurosym/retrieval_backend.py`](src/aec_interpreter/neurosym/retrieval_backend.py)
  — runs spatial retrieval first, keeps the `storey + type` pool as a recall safety net.
- IFC engine (graph build + Cypher, 1530 L): [`src/aec_interpreter/ifc_engine.py`](src/aec_interpreter/ifc_engine.py)
- Schema validation / value→graph alignment: [`src/aec_interpreter/schema/`](src/aec_interpreter/schema/) (`validators.py`, `mapping.py`, `schema_registry.py`)
- Retrieval backend is **Neo4j**; queries are deterministic templates (no Text-to-Cypher).

### 3. Rerank + routing
- Graph-RAG reranker: [`src/aec_interpreter/neurosym/graph_rag_rerank.py`](src/aec_interpreter/neurosym/graph_rag_rerank.py) (AP variant: `graph_rag_rerank_ap.py`)
  — **caveat:** helpful only on coarse / P1-only pools; on already topology-filtered pools it can *degrade* Top-1.
- Deterministic visual specialists: [`src/aec_interpreter/visual/`](src/aec_interpreter/visual/) (CLIP aligner, image parser) +
  `neurosym/floorplan_counter.py` (OpenCV slot/count), `neurosym/cluster_classifier.py` (ResNet size band).
- Calibrated routing harness (offline): `eval/calibrate_rerank.py`, `eval/calibration_diag.py`, `eval/field_contract.py`.

### 4. Service, handoff, datagen
- Pipeline as a callable + FastAPI app: [`src/aec_interpreter/service/app.py`](src/aec_interpreter/service/app.py), [`src/aec_interpreter/pipeline_base.py`](src/aec_interpreter/pipeline_base.py)
- BCF triage handoff (RQ2 deliverable): [`src/aec_interpreter/handoff/`](src/aec_interpreter/handoff/) (`bcf_lite.py`, `bcf_zip.py`, `trace.py`)
- Synthetic-data generation (zero real labels): [`src/aec_interpreter/datagen/`](src/aec_interpreter/datagen/) — wraps the Blender/Bonsai render tool.

### 5. Evaluation harness
- One entrypoint, bootstrap CIs, reads a declarative registry: [`eval/run_benchmark.py`](eval/run_benchmark.py) + [`eval/experiments.yaml`](eval/experiments.yaml)
- Oracle / ceiling diagnostics: `eval/spatial_address_ceiling.py`, `eval/fingerprint_ceiling.py`, `eval/rerank_prize.py`, `eval/oracle/`
- Specialist harnesses: `eval/slot_extractor_m1.py`, `eval/wall_extractor_m1.py`, `eval/slot_detector_cv.py`, `eval/wall_detector_cv.py`
- Live pipeline runners: `eval/live_infer.py`, `eval/live_runner.py`, `eval/live_rerank.py`
- Figure generators (paper): `eval/fig_*.py`; demo dashboards: `eval/build_demo.py`, `eval/build_3d_demo.py`
- Metric definitions + scorer conventions: [`docs/results_ledger.md`](docs/results_ledger.md)

---

## Repo map

| Path | What it holds |
|---|---|
| [`src/aec_interpreter/neurosym/`](src/aec_interpreter/neurosym/) | Core pipeline: VLM extractor → typed constraints → Cypher planner → Neo4j retrieval → reranker |
| [`src/aec_interpreter/ifc_engine.py`](src/aec_interpreter/ifc_engine.py) | IFC → Neo4j graph build + symbolic Cypher engine (neurosym depends on it) |
| [`src/aec_interpreter/visual/`](src/aec_interpreter/visual/) | Deterministic visual specialists (CLIP aligner, image parser) |
| [`src/aec_interpreter/schema/`](src/aec_interpreter/schema/) | Constraint-contract validation + value→schema alignment (P1 target) |
| [`src/aec_interpreter/service/`](src/aec_interpreter/service/) | Pipeline as a callable + FastAPI; shared by demo **and** eval |
| [`src/aec_interpreter/handoff/`](src/aec_interpreter/handoff/) | BCF issue-handoff / triage output contract |
| [`src/aec_interpreter/datagen/`](src/aec_interpreter/datagen/) | Synthetic-data generation (Blender/Bonsai render wrapper) |
| [`src/aec_interpreter/common/`](src/aec_interpreter/common/) | Shared utils: config, guid, evaluation, trace I/O, MCP |
| [`eval/`](eval/) | `run_benchmark.py` + `experiments.yaml`, oracle ceilings, specialist harnesses, figure generators |
| [`data/test_sets/`](data/test_sets/) | Benchmark sets **in git** (AP held-out 60-case e2e, leakage exclusions) |
| [`data/references/`](data/references/) | Committed reference data (element / position / wall-fingerprint indices) |
| `data/datasets/`, `data/ifc_models/`, `models/`, `output/` | Large artifacts — **gitignored** (paths in [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md)) |
| [`prompts/`](prompts/), [`schemas/`](schemas/) | Extraction/system prompts; JSON contract + CORENET-X min schema |
| [`scripts/graph_build/`](scripts/graph_build/) | IFC → Neo4j build (`01_export` → `02_add_topology_edges`) — `--live` prerequisite |
| [`deploy/`](deploy/) | Modal app (`modal_app.py`) + asset staging for the live VLM endpoint |
| [`site/`](site/) | Static project page + interactive 3D demo |
| [`docs/`](docs/) | ROADMAP · REPO_MAP · DATA_INVENTORY · results_ledger · `thesis/` writeups |

---

## System architecture

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OFFLINE: IFC → Neo4j graph   (ifc_engine.py · scripts/graph_build/)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 IFC file → Nodes (IFCElement, IFCStorey, IFCSpace)
   .guid .ifc_type .storey .material .object_type
   .width_mm .height_mm  .wall_position_index .wall_child_total
 Edges:
   -[:CONTAINS]->                  storey/space containment
   -[:FILLS]->                     Door/Window → host Wall
   -[:NEXT_TO {wall_guid,pos}]->   consecutive fillers on a wall
   -[:CONNECTS_TO {conn_type}]->   wall T/L/X junctions
   -[:ADJACENT_TO {distance_mm}]-> centroid distance 100–1500mm

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OFFLINE: training labels   (src/aec_interpreter/datagen/)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 raw IFC → skeleton mining → Blender hard-negative renders
   → Gemini scenario text → LLM-as-judge filter
   → Constraints-JSON label per case (zero real labels)
   → LoRA fine-tune (G8, Qwen2.5-VL-7B, r=32)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ONLINE: inference (per query)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 query: text + site_photo(s) + floorplan
   │
   ▼  NEURO LAYER — LoRA VLM (G8)        constraints_extractor_lora.py
        Constraints JSON: ifc_class, storey_name, target_w/h_mm,
        position_context, spatial_relations[{predicate, object_type,
        object_subtype, direction, connection_degree, distance_mm,
        confidence}]   ← each field {value, confidence, source}
   │
   ▼  QUERY PLANNER                       constraints_to_query.py
        fingerprint_level: exact_slot ▸ relation_fingerprint ▸
                           topology_only ▸ attribute_only
        P0 spatial_triplet (FILLS/NEXT_TO/CONNECTS_TO/ADJACENT_TO)
        P1 space+type · P2 name_keyword · P4 storey+type · P8 fallback
   │  QueryPlan
   ▼  SYMBOLIC LAYER — Neo4j Cypher       retrieval_backend.py
        single-hop / multi-anchor traversal + relaxation ladder
        (drop exact_slot → drop fingerprint → drop storey → P4)
   │  p0_union_p1:  P0 pool  ∪  storey+type safety net
   ▼  GRAPH-RAG RERANK + ROUTE            graph_rag_rerank.py
        per-candidate graph context → Gemini reorder
        calibrated confidence → ANSWER (commit GUID) | DEFER (pool)
   │
   ▼  ranked IFC GUID pool → Top-1 answer
```

> **Graph-RAG caveat:** only helps on P1-only / coarse pools; on already topology-filtered
> pools it *degrades* Top-1 — see [`docs/thesis/rq1_spatial_address.md`](docs/thesis/rq1_spatial_address.md).

---

## Quick start

All offline steps run with **no Neo4j, no GPU, no model API** — they replay frozen G8 traces
+ committed reference data, so the oracle diagnostics are leakage-proof.

### 1. Environment

```bash
# the repo .venv is already populated; use it directly
.venv/bin/python -m pytest -q          # 28 tests, all green
# fresh clone instead:
uv venv && uv pip install -e ".[dev]"
```

### 2. Reproduce the numbers (offline)

```bash
.venv/bin/python eval/run_benchmark.py --variant g8_posctx_dim   # thesis parity: Top-10 30.0, MRR 0.110
.venv/bin/python eval/fingerprint_ceiling.py        # attribute-layer |C| 46 → 13
.venv/bin/python eval/rerank_prize.py               # soft-rerank prize: oracle Top-1 → 61.7
.venv/bin/python eval/spatial_address_ceiling.py    # type-conditional address oracle: Top-1 → 78.5
.venv/bin/python eval/slot_extractor_m1.py          # position-slot harness: floor 2.4 → ceiling 91.0 (+figure)
```

### 3. Build the demo dashboards

```bash
.venv/bin/python eval/build_demo.py                 # one filler + one wall card → output/demo/case_*.png
.venv/bin/python eval/build_demo.py AP_SK_022       # any held-out case id(s)
explorer.exe "$(wslpath -w output/demo)"            # WSL: open the folder in Windows
```

Panels are tagged by epistemic status — `REAL` (inputs, GT address, |C| collapse, Top-1),
`ORACLE` (perfect-extraction "predicted address", not learned yet), `REALIZED` (G8's actual
extraction), `PENDING` (tiles reserved for the P2 learned extractor).

### 4. Live pipeline (real VLM + graph)

Runs the actual end-to-end path: site photo → Modal GPU VLM → constraints → live Neo4j
retrieval → grounded GUID. Needs Docker + Modal.

```bash
docker compose up -d                                   # Neo4j on bolt://localhost:7687
# one-time graph build (steps 01 → 02 only): scripts/graph_build/README.md
modal token new                                        # one-time Modal auth
.venv/bin/python eval/live_infer.py --case AP_SK_108   # one held-out case, live

# browser demo (same-origin, no CORS):
.venv/bin/uvicorn aec_interpreter.service.app:app --port 8000 --app-dir src
#   open http://localhost:8000/  → pick a case → "⚡ Run live inference"
```

The live VLM runs on a deployed Modal A100 (`mscd-vlm-lora3-inference`, canonical G8 adapter);
first call cold-starts ~1–2 min. The live route is currently **pure-VLM** — the OpenCV slot
specialist + soft-rerank (the 58.9% realized path) is the next enhancement, so live slot
predictions can be wrong; the system surfaces its confidence and ANSWER/DEFER.

### 5. Regenerate reference data (optional — needs the IFC model)

`data/references/*.jsonl` are committed, so nothing above needs this. To regenerate, you need
`data/ifc_models/AdvancedProject.ifc` (gitignored) + `ifcopenshell`:
`eval/reconstruct_position_index.py`, `eval/wall_fingerprint.py`, `eval/depth_saturation.py`,
`eval/fingerprint_reliability.py`.

---

## Conventions

- **One eval entrypoint** (`eval/run_benchmark.py`); experiments declared in
  `eval/experiments.yaml`, not scattered scripts.
- **Every reported number** lands in [`docs/results_ledger.md`](docs/results_ledger.md) with
  run id + commit, with bootstrap 95% CIs (n is small).
- Per-phase `protocol.md` is committed **before** running that phase's experiments.
- Large artifacts (`models/`, `data/datasets/`, `data/ifc_models/`, `output/`) are gitignored —
  canonical local paths in [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md).
