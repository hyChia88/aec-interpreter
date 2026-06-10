# DATA AUDIT — `synth_v0.5_ap` (2026-06-10)

> Gate before training the position-slot extractor (the MVP-defining build). Scope decision:
> **audit first, do NOT refactor the data_curation pipeline or regenerate n≈300** unless the
> audit exposes a real defect. It did expose one (fixable, cheap). Verdict below.

## ✅ VERDICT: GO — with TWO required fixes before any *image-consuming* model
1. element-disjoint split (train/test target leakage, §2); 2. **honest floorplan input
(image-annotation leak, §5) — found while scoping the extractor.** Both are cheap. The oracle
diagnostics (3a/3c/depth/rerank) are **unaffected by either** (they compute over the IFC, read
no image); only *learned extractors* are.

- **Held-out integrity:** ✅ the repo held-out (`data/test_sets/cases_ap_heldout_e2e.jsonl`,
  60) **is** the dataset's canonical eval split (`lora6_v2_ap_eval_canonical_m.jsonl`) — 60/60
  base-IDs match. No silent divergence.
- **Region-level leakage:** ✅ **0 overlap** — `region_id` is disjoint between train and
  held-out. The split was *designed* region-disjoint (good).
- **Element-level leakage:** ⚠️ **12/59 held-out target elements also appear as training
  targets** (an element can sit in two regions, so region-disjoint ≠ element-disjoint). This
  matters for *learned extractors* (the model could have seen the test element under a
  different skin). **Fix is cheap:** exclude the 12 `base_case_id`s →
  `data/test_sets/leakage_excluded_train_ids.txt`, costing **108/2247 train rows (4%)**.
- **Money-feature GT:** ✅ reconstructed wall `connection_degree` matches the dataset's own
  skeleton GT **14/14** — validates the wall fingerprint against authoritative labels. (The
  position-slot is geometry-reconstructed; the 14/14 wall match gives high confidence the IFC
  geometry reconstruction is faithful.)
- **Regenerate n≈300 / refactor pipeline:** ❌ **not needed.** Top-1 is demoted (pool/MRR/
  per-field are fine at n=60), and the dataset already carries a mature audit infrastructure
  (`mappings/audit_gap_report_*`, `mining_overlap_report_*`, `visual_exclude_ids_*`).

---

## Findings in detail

### 1. Split consistency ✅
`held-out ⊆ eval-canonical base-IDs` = True (60/60). The held-out is the intended canonical
eval split; the thesis G8 numbers were measured on it, so our parity/oracle work is comparable.

### 2. Leakage (the reason this audit existed)

| key | held-out | train | overlap | note |
|---|---|---|---|---|
| `region_id` | 48 | 187 | **0** ✅ | split is region-disjoint (by design) |
| **`target_guid`** | 59 | 214 | **12** ⚠️ | element-level target leakage — the fix target |
| `retrieval_gt_guid` | 48 | 176 | 7 ⚠️ | subset of the above |
| `host_guid` | 12 | 31 | 10 | context overlap (host walls) — secondary |
| `anchor_guid` | 42 | 143 | 13 | context overlap — secondary |
| `ref_element_guid` | 53 | 181 | 16 | context overlap — secondary |

- **Primary fix (required):** target-disjoint split → exclude
  `leakage_excluded_train_ids.txt` (12 `base_case_id`s, 108 rows / 4%). The 12 leaked targets
  are **9 fillers + 3 walls** — i.e. they hit exactly the money-feature subgroups, so the fix
  is not optional for a fair position-slot / wall-fingerprint extractor.
- **Secondary (optional, conservative):** host/anchor/ref elements also overlap. The target is
  the standard fairness bar; if a reviewer pushes on context memorization, additionally exclude
  train rows whose `host_guid`/`anchor_guid` ∈ held-out (more rows dropped). Decide at training
  time; not required for v1.
- **Within-test duplicate:** target `1ebX2H7F12su$wtPbeYATe` is the GT of **two** cases
  (`AP_SK_234`, `AP_SK_294`) → 60 cases but **59 unique target elements**. Minor; report n as
  "60 cases / 59 elements."

### 3. Money-feature GT verification ✅
- **Walls:** reconstructed `connection_degree` == skeleton `target_props.connection_degree`
  for **14/14** wall targets that record it. The dataset's own `discriminating_features` use
  `degree=N` — our wall fingerprint aligns with how the data was designed.
- **Fillers:** position-slot is geometry-reconstructed (`reconstruct_position_index.py`); no
  independent integer slot label in the dataset to diff against, but the wall geometry match
  (14/14) and the FILLS/NEXT_TO census give high confidence.

### 4. Distribution / difficulty
- **Class balance (held-out):** 22 `IfcWallStandardCase` / 30 `IfcWindow` / 8 `IfcDoor`.
- **Difficulty:** **all 60 are Tier-3 (hardest).** ⚠️ The held-out is a *hard-tier-only* slice
  — this is why realized Top-1 is 6.7%. **State in the paper:** results are on the hardest
  tier, not a difficulty-representative sample (conservative, but flag it).
- **Pattern:** CONNECTS_TO 14 · FILLS 14 · NEXT_TO 20 · ADJACENT_TO 12 (balanced).
- **Locatability score:** 0.7–0.95 (median 0.8) on the 48 relational cases — all reasonably
  locatable by design.
- **Train SR-depth:** 1-SR 391 · 2-SR 98 · 3-SR 260 (≈48% multi-hop) — the depth≥2
  over-supervision already flagged (depth policy: stop training it; see ROADMAP).

---

### 5. ⚠️ Image-annotation leak in the per-case floorplan patch (found 2026-06-10, scoping)
The held-out `inputs.floorplan_patch` → `floorplans/AP_SK_*_floorplan.png` is **GT-annotated
and target-centered**: the target element is highlighted (red "TARGET"), the host/anchor is
highlighted (orange), and the crop is centered on the target (`floorplans_v2/*.json`:
`crop_center ≈ target_center`, rendered from the GT `target_guid`). The same holds for
`floorplans_v2/` (745). So **the per-case floorplan encodes the answer** — any image model that
reads it is reading the GT, not grounding.
- **Honest image sources:** `floorplans_full/` (7 *clean* per-storey plans, no target mark) and
  `imgs/*_site.png` (raw site photos, unmarked — verified on AP_SK_022). Site photo is the
  realistic primary; clean storey plan is the honest top-down source.
- **Why G8's parity is still OK:** G8 received the annotated patch yet scored Top-1 6.7% → it
  did not (or could not) exploit the highlight. Incidental, not by design — **we must not rely on
  that for any new model.**
- **Interpretation (resolve with dataset intent):** the highlight may be the *intended*
  "floorplan-markup" modality (Idea 2b — subcontractor circles the area). If so it is a
  **legitimate but easier, human-in-the-loop capability** and must be reported **separately**
  from autonomous grounding; even then, target-centering makes it near-trivial, so it is an
  upper-bound track, not the RQ1/RQ2 number.
- **Required fix:** for measuring *autonomous* grounding (RQ1/RQ2), feed the extractor the **site
  photo (primary) + clean `floorplans_full` plan**, never the annotated per-case patch. Swap or
  drop `inputs.floorplan_patch` → annotated-patch in the held-out for image-consuming runs.

## Actions for the extractor build (next)
1. **Use the element-disjoint train set:** drop `leakage_excluded_train_ids.txt` (12 ids) from
   any extractor training. → element-disjoint + region-disjoint.
2. Report **n = 60 cases / 59 elements**, **Tier-3 only**.
3. Oracle analyses (3a/3c, depth) are **unaffected** by this leakage (they compute over the IFC,
   not the train/test split) — only learned extractors need the cleaned split.
4. No regeneration / no pipeline refactor.
