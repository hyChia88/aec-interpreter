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
| Policy-adaptivity | how smart must the router be? | agent vs learned vs static (Idea 1) | P1 ablation arm |
| **Routing** *(headline)* | per-field confidence → {hard/soft/drop/clarify} | P1 calibrated field-routing | HEADLINE |
| Evidence | which deterministic specialists feed the contract | segmentation/classification specialist (Idea 2a) | P2 extension |
| Feature-selection | which feature *subset* uniquely+reliably IDs an element | optimal discriminative fingerprint (Idea 3) | Phase 0 (3a) + theory of P1 |

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
  > **Cautions (write into the protocol):** (1) ceiling is on the same synthetic generator →
  > "optimal *given correct constraints*", same caveat as oracle, not "provably optimal";
  > (2) ∏ r(f) assumes feature/error **independence** — direction/position errors correlate;
  > model it or state as a limitation + sensitivity check; (3) needs **topology** computed
  > (offline geometry or Neo4j) — no GPU, but not zero-dependency.

### P2 — Confidence-gated deterministic specialists (supporting system result)
Promote high-confidence OpenCV position / ResNet size from soft-rerank to *gated*
constraints (hard if confident, soft otherwise). Fastest mover; GT-in-Pool must stay
100%. Engineering, not a research claim.
- **[NEW — Idea 2a] Segmentation/classification as a *routed* specialist (ADOPT, scoped).**
  Same pattern as OpenCV/ResNet: a deterministic specialist that beats the VLM on its
  sub-task, **emits its own confidence, feeds the contract, and is routed by P1** — NOT
  dumped into the VLM prompt (a tool in the prompt ≠ a specialist in the architecture).
  Aim it at the **22% storey/floor errors**: a floorplan/region segmenter (SAM-style mask →
  region → storey/zone) with confidence. Hard storey filter if confident, soft prior else.
  > **Caution:** SAM is heavier than OpenCV/ResNet (model + GPU) — it is *not* "fast pure
  > engineering" like position/size gating; scope it as its own sub-task with the 22% metric.
- **Idea 2b — Floorplan→graph (deriving topology from 2D): REJECTED (moat regression).**
  The IFC graph is already zero-error ground-truth topology = the auditability moat. Parsing
  topology from floorplans reintroduces the extraction error we eliminated. Floorplan stays
  on the **evidence/input** side only (2a), never as a graph source.

### P1 — Calibrated field-routing + verified schema-alignment (HEADLINE)
- Per-field confidence → role decision {hard filter / soft prior / drop / clarify};
  threshold-calibration first, optional tiny learned router.
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
| 1 | Scaffold + **confidence contract** + larger held-out (n≈300) + leakage-safe split | Phase 0 | nothing is routable/measurable without the `{value,confidence,source}` contract and CI-usable test set. Pre-register `protocol.md`. |
| 2 | **Idea 3a — offline optimal-fingerprint ceiling** ✅ DONE (both cuts, 2026-06-09) | Phase 0 | produced the ceiling (coarse 46→13, +topology→12 = saturated) + §4 figures; defined the prize as **reliability-bound**; gate fired → **Idea 3b SKIP**. |
| 3 | **P2** — gate position/size + **Idea 2a** segmenter | P2 | fastest mover, GT-in-pool stays 100%; adds routable fields (incl. 22% storey fix) that P1 then routes → precedes P1. |
| 4 | **P1** — calibrated field-routing + schema-alignment | P1 | the headline. Needs contract (1), prize gap (2), specialists (3). **Gate on ECE/reliability first.** |
| 5 | **P1 adaptivity ablation** (static → learned → agent, Idea 1) | P1 | only after static router works (it's the baseline the agent must beat). Apply Guardrail 1 (steelman) + 2 (measure repeatability). |
| 6 | **P4** — subtype-contrastive data aug | P4 | slowest loop; last; benefits from calibrated pipeline being in place. |
| — | Idea 3b (learned fingerprint selector) | ❌ RETIRED (2026-06-09) | step-2 gate fired SKIP: feature space saturated (attr-oracle 13 ≈ attr+topo 12), so no feature-selection prize; the recoverable gap is reliability-bound → P1's job, not a learned selector. |
| — | P3 (GNN rerank) | optional | demoted; low novelty + leakage risk. |

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
MLP-in-symbolic, constrained decoding, P0 real-data, 116-unified).
