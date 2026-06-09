# Graph build — IFC → Neo4j (the `--live` prerequisite)

Brings the AP IFC model into Neo4j so the live pipeline (`run_benchmark.py --live`)
can do topology retrieval. Plain Neo4j — no APOC/GDS.

> **Status:** scaffolded & path-corrected, **not yet run end-to-end** (Docker Desktop
> WSL integration was off in the dev env). This is the runbook to execute once Neo4j is up.

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

## Verify
```bash
# expect ~1666 IFCElement nodes for AP (matches the frozen trace initial pool)
# in the Neo4j browser (http://localhost:7474):
#   MATCH (e:IFCElement) RETURN count(e);
#   MATCH ()-[r]->() RETURN type(r), count(*) ORDER BY count(*) DESC;
```

## Then
`run_benchmark.py --live` (once wired) should reproduce the frozen G8 numbers within
noise — that closes the publish gate and lets `mscd_demo` be retired.

## Assets (gitignored — see docs/DATA_INVENTORY.md)
- `data/ifc_models/AdvancedProject.ifc` (43M)
- `data/references/element_index.jsonl` (4M)
