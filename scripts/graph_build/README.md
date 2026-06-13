# Graph build — IFC → Neo4j (the `--live` prerequisite)

Brings the AP IFC model into Neo4j so the live pipeline (`run_benchmark.py --live`)
can do topology retrieval. Plain Neo4j — no APOC/GDS.

> **Status (2026-06-12):** RUN END-TO-END. Steps 01→02 build the full enriched graph and
> `run_benchmark.py --live` reproduces the frozen G8 retrieval exactly (GT-in-pool 100%,
> Top-1 6.7, Top-5 16.7, pool median 76 / mean 118.4). Verified counts below.
>
> ⚠️ **Step 03 (`03_prepare_views.py`) is legacy and NOT needed.** It re-exports the base
> graph (clobbering step 02's edges) and then shells out to `conda run -n mscd_demo
> legacy/script/add_topology_edges.py`, which depends on the frozen `mscd_demo` repo. Its
> enrichment is redundant with the in-repo step 02. **Run 01→02 only.** (Step 03 left in
> place for the thesis base/enriched screenshot views; do not run it in the live-closeout flow.)

## Prerequisites
```bash
# 1. install deps incl. py2neo
uv pip install -e ".[dev,geom]"
# 2. start Neo4j (creds neo4j/password, bolt://localhost:7687)
docker compose up -d            # needs Docker Desktop WSL integration enabled
```

## Build steps (run from repo root)
```bash
# 1) load IFC elements / spaces / storeys into Neo4j
python scripts/graph_build/01_export_ifc_to_neo4j.py \
    --ifc data/ifc_models/AdvancedProject.ifc \
    --uri bolt://localhost:7687 --user neo4j --password password

# 2) add offline-geometry topology edges (FILLS / ADJACENT_TO / ON_TOP_OF / ...)
#    — these power the Priority-0 fingerprint that the planner relies on
python scripts/graph_build/02_add_topology_edges.py \
    --ifc data/ifc_models/AdvancedProject.ifc \
    --index data/references/element_index.jsonl \
    --uri bolt://localhost:7687 --user neo4j --password password

# 3) prepare views / indexes
python scripts/graph_build/03_prepare_views.py \
    --uri bolt://localhost:7687 --user neo4j --password password
```

## Verify (actual counts, 2026-06-12)
```
MATCH (e:IFCElement) RETURN count(e);              -> 1257   (= frozen L0 pool; the
                                                              "1666" earlier note was the
                                                              CONTAINS edge count, not nodes)
MATCH ()-[r]->() RETURN type(r), count(*) ...:
  CONNECTS_TO 1362 | CONTAINS 1257 | ADJACENT_TO 754 | NEXT_TO 526 | FILLS 389
```

## Then
```bash
python eval/run_benchmark.py --live --reference eval/fixtures/metrics/g8_posctx_dim.json
```
Reproduces the frozen G8 retrieval EXACTLY on the rerank-invariant metrics (GT-in-pool 100%,
Top-1 6.7, Top-5 16.7, pool median 76 / mean 118.4). Top-10/MRR differ by 2 cases because the
frozen Top-k included a Gemini graph-RAG rerank that needs `GOOGLE_API_KEY` (absent offline);
the live path ranks by retrieval ORDER BY only. This closes the publish gate for the graph +
retrieval layer — `mscd_demo` is reproducible in-repo and can be retired. (Engine:
`eval/live_runner.py`.)

## Assets (gitignored — see docs/DATA_INVENTORY.md)
- `data/ifc_models/AdvancedProject.ifc` (43M)
- `data/references/element_index.jsonl` (4M)
