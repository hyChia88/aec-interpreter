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

**Phase 0 — Foundation (in progress).** Skeleton scaffolded. Next: migrate canonical
code, build `service/` + `eval/run_benchmark.py`, regenerate a larger clean held-out.

Plan and rationale: [`docs/ROADMAP.md`](docs/ROADMAP.md).
Canonical vs deprecated data/models: [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md).

## Setup (after Phase 0 step 2)

```bash
pip install -e ".[dev]"
```

Large artifacts (`models/`, `data/datasets/`, `data/ifc_models/`, `output/`) are
gitignored — see `DATA_INVENTORY.md` for their canonical local paths.
