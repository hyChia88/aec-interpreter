# STATUS — where we are (at a glance)

> Single-page progress view. Updated as work lands. Detail lives in
> [`ROADMAP.md`](ROADMAP.md) (plan), [`results_ledger.md`](results_ledger.md) (numbers),
> [`DATA_INVENTORY.md`](DATA_INVENTORY.md) (assets), and `git log` (timeline).

**Last updated:** 2026-06-11
**Current position:** **MVP (locked scope) COMPLETE** — RQ1 oracle address (78.5), RQ2 ONE realized
extractor + calibration + selective prediction (6.6→67.6, defer→80.6), RQ3 depth law; demo live arm +
method-spine figure built; all 5 thesis sections drafted with verified citations + HTML project page.
**Remaining build is optional/strengthening** (wall detector = 2nd extractor; live closeout blocked on
Docker; leakage split = honesty fix not affecting the deterministic headline numbers).

---

## ✅ Done

- **Clean monorepo scaffold + docs** — `aec-interpreter`, src-layout, docs/ (commit `9ec5707`).
- **Code + asset migration** — `src/aec_interpreter/{neurosym,visual,common,handoff,schema,evaluation_infra}` + `ifc_engine`, `pipeline_base`; imports rewritten; reranker closure recovered from old eval tree (`6a4ee03`, `b87ef4b`).
- **Installable env (uv)** — `uv venv` + `uv pip install -e ".[dev]"`; 42/43 modules import clean (only `common.mcp` = V1/`[agent]`, expected).
- **Offline eval harness** — `eval/run_benchmark.py --from-traces` (+ `--variant`, `experiments.yaml`), clean scorer + bootstrap CIs (`3e2ca8c`).
- **Thesis parity validated** — G8 reproduces all 7 Track-B metrics exactly (Top-10 30.0%, MRR 0.1104, GT-in-pool 100%, pool median 76 / mean 118.4).
- **Parity regression test** — `tests/test_parity.py`, `pytest` 4 passed (`ab51520`).
- **Per-field confidence contract (structure)** — `schema/contract.py`: uniform
  `FieldValue {value, confidence, source, role}` + `ConstraintContract` + `from_legacy`
  adapter + generated `schemas/constraint_contract.schema.json` + 5 tests. (§2.1 step 1)
- **Idea 3a first cut (attribute-layer ceiling, Neo4j-free)** — `eval/fingerprint_ceiling.py`:
  median pool 46→13 (3.8×) from attributes alone, all via `object_type`; plateaus (2/60
  unique) → motivates topology + P1. Figure + ledger + 2 tests. (§2.1 step 2)
- **Idea 3a second cut (topology + reliability-weighting, Neo4j-free)** —
  `eval/fingerprint_reliability.py`: topology adds only 13→**12** (FILLS/CONNECTS
  homogeneous, ADJACENT_TO sparse) → feature space **saturated**; ∏r recall collapses to
  0.009 if all hard-filtered (best single r=0.625) → the 76→~13 gap is **reliability-bound**.
  **Decisive gate: Idea 3b (learned feature-selector) = SKIP; all effort → P1 calibrated
  routing.** Calibrated `object_type` routing alone: coarse 46→25.4. Figure + ledger + 3 tests.
  Also: full `IfcRel*` census (no untapped relation; `IfcRelSpaceBoundary`=0 → room-feature
  is the real-data revisit target) + 2-lever correction (soft rerank, not hard filter).
- **Idea 3c first cut (spatial-address ceiling — wall/non-filler fingerprint, offline)** —
  `eval/wall_fingerprint.py` + `eval/spatial_address_ceiling.py`. Closed the open wall subgroup:
  wall fingerprint `(connection_degree, hosted_opening_count, length_band, is_external)` →
  same-storey-wall \|C\| 110→**2** (10/22 unique, object_type 0/22). **Unified type-conditional
  spatial address** (position-slot for 35 fillers + wall-fp for 22 walls) → oracle **Top-1
  4.9→78.5, Top-10 31.5→98.1**; walls 11→64 Top-1. The full spatial-address contribution: every
  element class now has a discriminative, IFC-computable, evidence-recoverable address. Ledger +
  3 tests (23 total). Next: realistic (non-oracle) rows + full descriptor sweep + 3 "other".
- **Idea 3a third cut (soft-rerank prize on Top-k/MRR, offline) — CORRECTED w/ position_context** —
  `eval/rerank_prize.py` + `eval/reconstruct_position_index.py` (offline NEXT_TO slot, 321
  fillers, 35/60 targets addressable). Coarse saturated (31.5≈30). **Two complementary
  discriminators, both unextracted-as-structured:** `position_context` dominates **Top-1**
  (oracle 4.9→**56.5**, the thesis L4 "pool=1 for 35 cases"), `object_type` lifts **Top-10**
  (30→76); combined oracle **Top-1 61.7 / Top-10 85.6**, zero recall cost. Extract them (P2
  specialists, position-slot first) + calibrated soft rerank (P1) = money figure, justifies
  P2→P1. ⚠️ Earlier cut-2 "feature saturated" / cut-3 "object_type is the prize" SUPERSEDED
  (had omitted position_context — only in the enriched graph, not element_index). Figure +
  ledger + 5 tests (19 total).
- **Data audit (2026-06-10) — VERDICT: GO with one fix** (`docs/data_audit.md`). Held-out =
  canonical eval split (60/60 ✅); region-disjoint ✅; **but 12/59 held-out target elements leak
  into train** (region-disjoint ≠ element-disjoint) → fix = drop 12 ids
  (`data/test_sets/leakage_excluded_train_ids.txt`, 4% of train). Money-feature GT validated
  (wall `connection_degree` 14/14 vs skeleton). Held-out is **Tier-3-only** (explains low Top-1)
  + 60 cases/59 elements (1 dup). **No regenerate / no pipeline refactor needed.**
- **Live-closeout prep (docker-independent)** — `docker-compose.yml` (Neo4j 5.26, no APOC), `scripts/graph_build/` (01 export / 02 topology / 03 views) + runbook, AP IFC model + element_index migrated, `config/config.yaml`, py2neo dep (`1a9487a`).

## 🟡 In progress / partial (§2.1 step 1)

- **Per-field confidence contract** — ✅ structure + adapter + schema + tests done; ⬜ still
  need to *populate* it in the live extractor/specialists (P1 wiring) once `--live` exists.
- **Larger held-out (n≈300)** regenerated from `synth_v0.5_ap` — NOT done.
- **Leakage-safe split** (disjoint elements/regions) — NOT done.

## ⬜ Next (§2.1 order)

### ✅ M1a done (2026-06-10) — slot harness + floor/ceiling baselines
`eval/slot_extractor_m1.py` (+ fig + 5 tests, 28 total). 35 held-out fillers. **Realized floor
2.4** (G8 emits `position_context` 0/35; query has no positional cue → slot is purely visual),
**oracle ceiling 91.0**; decomposition says **the ordering index *i* is the bigger+harder lever**
(oracle-i 29.5 > oracle-M 18.8). Also: networkx pinned in pyproject; interface mock `build_demo.py`.

### 🟡 M1b probed (2026-06-10) — detector reshaped; ONE coverage decision pending
`eval/m1b_probe.py`. Findings: (1) the **marked patch occludes openings** (solid red/orange fill)
→ slot not readable from it; (2) the **clean plan color-codes openings** (window=blue, door=green)
→ directly color-segmentable, detector feasible; (3) **coverage = 3/7 storeys = 17/35 fillers**
(a deliberate scope cut in `3c_render_full_storeys.py` L155-166, not a limit). Detector design:
color-detect openings → group collinear per host wall → order → (i, M), scored on the M1a harness.

**DECISION (2026-06-10): (A) regenerate chosen — but found EXPENSIVE, so building (B) first.**
Quantified the under-reporting: **Floors 2-5 each have 46 windows but 0 storey-contained walls**
(multi-storey walls are contained in "Level 1"), so a naive full-storey re-render yields wall-less
plans (no wall to order along, no doors) — confirming the author's "F2 future work" deferral. Full
coverage needs real multi-storey-wall→floor reconstruction, **not** a flag-flip. ⇒ **Build the
color detector on the 17 fully-covered fillers now** (First Floor 6 + Garage 3 + Level 1 8 — same
detector regardless); regeneration to all 35 stays quantified F2 work.

### ✅ M1b v0+v1 done (2026-06-10) — `eval/slot_detector_cv.py`
Color-detect openings (blue=window/green=door) → wall axis from the target opening's elongation →
**orientation resolved** by a global-sign convention (`axis·(1,0.3)>0`, oracle-neutral, validated
91.0) → (i, M). **Filler Top-1: floor 2.4 → v0 4.9 → v1 9.1** (orientation now zero-loss). 32 tests.

### ✅ M1b v2 done (2026-06-10) — M-counting robustness
Fixed a GT bug (`build_global_slot` merged multi-storey walls → inflated M) + added **wall-continuity
truncation** (collinear ≠ same wall; corridor gaps break the run). **exact_M 5→12/17, Top-1
9.1→20.1, Top-10 32→43.** 34 tests. Residual bounded: 4× +1 corner end-effect, 1 corridor case,
~3-case orientation sign ambiguity.

### ✅ M1b coverage / F2 re-render done (2026-06-10) — `scripts/render_upper_storeys.py`
Pulled each upper-floor window's host wall (FILLS→VOIDS) + rendered via the dataset's own
`render_one` → **coverage 17/35 → 35/35**. Detector now: realistic-cluttered **Top-1 39.1** /
sparse-new 94.6 / aggregate 67.6 (oracle 91). ⚠️ **The new plans are sparse (host-walls-only) =
optimistic; the realistic number is 39.1** (floor 2.4 → 39.1 = 16× on cluttered plans). Full arc:
**2.4 → 39.1 realistic** (67.6 aggregate). 34 tests.

> ⚠️ **HONESTY LABEL — M1b is Arm-A (coordinate-anchored), NOT autonomous.** The detector takes the
> target's **known world centroid** (`detect(target_world, …)`) to anchor itself in the full plan,
> then reads the slot. So **39.1 = "given the target's location (the human mark / known coords),
> read its address from the image"** — like mscd_demo's predefined-coordinate approach. It is *not*
> find-from-scratch grounding. M (total) always comes from the **full plan** (the marked patch is
> cropped + occludes openings), so the only difference between arms is *how the host wall is found*.
> **Arm-B (autonomous) = future track:** anchor by **patch↔plan localization** (the demoted
> localization work returns here) instead of known coords; **A − B = value of knowing the location.**

### ✅ (2) P1 calibrated soft-rerank + ECE — DONE (2026-06-11), Steps A/B/C
`eval/field_contract.py` (A: contract bridge `FieldValue{value,conf,source=opencv}` + `collect_pairs`),
`eval/calibration_diag.py` (B: ECE gate), `eval/calibrate_rerank.py` (C: temperature + soft-rerank +
selective). **All scored vs `gslot`, NOT `pos`** (convention lock — see ROADMAP glossary).
- **B — gate PASSES:** raw M1b conf is +correlated (AUROC **0.80**), moderately mis-calibrated (ECE
  **0.206**), joint 74% (exact_M 83% / exact_i 74%). ⇒ no L188 contingency, no geometry-margin swap.
  ⚠️ A first pass scored vs `pos` (wdir local-X sign, image-non-recoverable) → 16/35 mirror disagreement
  → spurious anti-correlation (0.31 / ECE 0.41); **fixed same-day, fenced in `collect_pairs`** (requires gslot).
- **C — two findings:** (1) **soft-rerank == hard** (Top-1 **67.6**, floor 6.6) — the slot is the finest
  tiebreaker, any positive weight reorders identically, so reweighting is a no-op; (2) **selective
  prediction is the payoff** (L183): defer bottom ~20% → coverage 0.80, **Top-1 67.6 → 80.6 (+13pp)**.
  Calibration T=0.30, ECE 0.206→0.172. Figures: `output/calibration_diag.png`, `output/calibrate_rerank.png`. 46 tests.

### ✅ Demo live arm — DONE (2026-06-11)
`eval/build_demo.py` predicted panel now has a **LIVE** epistemic tag: the M1b position-slot
prediction + raw→temperature-calibrated confidence + selective **ANSWER/DEFER** decision (τ=0.40),
judged against `gslot`. The card now contrasts **G8 REALIZED** (leaves `position_context` empty)
vs **LIVE** (fills the slot, calibrated, defer-aware). Two showcase cards: `AP_SK_102` = ANSWER
(predicted 2/17, ✓ match, conf 0.52→0.57) ; `AP_SK_092` = DEFER (predicted 1/10 but GT 8/10 ✗,
conf 0.29→**0.05** → defers instead of confidently-wrong). Auto-disables if `slot_detector_cv.FULL`
absent. GT slot display + addr_str now use the `gslot` convention (lock). 48 tests.

### ✅ RQ2 write-up — DRAFTED (2026-06-11)
`docs/thesis/rq2_calibrated_routing.md` — mechanism chapter section (sibling of
`why_not_end_to_end.md`). Spine: soft prior in a recall-fixed pool (not hard filter, ∏r≈0.009) →
one extractor 6.6→67.6 → ECE gate passes (AUROC 0.80) → soft==hard no-op → selective prediction
(defer 20% → 80.6) → image-recoverable convention prerequisite. Leads with deferral (L183),
calibration supports (L102); honest boundary (n=35, one extractor, no-op reported not buried).
Pulls figures `output/{pipeline,calibration_diag,calibrate_rerank}.png` + DEFER card.

### ✅ Citations verified + RQ1 drafted (2026-06-11)
- **Citations:** `docs/thesis/references.bib` — all external `\cite{}` keys programmatically
  verified (arXiv id_list + doi.org BibTeX + URL HTTP-200): `guo2017calibration`,
  `geifman2017selective`, `sutton2019bitter`, `buildingsmart2024ifc4x3`. No BibTeX from memory.
  `[CITE: thesis baseline]` reframed as internal cross-ref.
- **RQ1 section:** `docs/thesis/rq1_spatial_address.md` — the representation headline. Confusable
  set C(e); coarse floor saturates (oracle 4.9 ≈ realized 6.7); type-conditional address
  (filler position-slot / wall fingerprint) → oracle Top-1 4.9→78.5 (fillers 91, walls 64.2);
  depth-1 saturation (13→8.2→8.1); IFC-computable (14/14) ∧ image-recoverable. All numbers
  trace to ledger; honest boundary (oracle r=1, "other" class, room gap, single project).

### ✅ RQ3 + intro/abstract drafted; thesis front-to-RQ3 complete (2026-06-11)
- **RQ3 section:** `docs/thesis/rq3_depth_law.md` — the depth law. Information≠realizability:
  oracle WL→1 (deeper unique) but per-hop reliability 0.40→0.05→0 caps realizable |C| at depth-1
  (13→8.2→8.1→8.1); training-side corroboration from prior thesis (depth-≥2 wasted + costs
  ifc_class, r=16, −13pp); answer = compile depth into the node, extract at depth ≤1.
- **Intro/abstract:** `docs/thesis/00_intro_abstract.md` — Farquhar 5-sentence abstract + one-
  sentence contribution + RQ1→2→3 threaded bullets + Figure 1 = pipeline.png + scope up front.
- **Citations:** +`chakraborty2024multihop`, `mao2019nscl` (arXiv-verified), `chiahuiyen_mscd_thesis`
  (self-cite; ⚠️ confirm title/year). `§[thesis baseline]` resolved → \cite. **All [CITE:] markers
  gone; 7 keys used = 7 verified in references.bib.**

### ✅ M2 wall detector — DONE as a negative result (2026-06-11)
`eval/wall_extractor_m1.py` (M2a harness) + `eval/wall_detector_cv.py` (M2b v0). **Finding: the
wall fingerprint is largely NOT image-recoverable** — collinear IfcWall instances merge into one
poché, so length_band (5/17) + connection_degree (needs endpoints) depend on a modelling
segmentation invisible in the render; only hosted_opening_count recovers (too weak alone). Realized
wall Top-1 3.3 ≈ floor (oracle 64.2). **This strengthens the thesis** (direct evidence for the
RQ1/RQ2 image-recoverability constraint; explains why the MVP scoped realization to ONE extractor =
fillers). v1 junction-counting not pursued (endpoints non-recoverable). 7 tests. ⇒ fold into
RQ1/RQ2 as the negative case; do not chase the wall number.

### ✅ Interactive 3D-highlight demo — DONE (2026-06-11)
`eval/build_3d_demo.py` + `site/demo.html`. Pick a held-out case → the grounded element is
highlighted in orange (glow box + beam) in the BIM model in 3D (Three.js + glTF), beside the
reasoning panel (site photo + predicted slot + calibrated confidence + ANSWER/DEFER). Server-side:
ifcopenshell.geom + trimesh extract each case's storey to a GUID-named GLB (~2MB, cached) +
cases.json (6 cases, 5 storeys). Verified end-to-end in headless Chrome (swiftshader). Launch
button + run instructions on `index.html`. trimesh added to deps. Project page also merged with the
thesis-stage portfolio (full problem→system→modules→impact narrative + glossary).

### ✅ Submission-gap closes + demo backend + VLM re-eval (2026-06-12)
- **External baseline** (`eval/external_baseline.py`): dense/lexical retrieval plateau (Top-1 1.7,
  Top-10 16–25) — below G8; address 78.5 breaks the ceiling. Beats an external standard, not own ablations.
- **Triage effort** (`eval/triage_effort.py`): manual scan 38 inspections → 0.5 with the address
  (76×; ~570s→~8s/element); search → verification.
- **Demo backend waterfall** (`build_3d_demo.py`+`demo.html`): per-case pool collapse 76→46→1 panel +
  blue look-alike dots vs orange target in 3D (window meshes don't shade → world-space markers).
- **VLM re-eval** (`eval/vlm_profile.py`): G8 extracts coarse 100% but discriminating slot/size 0%,
  direction 57% → delegate slot/size to specialists (the realized path); documented in RQ2 + project page.
- 65 tests pass.

### ▶️ NEXT (Docker-gated or low-priority)
- **Live closeout + agent ablation** — needs Docker WSL integration (you enable); unblocks the live
  Neo4j arm of the demo + the static→learned→agent adaptivity finding (RQ4).
- **P4 subtype-contrastive data aug** — only VLM-side gain (direction 57%→); slowest loop, lowest priority.
- **Real 20–30-case study** — the venue unlock for Automation in Construction (org-gated).

### (older) thesis assembly or build
- **Thesis:** all four RQ sections + abstract/intro + baseline drafted (markdown). Remaining:
  port to the LaTeX template, resolve `\cite{chiahuiyen_mscd_thesis}` title/year + the
  hand-added venue fields, related-work section, limitations consolidation.
- **Build (post-MVP, deferred):** (1) wall-fingerprint detector, (3) detector polish,
  Arm-B patch↔plan localization (autonomous track).

### (archived) NEXT: (2) P1 calibrated soft-rerank + ECE — *in MVP scope; recommended*
The locked MVP scope = **the ONE extractor (position-slot, done) + calibrated soft-rerank + ECE +
interface panel**; **"all-descriptor extractors" (incl. the wall detector) are explicitly OUT**. So:
- **DO NOW (2):** wire the per-field `{value,confidence,source}` contract on the M1b slot outputs →
  calibrate (temperature) → reliability diagram + **ECE** → recall-safe soft-rerank + selective
  prediction (defer on low conf). This is the **RQ2 mechanism** (determinism↔adaptivity) + the
  **demo's live arm**. Self-contained on existing outputs. Build it **class-agnostic** so the wall
  detector plugs in later for free.
- **DEFER (1) wall-fingerprint detector → post-MVP** (it's "all-descriptor", out of locked scope;
  partly reuses M1b opening-counting + adds junction detection for `connection_degree`).
- **DEFER (3) detector polish** (de-optimism the 94.6 via realistic clutter; corner-detection) — low ROI.
- **Arm-B localization anchoring** (above) — future autonomous track.

### (was) NEXT: position-slot structured extractor (P2) — the MVP-defining build
Scoped in `docs/specs/position_slot_extractor.md`. Turns oracle Top-1 56.5 / 78.5 into a
realizable number. **From the audit:** (1) *fix* — element-disjoint train set, drop
`data/test_sets/leakage_excluded_train_ids.txt` (12 ids); (2) *input clarification (§5,
supersedes earlier "leak")* — the marked per-case patch `floorplans/` is a **designed
human-marking input**, not a leak. Run **two input arms, fenced:** **Arm A** = marked plan +
photo + text (mark gives identity; slot still read from layout; eval on **address + GUID**, never
target detection — it's target-centered) vs **Arm B** = mark-free `imgs/*_site.png` + clean
`floorplans_full` + text (the hard autonomous RQ1 number). A−B = value of the mark. Report **n=60
cases / 59 elements, Tier-3 only**. Build order: M1 deterministic, both arms (offline) → M2 feed
slot → soft-rerank filler Top-k (the realizable number) → M3 calibrate → M4 learned head only if M1<oracle.

### Backlog
1. finish step 1: confidence contract (done) → leakage split (audit above) → n≈300 (DEMOTED).
2. ~~step 2 — Idea 3a~~ ✅ DONE (3 cuts + depth-saturation + Idea 3c wall fingerprint).
3. step 3 — P2 gated specialists (position-slot extractor first; + Idea 2a storey/zone segmenter).
4. step 4 — P1 calibrated routing (ECE gate) → step 5 adaptivity ablation → step 6 P4.

## ⚠️ Blockers

- **Docker** WSL integration off → can't run Neo4j → can't run `--live` / ingest / retire `mscd_demo`. Runbook is ready; needs Docker Desktop WSL integration enabled (or a local Neo4j on `bolt://localhost:7687`, `neo4j/password`).

## 🚪 Publish gate (retire `mscd_demo`)

Requires `--live` self-contained: Neo4j up → `scripts/graph_build` 01→03 → `--live` reproduces frozen G8. Then old repo can be frozen/closed.
