# DATA INVENTORY — canonical vs deprecated

> Single source of truth for *which* data/models are real, where they live, and what
> is poisoned. Large artifacts are gitignored (see `.gitignore`); this file records
> their canonical local paths so they can always be relocated.

Legend: ✅ canonical · ⚠️ use-with-caveat · ⛔ DEPRECATED (do not use)

---

## Datasets

| Status | Name | Canonical local path | Notes |
|---|---|---|---|
| ✅ | `synth_v0.5_ap` | `~/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap` (**confirmed**, 822M total) | Canonical synthetic dataset (AP building). Bulk = `imgs/` 636M + `mappings/` 64M. **Canonical training jsonl lives in `train/`** (5.6M): `lora6_v2_ap_train_canonical_m*.jsonl` + `..._eval_canonical_m*.jsonl` (+ g7/g9 variants, modality_slices, text_tier_slices). Structure to be cleaned during migration. Source for the new larger held-out. |
| ⛔ | `116-unified` | (old eval dirs) | Flawed / underqualified synthetic; previous test data only. **Do not use.** |
| ⛔ | `synth_v0.2 … v0.4`, `*_bh`, `*_dxa` variants | data_curation | Superseded by v0.5_ap unless a multi-building study is explicitly scoped. |

## Test sets

| Status | Name | Canonical local path | n | Notes |
|---|---|---|---|---|
| ✅ | AP held-out e2e | `~/projects/cmu/master_thesis/mscd_demo/evaluation/cases/cases_ap_heldout_e2e.jsonl` (**confirmed, 60 lines**) | 60 | Current canonical benchmark. Per-case keys: `case_id, bench, difficulty_tags, ground_truth, inputs, labels, query_text`. n=60 → Top-1 CI ±~6–7pp; always bootstrap. |
| 🆕 | larger clean held-out | `data/test_sets/` (to be generated) | ~300 | **Phase 0 [NEW] task.** Regenerate from `synth_v0.5_ap`. Must pass the leakage check below. |

## Models

| Status | Name | Canonical local path | Notes |
|---|---|---|---|
| ✅ | `lora6_v2_ap_20260331` | adapters: `~/projects/cmu/master_thesis/mscd_demo/models/lora6_v2_ap_20260331/` (**1.6G**) · predictions/results: `…/output/lora6_v2_ap_20260331/` (**361M**) | Canonical model line. Qwen2.5-VL + LoRA. **6 adapter variants:** `g3_fullaug_r32, g4_ultimate, g6_baseline, g7_position_context, g8_posctx_dim, g9_opencv_cluster`. **G8 (`g8_posctx_dim`) = thesis best** (Top-10 ~30%, pool ~76). |
| ✅ | `cluster_classifier_ap` (ResNet size) | `…/mscd_demo/models/cluster_classifier_ap/` (43M) | Size-cluster ResNet used by the visual specialist. Migrate with `visual/`. |
| ⛔ | lora3-era adapters, scattered 2GB checkpoints | various old `output/` | Stale; leave in archive. |

---

## Leakage check (gate before any learned component)

The train/test split must be by **disjoint elements/regions of the building, NOT just
disjoint case-IDs over the same elements.** Document the exact split when the larger
held-out is generated. Until verified, treat any learned-ranker result as provisional.

> **Confidence-source note (for migration):** the per-field confidence contract
> (`{value, confidence, source}`, see ROADMAP P1) needs the visual-specialist scores
> (OpenCV position, ResNet size) and the schema-alignment confidence wired through during
> code migration — confirm these signals are actually emitted by the migrated code.

## Migration status (Phase 0)

- [x] confirm exact canonical paths (synth_v0.5_ap, model, held-out) — **done, survey 2026-06-08**
- [x] **code migrated** → `src/aec_interpreter/{neurosym,visual,common,handoff,schema,evaluation_infra}` + `ifc_engine.py`, `pipeline_base.py`; imports rewritten to `aec_interpreter.*`; all 42 files compile
- [x] **prompts + schema + AP held-out migrated** → `prompts/`, `schemas/corenetx_min/v0.schema.json`, `data/test_sets/cases_ap_heldout_e2e.jsonl`
- [ ] `synth_v0.5_ap` (822M) → **referenced by documented path** (NOT copied; gitignored). Path in `config/` TBD when wiring service.
- [ ] `lora6_v2_ap_20260331` (G8) + `cluster_classifier_ap` → **referenced by documented path** (NOT copied; 1.6G+43M gitignored). Wire path in `config/`.
- [ ] larger clean held-out (~n=300) → generated + leakage-checked
- [ ] `pip install -e .` then full-import smoke test (deps now pinned in pyproject)
