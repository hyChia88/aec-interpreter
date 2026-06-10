# DATA AUDIT — `synth_v0.5_ap` (2026-06-10)

> Gate before training the position-slot extractor (the MVP-defining build). Scope decision:
> **audit first, do NOT refactor the data_curation pipeline or regenerate n≈300** unless the
> audit exposes a real defect. It did expose one (fixable, cheap). Verdict below.

## ✅ VERDICT: GO — one required fix + one input-protocol clarification
1. **(fix)** element-disjoint split (train/test target leakage, §2) — cheap, drop 12 ids.
2. **(clarified, not a defect)** the per-case floorplan markup is a **designed human-marking
input**, not a leak (§5, confirmed with the dataset author). It is honest *as a marked-plan arm*
under two rules (eval on address+GUID not detection; mark-free photo+text arm reported
separately). The oracle diagnostics (3a/3c/depth/rerank) are **unaffected by either** (they
compute over the IFC graph, read no image); only *learned extractors* touch the split.

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

### 5. ✅ Floorplan markup = designed human-marking input (clarified 2026-06-10 with dataset author; supersedes the earlier "leak" reading)
The per-case `floorplans/AP_SK_*_floorplan.png` patch is **GT-derived**: target rendered red
("TARGET"), host/anchor orange, crop centered on the target (`floorplans_v2/*.json`:
`crop_center ≈ target_center`, from the GT `target_guid`; same for `floorplans_v2/`, 745).
**This is by design, not a defect.** The dataset models a workflow where a human marks the target
area on the plan, and the task is to **extract the target's spatial address/relationships** given
that mark — *not* to detect the target from scratch. The reconciliation that keeps this honest:

- **Two representational spaces, joined only by the address.** The mark lives in *image space*
  (it tells the extractor *which* element to describe). Disambiguation lives in *graph space*
  (the extracted address is matched against the ~76 RAG-retrieved IFC candidates). The floorplan/
  photo are **not coordinate-registered** to the live graph, so the image-space mark **cannot
  prune the graph pool**. ⇒ the |C| 110→2 / Top-1 4.9→78.5 oracle diagnostics remain valid — they
  measure graph-space disambiguation, which the mark cannot short-circuit.
- **The mark does not give the address.** "Which element is red" ≠ "3rd of 5 on host wall,
  degree-3, external" — the slot/fingerprint still must be *read from the layout*. Slot extraction
  is a real task even with the mark.
- **Residual caveats (load-bearing — these gate the claims):**
  1. **Don't claim autonomous target *detection* from the marked plan** — centering + red give
     identity for free. Claims/eval are on **address accuracy + downstream GUID match**, never
     "found the target in the image."
  2. **Patch↔full-plan localization** (compare marked patch to clean `floorplans_full`) recovers
     *where the crop sits on the floor* = template matching. Useful for localization; since the
     crop is target-centered it is **not** evidence of target-finding. Report as localization.
  3. **Mark-free arm = the hard, honest headline track:** site photo (`imgs/*_site.png`, unmarked
     — on-site you realistically can't mark anyway) + text (names the target) + cross-attention →
     spatial clues. This is the autonomous RQ1 number, reported **separately** from the
     marked-plan-assisted arm.
- **Honest sources for the mark-free arm:** `floorplans_full/` (clean per-storey, shared across
  cases → cannot encode a per-case answer) + `imgs/*_site.png` (verified unmarked on AP_SK_022).
- **Why G8's parity is still OK:** G8 received the marked patch yet scored Top-1 6.7% → it did not
  exploit the highlight (the graph-space matching is the bottleneck, as above).
- **Independent issue:** the element-disjoint train leak (12/59, §2) is unrelated to the markup and
  **still stands** for any *learned* extractor.

**Two tracks, three modalities:** (A) marked plan + photo + text → address extraction *given* the
mark; (B) mark-free photo + text → autonomous, harder. Report both, fenced.

## Actions for the extractor build (next)
1. **Use the element-disjoint train set:** drop `leakage_excluded_train_ids.txt` (12 ids) from
   any extractor training. → element-disjoint + region-disjoint.
2. Report **n = 60 cases / 59 elements**, **Tier-3 only**.
3. Oracle analyses (3a/3c, depth) are **unaffected** by this leakage (they compute over the IFC,
   not the train/test split) — only learned extractors need the cleaned split.
4. No regeneration / no pipeline refactor.
