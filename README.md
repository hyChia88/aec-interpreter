# AEC Interpreter

Neuro-symbolic interpreter middleware that grounds unstructured on-site evidence
(site photo + natural-language note) to the correct **IFC element GUID** in a
building's BIM model.

> **System-proving-first.** From a *raw BIM model alone* — zero real on-site labels
> at day-1 — the system answers *"where is this element?"* (image + NL → IFC GUID),
> delivers immediate human-triage value, and is **designed to improve in accuracy as
> real on-site data flows in**.

Pipeline: fine-tuned VLM extracts typed spatial constraints → JSON contract →
deterministic Cypher templates over an enriched Neo4j IFC graph → reranked GUID pool.

This is the clean development repo for the post-thesis enhancement + paper phase.
The original thesis-submission code is frozen in `master_thesis/` (separate, untouched).

## Layout

See [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for what every directory holds.

```
src/aec_interpreter/   datagen · neurosym · visual · schema · service · handoff · common
eval/                  run_benchmark.py (bootstrap CIs) · experiments.yaml · oracle/
demo/                  thin front-end → calls src/aec_interpreter/service
data/                  datasets (gitignored) · ifc_models (gitignored) · test_sets (in git)
docs/                  ROADMAP · DATA_INVENTORY · REPO_MAP · results_ledger
```

## Status

**Phase 0 — Foundation (in progress).** Skeleton + code/asset migration done (installable
via `uv`, 42/43 modules import clean). `eval/run_benchmark.py --from-traces` built and
**thesis-parity validated** (G8 reproduces all 7 Track-B metrics exactly, now with bootstrap
CIs). Next: live-closeout (dockerize Neo4j + migrate IFC model + model access) → `service/`
→ larger clean held-out.

```bash
python eval/run_benchmark.py --variant g8_posctx_dim   # offline parity, no Neo4j/GPU
```

Plan and rationale: [`docs/ROADMAP.md`](docs/ROADMAP.md).
Canonical vs deprecated data/models: [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md).

## Getting Started — manual verification

Everything below is **offline** (no Neo4j, no GPU, no model API) and runs off the frozen
G8 traces + committed reference data (`data/references/*.jsonl`, `data/test_sets/`).

### 1. Environment

The repo `.venv` is already populated (matplotlib, networkx, ifcopenshell, torch, …). Use it
directly — **`.venv/bin/python`** (bare `python3` is system Python and lacks some deps):

```bash
.venv/bin/python -m pytest -q            # 28 tests, all green
```

Fresh clone instead? `uv venv && uv pip install -e ".[dev]"`.

### 2. Reproduce the numbers (each prints a table; some save a figure to `output/`)

```bash
.venv/bin/python eval/run_benchmark.py --variant g8_posctx_dim   # thesis parity: Top-10 30.0, MRR 0.110
.venv/bin/python eval/fingerprint_ceiling.py        # attribute-layer |C| 46 -> 13
.venv/bin/python eval/rerank_prize.py               # soft-rerank prize: oracle Top-1 -> 61.7
.venv/bin/python eval/spatial_address_ceiling.py    # type-conditional address oracle: Top-1 -> 78.5
.venv/bin/python eval/slot_extractor_m1.py          # position-slot harness: floor 2.4 -> ceiling 91.0  (+figure)
```

These read no images and no train/test split, so the oracle diagnostics are leakage-proof.

### 3. The visual interface mock (spatial-address dashboard)

```bash
.venv/bin/python eval/build_demo.py                 # default: one filler + one wall card
.venv/bin/python eval/build_demo.py AP_SK_022       # any held-out case id(s)
```

Output is PNGs at `output/demo/case_*.png` (one 3x3 dashboard per case). On WSL, open them in
Windows:

```bash
explorer.exe "$(wslpath -w output/demo)"            # open the folder
```

Every panel is tagged by epistemic status — `REAL` (inputs, GT address, local graph, |C|
collapse, Top-1), `ORACLE` (the "predicted address" = perfect extraction, *not learned yet*),
`REALIZED` (G8's actual extraction from the trace), `PENDING` (attention/segmentation tiles
reserved for the P2 learned extractor).

### 4. Regenerating reference data (optional — needs the IFC model)

`data/references/*.jsonl` are committed, so the steps above need nothing extra. To regenerate
them you need `data/ifc_models/AdvancedProject.ifc` (gitignored) + `ifcopenshell`:
`eval/reconstruct_position_index.py`, `eval/wall_fingerprint.py`, `eval/depth_saturation.py`,
`eval/fingerprint_reliability.py`.

Large artifacts (`models/`, `data/datasets/`, `data/ifc_models/`, `output/`) are gitignored —
see [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md) for their canonical local paths.
