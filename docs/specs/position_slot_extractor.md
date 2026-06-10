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

> ✅ **INPUT-MODALITY CLARIFICATION (data audit §5, supersedes the earlier "leak" reading).** The
> marked per-case patch (`floorplans/`/`floorplans_v2/`, red TARGET + target-centered) is a
> **designed human-marking input**: the task is to *extract the target's spatial address* given the
> human's mark, not to detect the target from scratch. It is honest because the mark (image space)
> and the disambiguation (graph space, ~76 RAG candidates, unregistered to the plan) are different
> spaces joined only by the extracted address — the mark cannot prune the graph pool, so the oracle
> Top-1 lift is graph-space and uncheatable. **Two rules keep it fair:** (1) claims/eval are on
> **address accuracy + downstream GUID**, never "detected the target in the image" (centering gives
> identity); (2) the **mark-free arm** — site photo + text + cross-attention, no mark — is the
> harder autonomous track, reported separately. ⚠️ The *element-disjoint train leak* (12/59, audit
> §2) is a separate issue and still applies to any learned arm.

## 2. I/O contract (feeds the per-field confidence contract)
**Two arms (report both, fenced):**
- **Arm A — marked-plan (given the human mark):** the per-case `floorplans/` patch (red TARGET,
  target-centered) + `floorplans_full` + text. The mark gives *which* element; the extractor must
  still *read the slot* (count fillers, find the ordinal) from the layout — the mark does not hand
  it the address. Eval on **slot accuracy + downstream GUID**, never on target detection.
- **Arm B — mark-free (autonomous, the hard headline):** `imgs/*_site.png` (raw, primary — for
  fillers the wall's openings are visible and countable) + **clean** `floorplans_full` (no target
  mark) + text (names the target). Cross-attention from text → site-photo clues. The query/anchor
  indicates the target region.
- **Output (both arms):** `FieldValue{ value=(i, M), confidence∈[0,1], source="floorplan_slot"|"vlm_slot", role=unset }`
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

## 4. Approach — method axis × input axis
**Method axis (this IS the learned-interface ablation):**
- **Arm 0 — deterministic specialist (build FIRST; no GPU).** From the **site photo** (Arm B):
  detect the openings on the visible wall, order them, locate the target's *i* / count *M*. And/or
  from the **storey plan**: once the host wall is identified, count its fillers and read the slot.
  Confidence from detection-count stability / ordering margin. (Thesis OpenCV element-count ~27% is
  the prior.)
- **Arm 1 — learned head (only if Arm 0 < oracle).** Fine-tune a small VLM / vision head to predict
  `(i, M)` (LoRA via `/peft` + `/trl-fine-tuning`, or a light CNN/ViT head). Softmax → confidence.
  Trained on the element-disjoint set.

**Input axis (run on both, report fenced — see §2):** **Arm A** = marked plan (mark gives identity,
slot still read from layout; eval address+GUID only) vs **Arm B** = mark-free photo+text (the hard
autonomous number). The **A − B gap** = the value of the human mark.
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
0. **Markup discipline (see top + audit §5)** — the marked patch is a *designed input* (Arm A),
   not a leak, BUT it is target-centered, so: never report it as autonomous *target detection*;
   eval Arm A on address+GUID only. Arm B (mark-free) is the genuinely-hard autonomous number; its
   *honest realizable fraction* is the RQ2 finding (a modest number is still publishable — it
   characterizes the oracle→realizable gap and its bottleneck). The Arm A − Arm B gap quantifies
   the value of the human mark.
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
| M1 | Arm 0 deterministic slot, **both input arms** (A marked plan / B mark-free photo+plan) + intrinsic eval | offline, no GPU | A = marked ceiling; B = *honest* realizable floor (the RQ2 number); A−B = mark value |
| M2 | feed Arm 0 slot → soft rerank → filler Top-k | offline | **converts oracle 56.5 → realized #** |
| M3 | calibration (ECE) + contract wiring | offline | gates P1 |
| M4 | Arm 1 learned head **only if** Arm 0 < oracle | GPU/training | the "does learning pay?" finding |

→ **Start at M1** (cheap, offline, no GPU). M4 is conditional — we may not need it.

## 8. Dependencies / deferred
- M1–M3 are offline (floorplan images + existing labels). M4 needs the training stack
  (`/peft`, `/trl-fine-tuning`) + the leakage-safe split.
- `--live` Neo4j path is **not** required for the *extractor* eval (slot accuracy + downstream
  rerank run on the frozen pools, as the 3a/3c cuts did). Live-closeout stays a parallel track.
