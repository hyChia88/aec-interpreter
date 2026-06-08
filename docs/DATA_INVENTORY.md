# DATA INVENTORY — canonical vs deprecated

> Single source of truth for *which* data/models are real, where they live, and what
> is poisoned. Large artifacts are gitignored (see `.gitignore`); this file records
> their canonical local paths so they can always be relocated.

Legend: ✅ canonical · ⚠️ use-with-caveat · ⛔ DEPRECATED (do not use)

---

## Datasets

| Status | Name | Canonical local path | Notes |
|---|---|---|---|
| ✅ | `synth_v0.5_ap` | `master_thesis/data_curation/…/synth_v0.5_ap` *(confirm exact)* | Canonical synthetic dataset (AP building). Structure to be cleaned during migration. Source for the new larger held-out. |
| ⛔ | `116-unified` | (old eval dirs) | Flawed / underqualified synthetic; previous test data only. **Do not use.** |
| ⛔ | `synth_v0.2 … v0.4`, `*_bh`, `*_dxa` variants | data_curation | Superseded by v0.5_ap unless a multi-building study is explicitly scoped. |

## Test sets

| Status | Name | Canonical local path | n | Notes |
|---|---|---|---|---|
| ✅ | AP held-out e2e | `master_thesis/mscd_demo/evaluation/cases/cases_ap_heldout_e2e.jsonl` | 60 | Current canonical benchmark. n=60 → Top-1 CI ±~6–7pp; always bootstrap. |
| 🆕 | larger clean held-out | `data/test_sets/` (to be generated) | ~300 | **Phase 0 [NEW] task.** Regenerate from `synth_v0.5_ap`. Must pass the leakage check below. |

## Models

| Status | Name | Canonical local path | Notes |
|---|---|---|---|
| ✅ | `lora6_v2_ap_20260331` | `master_thesis/mscd_demo/output/lora6_v2_ap_20260331/` + `models/lora6_v2_ap_20260331/` | Canonical model line. Qwen2.5-VL + LoRA. |
| ⛔ | lora3-era adapters, scattered 2GB checkpoints | various old `output/` | Stale; leave in archive. |

---

## Leakage check (gate before any learned component)

The train/test split must be by **disjoint elements/regions of the building, NOT just
disjoint case-IDs over the same elements.** Document the exact split when the larger
held-out is generated. Until verified, treat any learned-ranker result as provisional.

## Migration status (Phase 0)

- [ ] `synth_v0.5_ap` → migrated + structure cleaned
- [ ] `lora6_v2_ap_20260331` → migrated, paths documented
- [ ] AP held-out → migrated to `data/test_sets/`
- [ ] larger clean held-out (~n=300) → generated + leakage-checked
- [ ] confirm exact canonical `synth_v0.5_ap` path (currently TBD)
