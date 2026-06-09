# RESULTS LEDGER

> Every reported number lands here, once, with provenance. If a number isn't in this
> ledger it doesn't go in the paper. Append-only; never silently edit a past row.

Conventions:
- **Always** report bootstrap 95% CI for rate metrics (n is small).
- Mark each row **confirmatory** (pre-registered in that phase's `protocol.md`) or
  **exploratory** (post-hoc).
- `run_id` ties back to `output/<run_id>/` and the git `commit` it was produced at.

---

## Baselines / thesis-carried numbers (for reference, AP held-out n=60)

| metric | value | source |
|---|---|---|
| oracle GT-in-Pool | 100% | thesis Table 7.1 |
| oracle Top-10 (L3) | 58.3% | thesis Table 7.1 |
| oracle Top-10 (L4) | 100% (58.3% cov) | thesis Table 7.1 |
| realized GT-in-Pool | 100% | thesis Table 7.2 (G8) |
| realized Top-10 | ~30% | thesis Table 7.2 (G8) |
| realized Top-1 | ~6.7% | thesis Table 7.2 (G8) |
| realized MRR@10 | ~0.11 | thesis Table 7.2 (G8) |
| realized median pool | ~76 | thesis Table 7.2 (G8) |

> These are carried from the thesis for orientation only. Re-run on this repo's harness
> before citing as "our system" numbers (toolchain/version may differ).

---

## Metric definitions (this repo's clean scorer — `eval/run_benchmark.py`)

- **GT** = `scenario.ground_truth.target_guid`.
- **GT-in-pool** = GT present in the retrieved candidate pool
  (union of `internals.retrieval_results[*].candidates[*].guid`). Recall ceiling.
- **Top-k / MRR** = 1-based rank of GT in `interpreter_output.candidates` (the ≤10 reranked
  shortlist); MRR = mean reciprocal rank (0 if GT absent from shortlist).
- **pool size** = `final_pool_size` per case → mean **and** median (thesis "pool ~76" = median;
  mean = 118.4). Initial pool + search-space reduction reported too.
- All rates carry **bootstrap 95% CIs** (default 10 000 resamples, seed 0).

> **Parity note (gemini gt_in_pool):** the frozen thesis JSON reports gemini gt_in_pool 91.7%;
> this repo's clean union-of-pool definition gives 95.0% (+2 cases). All *ranking* metrics
> (Top-1/5/10, MRR, pool mean/median) reproduce exactly. The 2-case gap is a reference-side
> accounting quirk in the legacy gemini scorer (not reproduced on purpose — the clean
> definition is more defensible). G8 canonical matches on all 7 metrics exactly.

## Run log

| date | phase | run_id | commit | test set (n) | metric | value | 95% CI | conf/expl | notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-08 | 0 | from-traces:g8_posctx_dim | b87ef4b+ | AP held-out (60) | Top-10 | 30.0% | [18.3, 41.7] | confirmatory | **parity PASS** vs thesis (all 7 metrics exact); `python eval/run_benchmark.py --variant g8_posctx_dim` |
| 2026-06-08 | 0 | from-traces:g8_posctx_dim | b87ef4b+ | AP held-out (60) | MRR@10 | 0.1104 | [0.053, 0.181] | confirmatory | same run |
| 2026-06-08 | 0 | from-traces:g8_posctx_dim | b87ef4b+ | AP held-out (60) | final pool (median) | 76.0 | [61, 78] | confirmatory | mean 118.4 [92.7, 146.8] |
| 2026-06-08 | 0 | from-traces:g8_posctx_dim | b87ef4b+ | AP held-out (60) | Top-1 | 6.7% | [1.7, 13.3] | confirmatory | CI shows Top-1 unprovable at n=60 → demote, regen n≈300 |
| 2026-06-08 | 0 | from-traces:gemini_ap_v2 | b87ef4b+ | AP held-out (60) | Top-10 | 18.3% | [8.3, 28.3] | confirmatory | ranking-metrics parity PASS; gt_in_pool known-diff (see note) |

## Idea 3a — optimal-fingerprint ceiling (FIRST CUT: attribute layer, oracle r=1, Neo4j-free)

`eval/fingerprint_ceiling.py` over `element_index.jsonl` (universe = 1233 AP elements;
60 held-out targets). Confusable set C(e) = elements sharing e's fingerprint.

| pool (60 targets) | median | mean | min..max |
|---|---|---|---|
| coarse (storey+ifc_class) | 46 | 112.4 | 14..362 |
| attribute-optimal (oracle r=1) | **13** | 35.1 | 1..260 |

- **3.8× median shrinkage** from attribute feature-selection alone (no topology).
- **`object_type` does essentially all of it** (coarse+object_type → median 13; material /
  fire_rating / is_external add ~0 at the margin). `space_name`/`target_name_keyword`/
  `neighbor_type` are dead for AP (≈0% coverage).
- **Attributes plateau:** only **2/60** uniquely identified by attributes alone → topology
  features are required to approach Top-1 / oracle-L3 (~9). Motivates the topology cut + P1.

> **Caveats:** (1) universe = element_index (1233) ≠ live graph (1666) + finer live
> ifc_class granularity → absolute |C| ≠ live pool 76; the *relative* shrinkage is the
> result. (2) Oracle r=1 = upper bound; `object_type` is a Revit family/type string whose
> real photo-extraction reliability is likely low, so the **reliability-weighted cut (next)**
> will show a realizable floor well above 13 — that gap is the prize P1 chases. (3) Topology
> features pending (offline-geometry edge table, Neo4j-free) = second cut.

Figure: `output/fingerprint_ceiling.png` (coarse vs attribute-optimal distributions) → §4 spine visual.

## Idea 3a — SECOND CUT: topology features + reliability-weighting → prize gap + 3b gate

`eval/fingerprint_reliability.py` over `element_index.jsonl` (deduped by GUID → **852**
unique; raw 1233 double-counts IfcWall/IfcWallStandardCase). Adds offline (Neo4j-free)
topology features (ADJACENT_TO neighbour-class signature + CONTINUOUS spanning, same
geometry as `scripts/graph_build/02_add_topology_edges.py`) and per-field extraction
reliability r(f) from `mscd_demo/results.md` U3/Group-3.

**Oracle ceiling — feature space is SATURATED:**

| pool (60 held-out targets, r=1) | median |
|---|---|
| coarse (storey+class) | 46 |
| attribute-optimal | 13 |
| **attr + topology (full oracle)** | **12** |

- Topology adds only **1** element of shrinkage over attributes (13→12).
- **FILLS / CONNECTS_TO are type-level homogeneous** (389 FILLS = all windows/doors→walls;
  686 CONNECTS = all wall↔wall) → zero discrimination at the granularity a photo can
  extract. ADJACENT_TO is sparse (36/60 targets have **no** neighbour; 12 distinct
  signatures building-wide). Discriminative topology needs a *named* neighbour (multi-hop;
  thesis hop-2 predicate reliability ≈ 0.05).

**Reliability bind (the recall↔discrimination tension, quantified):** per-field r ≈
storey 0.66, ifc_class 0.50, object_type 0.625 (rest unmeasured/≈0 power). Joint recall if
a feature subset is hard-filtered ≈ ∏r(f):

| hard-filtered subset | oracle pool | ∏r recall |
|---|---|---|
| storey | 141 | 0.66 |
| + ifc_class (= coarse) | 46 | 0.33 |
| + object_type | 13 | 0.21 |
| all 8 features | 12 | 0.009 |

- **No hard filter sustains 90% recall** — even storey alone is 0.66. This is *why* the
  live planner UNIONs (soft) instead of INTERSECTs (hard): hard-filtering destroys recall,
  so the realized pool stays at ~76 despite a 12–13 oracle ceiling.
- **Calibrated single-feature recovery** (no compounding): `object_type` is the *only*
  feature with both discrimination and r>0.5. Perfectly calibrated routing on it alone:
  E[|C|] = 0.625·13 + 0.375·46 = **25.4** (coarse 46 → 25 ≈ half the 46→13 gap). Every
  other feature recovers 0 (no power or r≤0.5).

**Idea-3b GATE → SKIP.** The feature space is saturated (attr-oracle 13 ≈ attr+topo-oracle
12), so there is no feature-*selection* prize for a learned selector to win. The entire
recoverable gap (76 → ~13) is **reliability-bound**, so the correct lever is **P1
calibrated routing** (hard-filter per-instance only when confidence warrants), not Idea 3b.
This is the decisive output of the cut: it retires Idea 3b and points all effort at P1.

> **Caveats:** (1) r(f) are best-available per-field proxies (LoRA5 / Group-3 MC, n=70; G8
> not separately tabulated) — they set the *shape*, the live ECE study (P1) replaces them
> with per-instance confidence. (2) ∏r assumes independent per-field errors → upper bound
> on the recall penalty (the live system also unions over P0∪P1 strategies, which is why
> realized GT-in-pool is 100% despite low ∏r). (3) deduped universe 852 ≠ live 1666 →
> compare ratios, not absolute |C| vs live pool 76.

Figure: `output/fingerprint_reliability.png` (oracle pool ↓ vs joint recall ∏r ↓ along the
greedy frontier — the scissors crossing = the reliability bind) → §4 core figure.

**Raw-IFC relationship census (does saturation hold against ALL physical relations?):**
full `IfcRel*` census of `AdvancedProject.ifc`: material 1345 (have), CONNECTS_TO 686
(have, all wall↔wall), FILLS 389 (have, all window/door→wall), type 202 (have →
object_type), MEP ports 139 (irrelevant), aggregates 17 (tiny), storey-containment 10
(have). **`IfcRelSpaceBoundary` = 0; only 8 `IfcSpace`s with non-semantic names
("3ROK"/"5ROK"/"Area").** → no untapped discriminative+extractable relation in this file;
saturation holds **for this building**. ⚠️ **Caveat (threats-to-validity):** saturation is
a property of this homogeneous synthetic mock-up with *no exported space boundaries*, not
of the method. On a real project IFC with `IfcRelSpaceBoundary` + named rooms,
"element bounds room X" would be discriminative **and** photo-extractable — the first
feature to revisit on real data, and the reason `space_name` is 0% here.

**Two levers, and |C| under-counts the prize — correction to the prize-gap above.** The
∏r collapse binds **hard filtering only** (a wrong hard filter evicts GT → recall loss).
**Soft confidence-weighted rerank sidesteps the tension**: keep GT in pool (UNION, recall
100%), spend the unreliable signal on *ordering* only. The binding metric is NOT pool size
— realized **GT-in-pool = 100%** already, yet **Top-1 6.7% / Top-10 30%**, so the
bottleneck is ranking *inside* the pool. The |C|-based prize (46→25.4) models only the
hard-gate lever; the **soft-rerank lever (→ Top-k/MRR) is dominant and is already
implemented for 2 fields** (`graph_rag_rerank_ap.py:508` `_candidate_match_signals`:
`fusion = Σ score·conf / Σ conf` over `size_band` (ResNet conf) + `position_context`
(OpenCV/F4 conf), with hardcoded 0.7/0.8 default weights). **P1 = generalize 2→all routable
fields + replace hardcoded defaults with calibrated confidence (ECE gate).**

## Idea 3a — THIRD CUT: soft-rerank prize on Top-k / MRR (offline, real pools)

`eval/rerank_prize.py` reranks the **real G8 trace pools** (median 76, GT-in-pool 60/60)
by feature agreement — each pool guid joined to `element_index.jsonl` for its features,
expected Top-k/MRR with analytic tie handling. This sizes the prize on the *binding* metric
(ranking) instead of |C|. **Observed extraction reliability from the traces: storey 0.52,
ifc_class 0.82** (real G8 per-set numbers; refines cut-2's documented LoRA5 proxies 0.66/0.50).

| scheme (60 cases) | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|
| realized (G8) | 6.7 | 16.7 | **30.0** | 0.110 |
| blind rerank (storey+class, 2-field) | 3.3 | 9.8 | 15.7 | 0.084 |
| calibrated rerank (zero wrong fields) | 3.7 | 11.8 | 19.6 | 0.098 |
| oracle storey+class (perfect coarse) | 4.9 | 17.9 | 31.5 | 0.137 |
| **realistic +object_type (r=0.625)** | **13.2** | **40.2** | **59.5** | **0.271** |
| oracle +object_type (r=1 ceiling) | 18.1 | 53.6 | 76.3 | 0.352 |

- **Coarse is saturated:** oracle storey+class (31.5) ≈ realized (30.0) — perfecting the
  fields the model already extracts barely moves Top-10. Consistent with cut-1 (coarse pool 46).
- **The prize is object_type** (cut-2's sole discriminator, which the pipeline does NOT yet
  extract): oracle +object_type lifts Top-10 30→**76** (+45pp ceiling), Top-1 6.7→18.
- **Realistic estimate** (object_type specialist at r=0.625 + calibrated soft rerank;
  E = r·oracle + (1−r)·coarse): Top-10 **59.5** (≈2× realized), Top-1 **13.2** (≈2×), MRR
  0.271 (2.5×) — **with zero recall cost** (soft rerank never evicts GT).
- **Calibration prize, isolated** (controlled 2-field): zeroing wrong-extraction weights
  beats confidence-blind rerank by **+3.9pp** Top-10 — small here because only storey+class
  participate, but it's the real per-field effect P1 calibration exploits across all fields.

> **Caveats:** (1) blind/calibrated rows use ONLY storey+class to isolate the calibration
> effect → they sit *below* realized_g8, which uses the full pipeline (spatial relations +
> Gemini rerank + name hints); do NOT read blind<realized as "rerank hurts". (2) object_type
> oracle r=1 is a ceiling; r=0.625 is the cut-2 proxy (Revit family-type string, hard to read
> from a photo) — the realistic row is the defensible number. (3) the realistic-row fallback
> assumes calibration is good enough to revert to coarse when object_type is wrong (rather
> than be misled) — that is exactly the P1 premise, gated on the ECE study.

**Net story (cuts 1–3):** grounding is reliability-bound, not feature-bound; the one
discriminator (object_type) is unextracted; extracting it (**P2 specialist**) + calibrated
**soft rerank** (**P1**) ≈ doubles Top-10/Top-1 with no recall loss. This is the paper's
money figure and the justification for the P2→P1 order. Idea 3b stays retired.

Figure: `output/rerank_prize.png` (Top-1/Top-10 across schemes — the elbow at object_type).
