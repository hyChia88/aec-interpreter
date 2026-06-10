# ROADMAP — AEC Interpreter (enhancement + paper phase)

> Authoritative, version-controlled plan. Generated from the consolidated planning
> note + project memory after the research review and the autoresearch red-team.
> Principle: **DEEPEN one claim, don't broaden.**

---

## 0. Framing — "system-proving-first / cold-start from raw BIM"

From a **raw BIM model alone** — zero real on-site labels at day-1 — we stand up a
system that understands space: given an image + natural-language note it answers
*"where is this element?"* (→ correct IFC GUID), delivers immediate triage value,
and is **designed to improve in accuracy as real on-site data flows in**.

This reframes synthetic-only from a weakness into deployment reality: on day-1 you
have the BIM, not a labeled photo dataset.

> **Honesty caveat (bake into the paper):** "improves as data flows in" is a
> *designed-for hypothesis, not a demonstrated result*, until real data exists.
> State it as future-validated, not proven.

---

## 1. Diagnostic (from thesis Ch.7) — drives everything

- Symbolic backend essentially solved: oracle 100% GT-in-Pool; oracle Top-10 58% (L3),
  100% at L4 (58% cov).
- **Correction / sharpening (2026-06-09):** do not read the latest repo cuts as
  "topology enrichment does not matter." Thesis Ch.7 says the opposite: coarse
  relation type (`predicate + object`, L2) compresses weakly, but richer fingerprints
  (`direction + subtype + material + distance + connection_degree`, L3) drive the
  oracle jump, and exact position slots (L4) are decisive when extractable. The prize is
  a **visual-topological spatial address**, not just adding more edge labels.
- Realized system is weak at **ranking**: pool ~76, Top-10 ~30%, Top-1 ~6.7%, MRR ~0.11.
  GT-in-Pool already 100% → remaining gains are *ranking/compression*, not recall.
- Live planner falls back to the P1 attribute pool (~76) instead of consuming the L3
  fingerprint (oracle pool ~9) because it **can't trust extraction confidence**.
  Closing 76→9 / 30→58% is the bounded prize.
- OpenCV (position 27%) and ResNet (size 31.6%) already beat the VLM on their sub-tasks
  but are only used as soft rerank text.

**Spine claim (framed as a tension resolution):** *Neuro-symbolic IFC retrieval faces a
**determinism/auditability ↔ adaptivity/accuracy** tension — the deterministic backend is
auditable but cannot exploit uncertain extractions, so it falls back to a coarse pool. We
resolve it with a confidence-routing layer placed **between** probabilistic extraction and
deterministic execution: the policy adapts, the execution stays auditable. Mechanism:
field-level extraction confidence is the binding constraint, and calibrated per-field
routing recovers a measurable fraction of the oracle–realized gap.*

> Lead with the tension/auditability framing, not "we added calibration." In a
> liability-heavy vertical (AEC), an auditable deterministic decision trace + calibrated
> confidence is a genuine differentiator.

**SPINE DECISION (2026-06-09) — one line, not three pillars.** Rank by epistemic status:
- **Spatial address = the CONTRIBUTION / headline.** Grounding = *predict a visual-topological
  spatial address* (IFC-computable ∧ image-recoverable) in a known BIM map — image-to-map
  localization / visual place recognition. Most novel, domain-defensible, not "applied calibration."
- **Confidence routing = the MECHANISM** (predicts the address under uncertainty; soft rerank
  primary, calibration supporting). Do NOT lead with calibration (ECE-failure contingency makes
  it fragile as a headline).
- **Agent orchestration = an ABLATION arm** of routing (the card most likely to lose), not a pillar.
- **SAM** = framing discipline only (one task, one representation); the technical analogy is visual
  place recognition, not segmentation (we have no SAM-scale data engine — synthetic n≈300).

**Phase-0 measured diagnostics (2026-06-09)** — all offline, AP held-out n=60; full numbers in
`results_ledger.md`, figures in `output/`:
- **Soft-rerank prize (real pools, GT-in-pool 100%):** two complementary, currently-unextracted
  discriminators — `position_context` (the `ifc_engine` NEXT_TO slot, 35/60 targets) drives **Top-1**
  (oracle 4.9→**56.5**, = thesis L4 "pool=1 for 35 cases"); `object_type` drives **Top-10** (30→**76**).
  Both oracle → Top-1 61.7 / Top-10 85.6. Realistic `object_type` (r=0.625) ≈ doubles Top-10 (30→59.5).
  Soft rerank ⇒ zero recall cost. (Earlier cuts missed `position_context` — it lives only in the
  enriched graph, not `element_index`.)
- **Depth saturation (measured, not asserted):** realizable median |C| by relational depth =
  13 (attr) → **8.2 (1 hop)** → 8.1 → 8.1. Oracle WL → 1 (info says deeper is unique) but per-hop
  reliability (0.40/0.05/0) caps realizable gain at **depth-1** (≈ oracle-L3 9). → **extract at
  depth ≤1; go richer at depth-1, never deeper.** (`eval/depth_saturation.py`)

---

## 2. Phases

Test set = **AP held-out only** (116-unified dropped, flawed). Primary metrics =
**pool-compression (76→9) + MRR@10 + per-field extraction accuracy** (more power than
Top-1 at small n). Latency/cost tracked first-class. Top-1 reported but demoted.

### 2.0 Framing spine — one tension, four layers

The enhancements are **not separate directions** — they are the same
determinism/auditability ↔ adaptivity/accuracy tension (§1) attacked at four layers.
Framed as "one tension at four layers" → coherent depth; framed as "we also added an
agent, also segmentation, also a fingerprint module" → scope creep / desk-reject.
**Rule:** every enhancement is justified by *which layer it deepens*, never by "more
capability." If it doesn't map to a layer, it broadens → cut.

| Layer | Decision | Enhancement | Status |
|---|---|---|---|
| **Feature/addressing** *(HEADLINE)* | which IFC-derived spatial address uniquely+reliably IDs an element within its visual-confusable set | visual-topological spatial address + fingerprint diagnostics (Idea 3a/3c) | **HEADLINE = the contribution** |
| **Routing** *(mechanism)* | per-field confidence → {hard/soft/drop/clarify}; soft rerank primary | P1 calibrated, vocabulary-constrained neural→symbolic interface | MECHANISM (predicts the address under uncertainty) |
| Evidence | which deterministic specialists feed the contract | segmentation/classification / floorplan-address specialist (Idea 2a) | P2 extension |
| Policy-adaptivity | how smart must the router be? | agent vs learned vs static (Idea 1) | P1 ablation arm (likely to lose; not a pillar) |

### Phase 0 — Foundation (new clean monorepo + harness)  ← CURRENT
- New clean monorepo (datagen + system + eval + demo). Old 3 components frozen as
  thesis-submission archive. Migrate ONLY canonical assets (`synth_v0.5_ap`,
  `lora6_v2_ap_20260331`, AP held-out, `src/{neurosym,visual,common,handoff}`,
  refactored `schema/`, prompts, `ifc-bonsai-mcp` as datagen tool).
- `docs/`: ROADMAP, DATA_INVENTORY, REPO_MAP, results_ledger.
- `src/aec_interpreter/service/` (pipeline as callable + FastAPI, shared by demo+eval)
  + `eval/run_benchmark.py` (bootstrap CIs). **Two modes (decided 2026-06-08):**
  - `--from-traces` — score saved per-case e2e traces offline. **No Neo4j, no GPU.**
    Used for harness validation, thesis-parity, and as a fast regression baseline.
  - `--live` — run the real pipeline (extract → plan → retrieve → rerank). **Needs
    Neo4j + model inference (GPU or API).** Used for every new experiment (P2/P1) and
    for publication-grade from-scratch reproduction.
- **Runtime deps (surveyed 2026-06-08):** retrieval backend = `memory | neo4j`; memory
  mode *degrades* on all topology strategies ("no adjacency data") so faithful results
  need **Neo4j** (`bolt://localhost:7687`, ingested from IFC via `ifc_engine.py`).
  Live extraction needs the Qwen2.5-VL LoRA (GPU) or an API path. Precomputed artifacts
  exist for every variant: Track-A extraction `output/.../gN__ap_eval.jsonl` and Track-B
  per-case e2e `…/ap_e2e_phase5_g8/g8_posctx_dim/traces_*.jsonl` + `metrics/*_metrics.json`.
- **Baseline-reproduction — ✅ DONE (2026-06-08).** `eval/run_benchmark.py --from-traces`
  (+ `--variant`, `experiments.yaml`) reproduces G8 with **all 7 Track-B metrics exact**
  (Top-10 30.0% · MRR 0.1104 · GT-in-pool 100% · pool median 76 / mean 118.4), now with
  bootstrap 95% CIs. Harness validated. CIs empirically confirm Top-1 6.7% [1.7, 13.3] is
  unprovable at n=60 → lead with pool/MRR, regen n≈300. (gemini gt_in_pool has a documented
  reference-side ±2-case nuance; all ranking metrics match.) See `results_ledger.md`.
- **🚪 Publication gate — closing `mscd_demo`:** because the goal is to publish ONLY this
  repo, the old repo can be retired *only after* `--live` runs **fully self-contained from
  this repo**. That requires, still TODO: (1) **dockerize Neo4j** (`docker-compose`) +
  the IFC→graph ingestion path; (2) **migrate the AP IFC model file(s)** into
  `data/ifc_models/` (gitignored + documented; currently NOT migrated); (3) **model-adapter
  access** (G8 1.6G via gitignore+documented download / DVC, or an API inference path).
  Until these land, `mscd_demo` stays as the live-run fallback. The saved traces then
  become regression fixtures, not the only source of numbers.

**Sequencing (decided):** (1) offline `--from-traces` harness + thesis parity → (2) live
closeout (Neo4j docker + IFC migration + model access) = the gate to retire `mscd_demo` →
(3) P2/P1 (which run `--live`).
- **Pre-registration:** per-phase `protocol.md` committed to git *before* running
  (confirmatory vs exploratory).
- **[NEW] Synthetic-dataset-enhance:** regenerate a **larger clean held-out (~n=300)**
  from `synth_v0.5_ap` — n=60 makes Top-1 CI ±~6–7pp, unprovable. Cheap (synthetic).
- **[NEW] Leakage check:** split by **disjoint elements/regions, not just case-IDs**.
  Document the split. (Critical before any learned ranker.)
- **[NEW] Per-field confidence contract invariant:** every extracted attribute carries
  `{value, confidence, source}` (VLM logprob for categorical/text, OpenCV score for
  position, ResNet confidence for size, alignment confidence for schema-repaired values).
  This is the *enabling substrate* for P1 routing and closes `neurosym/README.md`
  limitations #4 + #10. Design it in `schemas/` + `service/` now, not later.
- **[NEW — Idea 3a] Offline optimal-fingerprint ceiling (do FIRST after the contract; near-free, reframes the paper).**
  Pure compute on the IFC graph + measured per-field reliabilities — **no training, no GPU,
  no new data.** Reframes P1 from "we added calibration" to "we *formulate* grounding as
  **constrained discriminative feature-selection** and show calibrated routing is its online
  approximation." For target *e*: confusable set C(*e*) = same-storey+ifc_class siblings;
  pick feature subset **S\*** = argmax discriminative_power(S) s.t. expected_recall(S) ≥ τ
  (joint reliability ≈ ∏ r(f) → the recall-vs-discrimination tension = why the live planner
  Unions not Intersects). Two runs: oracle r=1 (per-element ceiling vs uniform L4) +
  reliability-weighted (= P1 generalized per-subset); the gap = the prize P1 chases.
  Deliverable: `eval/fingerprint_ceiling.py` + ledger row + the §4 spine figure.
  **Gate for Idea 3b (learned selector):** only pursue if S\* beats the simple
  Union-above-reliability-threshold heuristic; if heuristic ~95% as good, the null is the finding.
  - **✅ DONE (2026-06-09) — both cuts.** First cut (`fingerprint_ceiling.py`): coarse 46 →
    attribute-optimal 13 (3.8×), all via `object_type`; plateaus at 2/60 unique. Second cut
    (`fingerprint_reliability.py`, +offline topology +reliability r(f)): topology adds only
    13→**12** (FILLS/CONNECTS homogeneous, ADJACENT_TO sparse) → **feature space saturated**;
    ∏r collapses to 0.009 if all hard-filtered → the 76→~13 gap is **reliability-bound**.
    **Idea-3b GATE RESULT = SKIP** (no feature-selection prize for a learned selector; the
    lever is P1 calibrated routing). Numbers + caveats in `results_ledger.md`.
    **Interpretation correction:** "feature space saturated" here means *the low-order
    relation-type features implemented in this AP export* are saturated. It does **not**
    retire richer spatial addressing. Thesis L3/L4 show that direction/subtype/distance/
    connection-degree/position-slot features remain the real topology prize.
  > **Cautions (write into the protocol):** (1) ceiling is on the same synthetic generator →
  > "optimal *given correct constraints*", same caveat as oracle, not "provably optimal";
  > (2) ∏ r(f) assumes feature/error **independence** — direction/position errors correlate;
  > model it or state as a limitation + sensitivity check; (3) needs **topology** computed
  > (offline geometry or Neo4j) — no GPU, but not zero-dependency.

- **[NEW — Idea 3c] Visual-topological spatial address (graph enrichment as a research module).**
  Research question: *Can we derive a canonical, graph-computable spatial address for each
  IFC element that is discriminative in BIM and recoverable from site image/floorplan
  evidence?* The unit of enrichment is no longer "more edge types"; it is a descriptor
  family with three tests: **IFC-computable**, **visually/floorplan recoverable**, and
  **information-bearing** over the confusable set.
  - **Descriptor families to test:** (1) anchor chains
    (`target → opening/host → host wall/slab → connected wall / generated cell / facade bay`);
    (2) ordinal / curvilinear coordinates (`host_axis_s`, rank from left/right, distance to
    nearest wall end/corner, between junctions, near T/L-junction); (3) local k-hop typed
    ego-graph signatures with distance/angle/degree/material/subtype bins; (4) landmark
    coordinates to stairs/elevators/core/gridlines/facade boundaries/corners/door clusters;
    (5) generated space cells from wall loops / floorplan segmentation, using
    `IfcRelSpaceBoundary` directly when exported and geometry-derived cells when not.
  - **Deliverable:** `eval/spatial_address_ceiling.py` reporting descriptor `coverage`,
    `median pool`, `Top-k/MRR rerank prize`, `extractability proxy`, and `stability risk`,
    plus a "spatial-address Pareto frontier" figure.
  - **Priority order:** host-axis ordinal/address slot → corner/junction/connection-degree
    + angle → generated cell/boundary → landmark/grid/facade bay → existing
    CONNECTS/ADJACENT/CONTINUOUS with distance/angle/subtype attributes.
  - **P1 integration:** descriptors enter the same confidence contract and are used as
    soft rerank / selective hard filters. A floorplan crop is an evidence-side noisy
    observation of this address, not a replacement for the IFC graph.

### P2 — Confidence-gated deterministic specialists (supporting system result)
Promote high-confidence OpenCV position / ResNet size from soft-rerank to *gated*
constraints (hard if confident, soft otherwise). Fastest mover; GT-in-Pool must stay
100%. Engineering, not a research claim.
- **[NEW — Idea 2a] Segmentation/classification as a *routed* specialist (ADOPT, scoped).**
  Same pattern as OpenCV/ResNet: a deterministic specialist that beats the VLM on its
  sub-task, **emits its own confidence, feeds the contract, and is routed by P1** — NOT
  dumped into the VLM prompt (a tool in the prompt ≠ a specialist in the architecture).
  Aim it at the **22% storey/floor errors** and the new spatial-address observations:
  a floorplan/region segmenter (SAM-style mask → region → storey/zone/generated cell/
  host-axis slot/landmark) with confidence. Hard storey filter if confident, soft prior else.
  > **Caution:** SAM is heavier than OpenCV/ResNet (model + GPU) — it is *not* "fast pure
  > engineering" like position/size gating; scope it as its own sub-task with the 22% metric.
- **Idea 2b — Floorplan→graph needs precise wording.** REJECTED: deriving the
  authoritative topology graph from a 2D floorplan as a replacement for IFC. ADOPTED:
  floorplan patch / annotation → evidence-side local graph or spatial-address observation
  aligned to the IFC graph (`cell`, `host_axis_s`, `ordinal_slot`, `landmark`, confidence).

### P1 — Calibrated field-routing + verified schema-alignment (MECHANISM under the spatial-address headline)
- Per-field confidence → role decision {hard filter / soft prior / drop / clarify};
  threshold-calibration first, optional tiny learned router.
- **Learned neural→symbolic interface ablation (where does learning pay?).** Make the
  probabilistic-extraction → strict-schema station an *ablatable stack*: Arm0 deterministic
  schema-alignment (Gusarov) · Arm1 **[A]** learned schema-constrained extractor (emits
  position-slot/object_type directly) · Arm2 **[B]** learned MLP adapter (raw VLM → calibrated
  schema fields) · Arm3 both. Score per-field acc + Top-k/MRR + **ECE** + repeatability;
  "[B] adds nothing once [A] is structured" is as publishable as the opposite. **Two rules keep
  it auditable:** (i) audit boundary = the structured `{field,value,confidence,source}` record
  (executor deterministic on it), not model internals; (ii) the learned layer is
  **constrained to the graph-attested vocabulary** (select/rank valid terms + emit confidence,
  cannot invent values) — this reconciles "learned" with "faithful execution" and upgrades
  schema-alignment to a *calibrated, vocabulary-constrained neural→symbolic adapter*. Order:
  [A] first (cut-3's binding gap), [B] after (may be redundant — test, don't assume).
  **[E] learned fusion/rerank (GNN-style) stays OUT** (gap isn't in fusion; auditability + leakage cost).
- **Two levers — the SOFT one is dominant (Idea-3a 2nd-cut correction, 2026-06-09).**
  The ∏r recall collapse binds **hard filtering only** (wrong hard filter evicts GT). The
  **soft confidence-weighted rerank** keeps GT in pool (recall stays 100%) and spends the
  unreliable signal on *ordering* — sidestepping the tension. Since realized GT-in-pool is
  already 100% but Top-1 6.7%/Top-10 30%, the bottleneck is **ranking inside the pool**, so
  soft rerank is the bigger prize. **Already implemented for 2 fields** (`size_band` ResNet
  conf + `position_context` OpenCV conf) in `graph_rag_rerank_ap.py:508`
  (`fusion = Σ score·conf / Σ conf`, hardcoded 0.7/0.8 weights). **P1 core work =
  generalize 2→all routable fields + replace hardcoded weights with CALIBRATED confidence.**
- Verified schema-alignment (embedding-sim + existence-check Cypher, **Gusarov-style,
  adopted as a component, NOT sold as novelty**) repairs each value to a graph-attested
  term and emits alignment confidence.
- **Gate on a calibration sanity-check first (ECE + reliability diagram)** — if
  confidences aren't calibrated, the routing premise fails.
- New diagnostic metric: live pool vs oracle L3 (9) → shows routing closes 76→9.
- **"Clarify"/defer = first-class outcome (selective prediction).** Report a
  **coverage-vs-accuracy curve** (accuracy at each defer rate), not just point accuracy —
  "here are 9 candidates, I'm unsure" beats a confident wrong Top-1, and *is* the triage
  value prop.
- **Adaptivity-arm ablation (home of the AI-agent orchestration idea).** Same backbone,
  three adaptivity levels: `static-threshold → tiny learned router → LLM-agent
  orchestrator` (agent reads extraction + confidences + *intermediate pool sizes*,
  decides which deterministic specialist to call / which constraint to relax — adaptive
  test-time compute over deterministic tools, NOT agent-as-grounding). Score accuracy
  **+ latency + repeatability**. Static is the headline; the agent must beat it on the
  same budget. "Agentic orchestration doesn't pay its latency" is itself a finding.

> **ECE-failure contingency (state up front):** out-of-the-box VLM token-probabilities
> are usually poorly calibrated. If the ECE gate fails, the gain shifts to
> schema-alignment + visual specialists carrying the load. Survivable, but name the risk
> rather than discovering it late.

### P4 — Subtype-contrastive data aug (reframed as a finding)
Add hard-negative subtype contrasts to the Blender pipeline; retrain a LoRA variant.
Frame around the **multi-task capacity tension** the thesis found (r=16 degrades
ifc_class when adding spatial supervision) — makes it a finding, not just augmentation.
- **Depth-policy synergy (measured):** the depth-saturation result says depth≥2 spatial
  supervision is wasted (realizable Δ≈0) and actively costs `ifc_class` capacity. So P4's
  first move is *subtractive*: drop depth≥2 chains, reallocate capacity to ifc_class +
  depth-1 descriptor (position-slot) extraction. Cheaper and better-motivated than adding aug.

### Cross-cutting (from red-team)
- **≥1 external baseline** (Text-to-Cypher à la Auto-Cypher/Gusarov, or dense/CLIP
  retrieval). "Beat our own ablations + zero-shot Gemini" is too weak alone.
- **Triage measurement** (even small: human/simulated time + success) — validates the
  "compress 1200→70 for triage" value prop, which Top-k does not.

### Tooling / skills (leverage where they add professionalism + accuracy)
Situational — adopt **only when the phase actually needs it**, and only if it helps; not now.
- **P1 fine-tuning → consider `/peft` + `/trl-fine-tuning`** (and `/axolotl` for a YAML-driven
  pilot config) when we do real per-project LoRA adaptation / preference (accept-reject) SFT
  from the G8 checkpoint. Recommended *if helpful* — they encode best practices (rank
  allocation, adapter merging, continued training) that raise rigor/accuracy.
- **P1/P2 experiment tracking → `/weights-and-biases`** once multiple adapter runs need
  comparison tables for the paper.
- **Do NOT pull in now / mind the misfits:** `/instructor` (+ constrained decoding) only
  enforces JSON *validity*, not the *semantic* field correctness that is our actual bottleneck —
  already DROPPED in ARCHIVE; `/grpo-rl-training` is overkill vs SFT for our signal; paper
  skills (`/systems-paper-writing`, `/academic-plotting`) belong to the deferred paper phase.
- **Repo-quality validation is not a skill** — it's `ruff` + a `pytest` parity-regression test
  + `/code-review` on new code.

### Execution order (each step gates the next; cheapest/framing-defining work before GPU spend)

| # | Step | Phase | Why here / what it gates |
|---|---|---|---|
| 1 | Scaffold + **confidence contract** + leakage-safe split + **DATA AUDIT** | Phase 0 | contract is the routing substrate. **n≈300 regeneration demoted** (Top-1 demoted → pool/MRR/per-field fine at n=60); audit first (leakage + verify `position_context`/`object_type` GT), regenerate/refactor only if the audit exposes a real defect. Pre-register `protocol.md`. |
| 2 | **Idea 3a — fingerprint ceiling** ✅ DONE (3 cuts + depth-saturation, 2026-06-09) | Phase 0 | two complementary discriminators (`position_context`→Top-1, `object_type`→Top-10), both unextracted-as-structured; discrimination saturates at **depth-1**. See §1 measured block + `results_ledger.md`. |
| 3 | **Idea 3c — visual-topological spatial address ceiling** | Phase 0/1 | compute host-axis ordinal, junction/corner, generated cell, landmark/grid/facade-bay descriptors before training; decide which address fields deserve P2/P1 support. |
| 4 | **P2** — gate position/size + **Idea 2a** segmentation/floorplan-address specialist | P2 | adds routable fields (storey/zone/cell/host-axis slot/landmark/object_type); GT-in-pool stays 100%; precedes P1. |
| 5 | **P1** — calibrated field-routing + schema-alignment | P1 | the headline. Needs contract (1), prize gaps (2–3), specialists (4). **Gate on ECE/reliability first.** |
| 6 | **P1 adaptivity ablation** (static → learned → agent, Idea 1) | P1 | only after static router works (it's the baseline the agent must beat). Apply Guardrail 1 (steelman) + 2 (measure repeatability). |
| 7 | **P4** — subtype-contrastive data aug | P4 | slowest loop; last; benefits from calibrated pipeline being in place. |
| + | **Depth policy (measured): inference extract at depth ≤1** | Phase 0/P2 | depth-saturation: realizable discrimination saturates at depth-1. Stop training depth≥2 chains (frees adapter capacity → recovers `ifc_class`); compile depth into node-level spatial address. Allow depth-1-to-landmark only when the anchor is independently grounded. |
| — | ~~Idea 3b (learned feature *selector*)~~ **RETIRED** | — | features are known/named (`position_context`, `object_type`) → no need for a learned *selector* to discover them. 3c's address-family search (walls/non-filler fingerprints) is separate and continues at step 3. |
| — | P3 (GNN rerank) / learned fusion [E] | optional / out | demoted; low novelty + leakage risk; cut-3 shows the gap is extraction, not fusion. |

**Cross-cutting (run alongside, required before submission):** ≥1 external baseline
(Text-to-Cypher / dense-CLIP) + a small triage measurement.

> **Note on actual order:** the live-closeout (Neo4j docker + IFC ingestion + model access)
> is a parallel Phase-0 track gating `--live` and the retirement of `mscd_demo` (see
> `STATUS.md` + `DATA_INVENTORY.md`); it is not in the research execution order above but
> must land before any step that needs `--live` re-runs (P2 onward).

---

## 3. Open decisions
- Large-file strategy: gitignore + documented paths now; DVC/LFS later if needed. (default)
- **Venue:** synthetic-only likely too weak for *Automation in Construction* (applied).
  Either get a 20–30 case real "case study" (easier than a benchmark) to unlock AuC, or
  target a methods/analysis venue / workshop. **Decide before paper writing.**

---

## 4. Deferred — storytelling / demo (technical first)
Web live demo from old `mscd_demo/demo`, refactored into a thin front-end over
`src/aec_interpreter/service`. Input image/text → highlighted element + heatmap. Doubles
as a future real-data collection funnel. Grasshopper plugin = optional, not primary.

---

## Source Anchors
- Thesis: `D:\ahYen Workspace\ahYen Work\CMU_academic\MSCD_Thesis\final_submit\Chia Hui Yen_MSCD_Thesis.pdf`,
  especially Ch.6.1.3 (IFC enrichment), Ch.7.1.2 / Table 7.1 (oracle ladder), Ch.7.2.2
  (topology interpretation), and Ch.8.4 (floorplan patches as bridge modality).
- buildingSMART `IfcRelSpaceBoundary`: element-space boundary + optional boundary geometry.
  https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcRelSpaceBoundary.htm
- buildingSMART `IfcRelConnectsPathElements`: path-element connectivity with connection
  type/geometry. https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcRelConnectsPathElements.htm
- buildingSMART `IfcRelFillsElement`: opening/filling relation for doors/windows.
  https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcRelFillsElement.htm
- Floorplan topology analogue: https://arxiv.org/abs/2204.12338
- SAM as segmentation candidate, not novelty claim: https://arxiv.org/abs/2304.02643
- Calibration basis for P1: https://arxiv.org/abs/1706.04599
- Multi-hop KGQA error compounding (justifies depth ≤1): https://arxiv.org/abs/2404.19234
- Neuro-symbolic division of labor — neural perception + symbolic executor (Mao NS-CL,
  justifies "compile depth into the node, extract shallow"): https://arxiv.org/abs/1904.12584

---

## Validity guardrails (carry into every phase)
- **n is small.** Always report bootstrap CIs; lead with pool-compression + MRR, not Top-1.
- **Oracle is not "provably correct."** Oracle uses GT constraints from the same
  synthetic generator → claim "faithful execution given correct constraints," not
  "architecture provably correct."
- **Leakage.** Re-verify disjoint elements/regions whenever a learned component is added.
- **Pre-register** confirmatory metrics before each run; mark post-hoc results exploratory.

## Dropped ideas
See the ARCHIVE section of the planning note (`AEC Interpreter - enhanced module.md`)
for every dropped idea with its reason (agent-as-grounding, agent spectrum study as
headline, GNN headline, schema-alignment as novelty, SpatialVQA reframe, bigger backbone,
MLP-in-symbolic, constrained decoding, P0 real-data, 116-unified). **Added 2026-06-09:**
deep multi-hop extraction at inference (depth≥2 — measured: realizable Δ≈0 beyond depth-1,
hop-2 extraction 5%, hurts −13pp); learned feature *selector* (Idea 3b — features are
known/named); learned fusion layer [E] (gap is extraction, not fusion); three co-equal
spine pillars (scope-creep → one line: address=headline, routing=mechanism, agent=ablation).
