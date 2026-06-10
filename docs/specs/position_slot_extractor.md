# SPEC — Position-slot extractor (P2, the MVP-defining build)

> Turns the oracle ceiling into a realizable number. `position_context` (the NEXT_TO
> wall-slot) is the headline discriminator (oracle Top-1 6.7 → **56.5** for the 35 filler
> targets). This is the one extractor v1 builds (see ROADMAP "~70% topology / one extractor").
> It is the learned-interface ablation's **Arm 0 (deterministic) vs Arm 1 (learned)** in
> concrete form.

## 1. Objective
Given site evidence for a target window/door, predict its **position slot** = the structured
field `{wall_position_index i, wall_child_total M}` ("the *i*-th of *M* fillers along the host
wall"). Feed it into the deterministic symbolic layer + calibrated soft rerank to *realize* the
oracle Top-1 lift, with zero recall cost (soft, never evicts GT).

> ⚠️ **BINDING CONSTRAINT (data audit §5): the per-case floorplan patch leaks the answer.**
> `floorplans/` and `floorplans_v2/` are GT-annotated (target highlighted + crop centered on the
> target). Feeding them = reading the GT, not grounding. **Honest inputs only:** `imgs/*_site.png`
> (raw site photo, primary) + `floorplans_full/` (7 clean per-storey plans, top-down). The
> annotated patch is at most a **separate "floorplan-markup" upper-bound track** (human-in-the-loop),
> reported apart from the autonomous RQ1/RQ2 number.

## 2. I/O contract (feeds the per-field confidence contract)
- **Input (HONEST):** `site_photo` (primary — for window/door fillers the wall's openings are
  visible and countable) + **clean** `floorplans_full` storey plan (top-down, no target mark).
  **NOT** the annotated per-case patch. The query/anchor indicates the target region.
- **Output:** `FieldValue{ value=(i, M), confidence∈[0,1], source="floorplan_slot"|"vlm_slot", role=unset }`
  conforming to `src/aec_interpreter/schema/contract.py`. Routed by P1 (soft prior by default;
  selective hard filter only when calibrated-confident).
- **Label space (measured, small/discrete):** `M ∈ {2,3,4,5,6,9,10,14,17}`, `i ∈ {0..16}` (low-
  skewed). → ordinal classification, not regression.

## 3. Data + labels
- **Training:** 1179 rows / **128 unique filler targets** (after dropping
  `leakage_excluded_train_ids.txt` → element-disjoint *and* region-disjoint).
- **Labels:** GT `(i, M)` from `data/references/position_index.jsonl` (reconstructed from IFC
  geometry; validated 14/14 against skeleton GT for the wall analog — high confidence).
- **Eval:** AP held-out fillers (n≈35, element-disjoint, **Tier-3 only** — report as such).

## 4. Approach — two arms (this IS the learned-interface ablation)
- **Arm 0 — deterministic specialist on HONEST inputs (build FIRST; no GPU).** From the **site
  photo**: detect the openings on the visible wall, order them, locate the target's *i* / count
  *M*. And/or from the **clean storey plan**: once the host wall is identified, count its fillers
  and read the slot. Confidence from detection-count stability / ordering margin. (Thesis OpenCV
  element-count ~27% is the prior; honest inputs make this *harder* than the leaky patch, not
  easier — that is the point.)
- **Arm 1 — learned head (only if Arm 0 < oracle).** Fine-tune a small VLM / vision head on the
  floorplan-patch crop to predict `(i, M)` (LoRA via `/peft` + `/trl-fine-tuning`, or a light
  CNN/ViT head). Softmax → confidence. Trained on the element-disjoint set.
- **Vocabulary-constrained:** outputs are constrained to valid `(i, M)` ranges per the host
  wall's known filler count — cannot emit an impossible slot (the auditability rule).

## 5. Evaluation
- **Intrinsic:** exact-`i`, exact-`M`, joint `(i,M)`, and ±1-tolerance accuracy on held-out
  fillers. Baselines: OpenCV count (~27%), G8 free-text `position_context`.
- **Downstream (the money metric):** feed predicted slot → soft rerank → measured **Top-1/Top-10
  on the filler subgroup**, vs realized G8 (Top-1 2.4 fillers) and oracle (91.0 fillers). This
  converts the 56.5 oracle ceiling into a realized number.
- **Calibration:** reliability diagram + ECE; temperature-scale if needed (gates P1 routing).

## 6. Risks
0. **Annotation leak (binding, see top + audit §5)** — never use the GT-annotated/target-centered
   per-case floorplan for the autonomous number. Honest inputs make the task genuinely hard; the
   *honest realizable fraction* is the RQ2 finding (a modest number is still publishable — it
   characterizes the oracle→realizable gap and its bottleneck).
1. **Host-wall identification** — the slot is relative to the *correct* host wall; on honest
   inputs this is itself part of the grounding problem (somewhat circular: to read the slot you
   must first find the element). Mitigation: use the query anchor + storey to narrow the wall;
   accept that *M* may be the easier sub-target than absolute *i*.
2. **Synthetic-floorplan over-optimism** — clean glyphs may make Arm 0 look better than it would
   on real plans. Flag as a transfer caveat; it's the cold-start honesty boundary.
3. **Reference-frame (left/right)** — floorplan orientation vs model frame must be consistent;
   define a canonical ordering (along host-wall local +X, matching `_create_next_to_edges`).
4. **`M` from the site photo alone is often unknowable** (perspective/occlusion) → that's *why*
   the floorplan patch is primary, not the photo.

## 7. Milestones (de-risk cheap → expensive)
| M | step | cost | gate |
|---|---|---|---|
| M1 | Arm 0 deterministic slot on **honest inputs** (site photo + clean storey plan) + intrinsic eval | offline, no GPU | measures the *honest* realizable floor (the RQ2 number) |
| M2 | feed Arm 0 slot → soft rerank → filler Top-k | offline | **converts oracle 56.5 → realized #** |
| M3 | calibration (ECE) + contract wiring | offline | gates P1 |
| M4 | Arm 1 learned head **only if** Arm 0 < oracle | GPU/training | the "does learning pay?" finding |

→ **Start at M1** (cheap, offline, no GPU). M4 is conditional — we may not need it.

## 8. Dependencies / deferred
- M1–M3 are offline (floorplan images + existing labels). M4 needs the training stack
  (`/peft`, `/trl-fine-tuning`) + the leakage-safe split.
- `--live` Neo4j path is **not** required for the *extractor* eval (slot accuracy + downstream
  rerank run on the frozen pools, as the 3a/3c cuts did). Live-closeout stays a parallel track.
