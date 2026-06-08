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

**Spine claim:** *In determinism-constrained, high-repetition IFC retrieval, the binding
constraint is field-level extraction confidence; calibrated field-routing recovers a
measurable fraction of the oracle–realized gap.*

---

## 2. Phases

Test set = **AP held-out only** (116-unified dropped, flawed). Primary metrics =
**pool-compression (76→9) + MRR@10 + per-field extraction accuracy** (more power than
Top-1 at small n). Latency/cost tracked first-class. Top-1 reported but demoted.

### Phase 0 — Foundation (new clean monorepo + harness)  ← CURRENT
- New clean monorepo (datagen + system + eval + demo). Old 3 components frozen as
  thesis-submission archive. Migrate ONLY canonical assets (`synth_v0.5_ap`,
  `lora6_v2_ap_20260331`, AP held-out, `src/{neurosym,visual,common,handoff}`,
  refactored `schema/`, prompts, `ifc-bonsai-mcp` as datagen tool).
- `docs/`: ROADMAP, DATA_INVENTORY, REPO_MAP, results_ledger.
- `src/aec_interpreter/service/` (pipeline as callable + FastAPI, shared by demo+eval)
  + `eval/run_benchmark.py` (bootstrap CIs).
- **Pre-registration:** per-phase `protocol.md` committed to git *before* running
  (confirmatory vs exploratory).
- **[NEW] Synthetic-dataset-enhance:** regenerate a **larger clean held-out (~n=300)**
  from `synth_v0.5_ap` — n=60 makes Top-1 CI ±~6–7pp, unprovable. Cheap (synthetic).
- **[NEW] Leakage check:** split by **disjoint elements/regions, not just case-IDs**.
  Document the split. (Critical before any learned ranker.)

### P2 — Confidence-gated deterministic position/size (supporting system result)
Promote high-confidence OpenCV position / ResNet size from soft-rerank to *gated*
constraints (hard if confident, soft otherwise). Fastest mover; GT-in-Pool must stay
100%. Engineering, not a research claim.

### P1 — Calibrated field-routing + verified schema-alignment (HEADLINE)
- Per-field confidence → role decision {hard filter / soft prior / drop / clarify};
  threshold-calibration first, optional tiny learned router.
- Verified schema-alignment (embedding-sim + existence-check Cypher, **Gusarov-style,
  adopted as a component, NOT sold as novelty**) repairs each value to a graph-attested
  term and emits alignment confidence.
- **Gate on a calibration sanity-check first (ECE + reliability diagram)** — if
  confidences aren't calibrated, the routing premise fails.
- New diagnostic metric: live pool vs oracle L3 (9) → shows routing closes 76→9.

### P4 — Subtype-contrastive data aug (reframed as a finding)
Add hard-negative subtype contrasts to the Blender pipeline; retrain a LoRA variant.
Frame around the **multi-task capacity tension** the thesis found (r=16 degrades
ifc_class when adding spatial supervision) — makes it a finding, not just augmentation.

### Cross-cutting (from red-team)
- **≥1 external baseline** (Text-to-Cypher à la Auto-Cypher/Gusarov, or dense/CLIP
  retrieval). "Beat our own ablations + zero-shot Gemini" is too weak alone.
- **Triage measurement** (even small: human/simulated time + success) — validates the
  "compress 1200→70 for triage" value prop, which Top-k does not.

**Sequence:** Phase 0 → P2 → P1 (+calibration check) → P4. P3 (GNN) only optional ablation.

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
