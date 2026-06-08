# REPO MAP — where everything lives

> This is the **clean development repo** for the post-thesis enhancement + paper phase.
> The original thesis-submission code stays frozen in `~/projects/cmu/master_thesis/`
> (3 separate components — see "Provenance" below) and is **not** developed further.

```
aec-interpreter/
├── src/aec_interpreter/
│   ├── datagen/      synthetic data generation; wraps the Blender/Bonsai render tool
│   ├── neurosym/     VLM extraction → typed constraints → Cypher planner over Neo4j
│   ├── visual/       deterministic visual specialists (OpenCV position, ResNet size)
│   ├── schema/       value → schema alignment (to become verified schema-alignment, P1)
│   ├── service/      pipeline as a callable + FastAPI; shared by demo AND eval
│   ├── handoff/      output contract / triage handoff structures
│   └── common/       shared utils, config, types
├── eval/
│   ├── run_benchmark.py   one entrypoint; bootstrap CIs; reads experiments.yaml
│   ├── experiments.yaml   declarative experiment/group registry (replaces old track_registry)
│   └── oracle/            oracle-ceiling experiments (fingerprint ladder L0–L7)
├── demo/             thin front-end → calls src/aec_interpreter/service (deferred phase)
├── data/
│   ├── datasets/     synthetic datasets (gitignored)
│   ├── ifc_models/   raw BIM / IFC (gitignored)
│   └── test_sets/    small benchmark sets (IN git): AP held-out + new larger held-out
├── models/           LoRA adapters / checkpoints (gitignored)
├── output/           run artifacts, predictions, ledgers (gitignored)
├── prompts/          extraction / system prompts
├── schemas/          JSON schemas for the constraint contract
├── config/           runtime config
└── docs/             ROADMAP · DATA_INVENTORY · REPO_MAP · results_ledger
```

## Provenance — old repos (frozen, read-only reference)

`~/projects/cmu/master_thesis/` contains 3 components:

| Old component | What it was | Migrates into |
|---|---|---|
| `data_curation/` | synthetic data generation; `synth_v0.2…v0.5 ×(ap/bh/dxa)` | `src/aec_interpreter/datagen/` + `data/datasets/` |
| `mscd_demo/` | system + eval + training + output. Core = `src/neurosym/` (README lists 10 backend limitations). Canonical model `output/lora6_v2_ap_20260331/`. `rq2_schema/mapping.py` = deterministic copy (the place P1 schema-alignment replaces). Old web demo in `demo/`. | `src/aec_interpreter/{neurosym,visual,schema,service,handoff,common}/`, `eval/`, `demo/` |
| `ifc-bonsai-mcp/` | Blender (Bonsai/BlenderBIM) MCP plugin used to render/screenshot IFC for data synthesis. **A DATAGEN tool, not the legacy agent.** | referenced by `src/aec_interpreter/datagen/` |

The abandoned **V1 agent-as-grounding** code lives somewhere in old `mscd_demo`
(likely `src/main_mcp.py` / `mcp_servers/`, unconfirmed) — **not migrated**; cited
qualitatively only.

## Conventions
- One eval entrypoint (`eval/run_benchmark.py`); experiments declared in
  `experiments.yaml`, not scattered scripts.
- Every reported number lands in `docs/results_ledger.md` with run id + commit.
- Per-phase `protocol.md` committed before running that phase's experiments.
