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

### Verified migration map (mscd_demo, survey 2026-06-08)

| Old path (`mscd_demo/`) | Size | → New home | Notes |
|---|---|---|---|
| `src/neurosym/` (pipeline, constraints_extractor_lora, constraints_to_query, retrieval_backend, graph_rag_rerank, cluster_classifier, floorplan_counter, condition_mask, metrics, types, README) | — | `src/aec_interpreter/neurosym/` | Core. README = the 10-limitations doc. |
| `src/ifc_engine.py` | **1530 L** | `src/aec_interpreter/neurosym/` (or `common/`) | **Was NOT in the original migrate list** — big symbolic engine that neurosym depends on. Must migrate. |
| `src/pipeline_base.py` | 187 L | `src/aec_interpreter/service/` | Pipeline base → fold into `service/`. |
| `src/visual/` (aligner, image_parser) | — | `src/aec_interpreter/visual/` | + `models/cluster_classifier_ap` (ResNet, 43M). |
| `src/common/` (config, evaluation, guid, mcp, response_parser, trace_io) | — | `src/aec_interpreter/common/` | |
| `src/handoff/` (bcf_lite, bcf_zip, trace) | — | `src/aec_interpreter/handoff/` | BCF triage handoff. |
| `src/rq2_schema/` (mapping, extract_final_json, schema_registry, validators, pipeline) | — | `src/aec_interpreter/schema/` | `mapping.py` = deterministic copy → **P1 replaces with verified schema-alignment**. |
| `src/evaluation_infra/` (runner 455L, contracts, metrics, visualizations) + `experiments.yaml` + `run.sh` 18K | — | `eval/` | The messy eval system → **rebuild as one `run_benchmark.py` + clean `experiments.yaml`**. Mine for bootstrap/metric logic; don't copy wholesale. |
| `prompts/` (system_prompt, constraints_extraction, image_parsing, graphrag_rerank, ifc_registry, tool_descriptions, dimension_anchors.json, size_cluster_taxonomy.json) | — | `prompts/` | |
| `schemas/corenetx_min/v0.schema.json` | — | `schemas/` | Shallow (≤2-level) contract. **Extend here for the per-field `{value, confidence, source}` invariant.** |
| `evaluation/cases/cases_ap_heldout_e2e.jsonl` | 60 cases | `data/test_sets/` | Canonical benchmark. |

**NOT migrated — V1 agent-as-grounding (confirmed):** `src/main_mcp.py` (546 L) + `mcp_servers/`
(`ifc_server.py` 34K, `visual_server.py` 6K). Cited qualitatively only. Also skip loose CLIs
(`chat_cli.py`, `chat_logger.py`, `ifc_export_cli.py`) unless the demo needs them.

### P1 surgical homes (verified 2026-06-08 — read `types.py` + `constraints_to_query.py`)

The confidence-routing skeleton **already exists for 2 fields**; P1 = generalize + calibrate it.

- **Per-field confidence contract** → `neurosym/types.py:Constraints`. The `{value, confidence,
  source}` triple currently exists ONLY for `position_context` and `size_band`. P1 contract
  invariant = extend it to every field (`storey_name`, `ifc_class`, `space_name`, spatial
  `object_subtype`/`direction`, `size_cluster`).
- **Calibrated field-routing** → `neurosym/constraints_to_query.py:_build_params` (lines ~276–291).
  A `should_hard_filter` gate keyed on `position_context_confidence >= 0.8` (hardcoded) already
  exists for ONE field. P1 = generalize to all fields with calibrated per-field thresholds and the
  {hard / soft / drop / clarify} decision. `fingerprint_level_requested` (attribute_only →
  topology_only → relation_fingerprint → exact_slot) is the live L0–L7 ladder hook.
- **Verified schema-alignment (input value→graph term)** → **currently ABSENT.** Values flow
  straight into params (`params["type"] = constraints.ifc_class`). The only existence-check is
  OUTPUT-side `schema/validators.py:domain_validate`. P1 adds a NEW pre-planning step that reuses
  that graph existence-check primitive to repair values to graph-attested terms.
- **P2 visual gating** → partially exists as config modes `size_cluster_mode` / `size_band_mode`
  (off/soft/hard) consumed in `_build_params`.
- **`schema/mapping.py`** = OUTPUT submission assembler (coupled to old V1 `agent_final` contract).
  Rewrite against the new pipeline contract + carry confidence + emit defer/selective-prediction
  info. NOT the input aligner.

## Conventions
- One eval entrypoint (`eval/run_benchmark.py`); experiments declared in
  `experiments.yaml`, not scattered scripts.
- Every reported number lands in `docs/results_ledger.md` with run id + commit.
- Per-phase `protocol.md` committed before running that phase's experiments.
