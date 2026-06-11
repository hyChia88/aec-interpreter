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

> ⚠️ **SUPERSEDED (2026-06-09) — this cut omitted `position_context`.** The "saturated"
> claim below is over `element_index.jsonl` features + my re-derived ADJACENT_TO/CONTINUOUS
> **only**. It missed the `ifc_engine` NEXT_TO position-slot (`wall_position_index` /
> `wall_child_total` = `position_context`), which lives only in the enriched Neo4j graph,
> not the flat index. The THIRD CUT (corrected) shows position_context is in fact the
> dominant Top-1 discriminator (thesis L4 "pool=1 for 35 cases"). So the feature space is
> **NOT** saturated, and the gap is **feature-AND-reliability bound** (the discriminators
> exist — object_type, position slot — but the model doesn't extract them as structured
> fields). The "∏r reliability bind" finding (below) still stands for *hard filtering*; the
> soft-rerank lever is where position_context pays off.

**Oracle ceiling over element_index attributes + low-order topology (position_context EXCLUDED):**

| pool (60 held-out targets, r=1) | median |
|---|---|
| coarse (storey+class) | 46 |
| attribute-optimal | 13 |
| **attr + ADJACENT_TO/CONTINUOUS (full)** | **12** |

- Within *this* (incomplete) feature set, topology adds only **1** element of shrinkage (13→12).
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

**Idea-3b GATE → still SKIP, but for a CORRECTED reason (2026-06-09).** Original (wrong)
reason: "feature space saturated." Corrected reason: the discriminative features are now
**known and named** — `object_type` (attribute) and `position_context` (the NEXT_TO slot,
thesis L4) — and both are already wired into the retrieval Cypher + reranker. So there is no
need for a *learned selector to DISCOVER* unknown features (Idea 3b); the lever is **extract
them as structured fields (P2 specialists) + calibrated soft rerank (P1)**. 3b stays deferred
not because no feature helps, but because *which* features help is already established.

> **Caveats:** (1) r(f) are best-available per-field proxies (LoRA5 / Group-3 MC, n=70; G8
> not separately tabulated) — they set the *shape*, the live ECE study (P1) replaces them
> with per-instance confidence. (2) ∏r assumes independent per-field errors → upper bound
> on the recall penalty (the live system also unions over P0∪P1 strategies, which is why
> realized GT-in-pool is 100% despite low ∏r). (3) deduped universe 852 ≠ live 1666 →
> compare ratios, not absolute |C| vs live pool 76.

Figure: `output/fingerprint_reliability.png` (oracle pool ↓ vs joint recall ∏r ↓ along the
greedy frontier — the scissors crossing = the reliability bind) → §4 core figure.

**Raw-IFC relationship census (does low-order saturation hold against implemented physical relations?):**
full `IfcRel*` census of `AdvancedProject.ifc`: material 1345 (have), CONNECTS_TO 686
(have, all wall↔wall), FILLS 389 (have, all window/door→wall), type 202 (have →
object_type), MEP ports 139 (irrelevant), aggregates 17 (tiny), storey-containment 10
(have). **`IfcRelSpaceBoundary` = 0; only 8 `IfcSpace`s with non-semantic names
("3ROK"/"5ROK"/"Area").** → no untapped discriminative+extractable **low-order
relationship type** in this file; saturation holds **for this AP export and this descriptor
granularity**. ⚠️ **Caveat / correction (2026-06-09):** this does **not** mean topology
enrichment is exhausted. Thesis Table 7.1 shows L3/L4 gains come from richer fingerprints
(`direction`, `subtype`, `material`, `distance`, `connection_degree`, exact position slot),
not from predicate-object edges alone. On a real project IFC with `IfcRelSpaceBoundary` +
named rooms, "element bounds room X" could be discriminative **and** photo-extractable.
Even when spaces are unnamed (as in AP), geometry-derived cells, host-axis position,
junction/corner descriptors, and landmark/grid/facade-bay addresses remain open
spatial-address features to test.

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

**CORRECTED (2026-06-09)** to include `position_context` — the `ifc_engine` NEXT_TO slot
reconstructed offline (`eval/reconstruct_position_index.py`, 321 fillers on multi-filler
walls; **35/60 held-out targets addressable**). The original table credited only object_type
and wrongly called it "the prize."

| scheme (60 cases) | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|
| realized (G8) | 6.7 | 16.7 | 30.0 | 0.110 |
| oracle storey+class (perfect coarse) | 4.9 | 17.9 | 31.5 | 0.137 |
| oracle +object_type (r=1) | 18.1 | 53.6 | 76.3 | 0.352 |
| **oracle +position_context (r=1)** | **56.5** | 69.1 | 75.6 | **0.632** |
| **oracle all (both)** | **61.7** | **76.8** | **85.6** | **0.692** |
| realistic +object_type (r=0.625) | 13.2 | 40.2 | 59.5 | 0.271 |

- **Coarse is saturated:** oracle storey+class (31.5) ≈ realized (30.0).
- **Two complementary discriminators, both currently unextracted-as-structured:**
  - **`position_context` dominates Top-1**: +51.6pp over coarse → Top-1 **56.5%** (≈ the
    35/60 addressable targets going to pool≈1 — the thesis L4 "pool=1 for 35 cases" unlock,
    `results.md:413`). It nails *precision* (exact slot → unique on the host wall).
  - **`object_type` lifts Top-5/10 broadly**: Top-10 30→76 (+45pp). It improves *recall into
    the shortlist* (family-type narrows the field) but barely moves Top-1.
  - **Combined (oracle all): Top-1 61.7, Top-10 85.6, MRR 0.692** — they stack.
- **All gains are soft-rerank gains → zero recall cost** (GT never evicted).
- The realistic object_type row (r=0.625) stays as a defensible single-feature estimate
  (Top-10 59.5 ≈ 2×). A realistic position_context row awaits a *structured* slot extractor —
  G8 emits position as free text, not an integer (`results.md:453`), which is exactly why
  realized Top-1 is only 6.7% despite the 56.5% oracle. **That structured extractor is the
  single highest-value P2 specialist.**

> **Caveats:** (1) position_context oracle r=1 is a ceiling; the realizable number needs a
> structured slot specialist (the open thesis unlock) — but even partial extraction helps via
> soft rerank with no recall cost. (2) position-slot reconstruction replicates
> `ifc_engine._create_next_to_edges` (wall-axis projection of co-fillers); the live OpenCV
> path computes it from the photo. (3) blind/calibrated 2-field rows (see JSON) sit below
> realized_g8 by construction — do not read as "rerank hurts".

**Net story (cuts 1–3, corrected):** the bottleneck is *ranking*, and it is **both** a
feature-availability and a reliability problem — the two discriminators that solve it
(`position_context` for Top-1, `object_type` for Top-5/10) **exist in the IFC graph but are
not extracted as structured fields**. Extracting them (**P2 specialists**, position-slot
first) + calibrated **soft rerank** (**P1**) takes the oracle to Top-1 62 / Top-10 86 with
zero recall loss. This is the paper's money figure and the justification for the P2→P1 order.
Idea 3b (learned feature *selector*) stays deferred — the features are known, not to be
discovered. (`Idea 3c` will widen the position-slot into a general visual-topological address.)

Figure: `output/rerank_prize.png` (Top-1/Top-10 across schemes — position_context is the
Top-1 elbow; object_type the Top-10 elbow).

## Idea 3c — visual-topological spatial address (planned diagnostic)

New research module opened after reviewing the thesis + 3a caveats. The goal is not to
add arbitrary relationship labels, but to compute canonical IFC-derived descriptors that are
both discriminative in the BIM graph and recoverable from site image/floorplan evidence.

Candidate descriptor families:
- host/anchor chain: target → opening/host → host wall/slab → generated cell / connected
  wall / facade bay;
- ordinal/curvilinear host coordinate: `host_axis_s`, rank from left/right, distance to
  nearest wall end/corner, between junctions, near T/L-junction;
- local typed ego-graph signature with distance/angle/degree/material/subtype bins;
- landmark coordinates to stairs/elevators/core/gridlines/facade/corners/door clusters;
- generated unnamed space cells from wall loops / floorplan segmentation, using
  `IfcRelSpaceBoundary` directly if exported.

Planned output: `eval/spatial_address_ceiling.py` with `coverage`, `median pool`,
`Top-k/MRR rerank prize`, `extractability proxy`, and `stability risk`. This diagnostic
decides which address fields enter P2 specialists and P1 calibrated routing.

### FIRST CUT (2026-06-09) — wall/non-filler fingerprint + unified type-conditional address

`eval/wall_fingerprint.py` + `eval/spatial_address_ceiling.py`. The 60 held-out targets
split: **35 fillers** (window/door, addressed by `position_context` slot, cut-3) · **22 walls**
· **3 other**. Walls are hosts (no position-slot) → needed their own descriptor. The **wall
fingerprint** = `(connection_degree, hosted_opening_count, length_band, is_external)` — all
IFC-computable *and* photo/floorplan-recoverable (count a wall's junctions + openings, judge
length + interior/exterior).

**Wall |C| ceiling (within same-storey walls, 22 wall targets):**

| within same-storey walls | median |C| | uniquely ID'd |
|---|---|---|
| coarse | 110 | — |
| + object_type | 26 | 0/22 |
| **+ wall fingerprint** | **2** | **10/22** |

→ the wall fingerprint discriminates where `object_type` cannot (0/22 unique).

**Unified type-conditional spatial address — oracle Top-k on real pools (60 targets):**

| scheme (oracle r=1) | Top-1 | Top-5 | Top-10 | MRR |
|---|---|---|---|---|
| realized (G8) | 6.7 | 16.7 | 30.0 | 0.110 |
| coarse storey+class | 4.9 | 17.9 | 31.5 | 0.137 |
| + object_type | 18.1 | 53.6 | 76.3 | 0.352 |
| **+ spatial address (type-conditional)** | **78.5** | **94.2** | **98.1** | **0.854** |
| + both | 82.4 | 94.6 | 98.3 | 0.878 |

By subgroup (spatial address): **fillers** Top-1 91.0 / Top-10 100.0 (position-slot);
**walls** Top-1 64.2 / Top-10 97.4 (wall fingerprint, vs object_type 11.4 / 62.9).

**Finding:** the *type-conditional* visual-topological spatial address — position-slot for
fillers, connection/opening/length/external fingerprint for walls — takes oracle Top-1 from
4.9 → **78.5** and Top-10 → **98.1**. This is the full spatial-address contribution: **every
element class now has a discriminative, IFC-computable, evidence-recoverable address.** Walls
were the open piece; they're closed. Remaining: the 3 "other" targets, a *realistic*
(non-oracle) row per descriptor (needs the structured extractors = P2), and the full 3c
descriptor sweep (junction-type / generated-cell / landmark) + extractability/stability scoring.

> **Caveats:** (1) oracle r=1 — realizable needs the structured extractors (position-slot +
> wall connection/opening counts); all are photo/floorplan-recoverable by construction (the 3c
> criterion). (2) wall fingerprint reconstructed offline from `IfcRelConnectsPathElements` +
> FILLS reverse + IFC Length; `connection_degree`/`hosted_opening_count` are the dominant
> descriptors. (3) stability risk (e.g. `connection_degree` sensitivity to model authoring)
> not yet scored — part of the full 3c sweep.

---

## M1a — position-slot extractor: intrinsic harness + floor/ceiling baselines (2026-06-10)
`eval/slot_extractor_m1.py` · `output/slot_extractor_m1.png` · 5 tests. Held-out **35 fillers**
(Tier-3, = thesis "pool=1 for 35 cases"; 0 leaked-id fillers → eval set intact). The M1 build's
measurement scaffold — the image detector (Arm A marked plan / Arm B mark-free) is M1b and plugs
a predictor into `PREDICTORS`.

| predictor | cov | exact_i | exact_M | joint | ±1_i | **Top-1** | Top-10 |
|---|--:|--:|--:|--:|--:|--:|--:|
| prior (modal i,M) — FLOOR | 100% | 23% | 29% | 6% | 54% | 6.6 | 27.6 |
| text-parse (honest query) | 0% | 0% | 0% | 0% | 0% | **2.4** | 24.4 |
| G8 realized `position_context` | 0% | 0% | 0% | 0% | 0% | **2.4** | 24.4 |
| oracle M (host known), prior i | 100% | 23% | 100% | 23% | 54% | 18.8 | 39.9 |
| oracle i, prior M | 100% | 100% | 29% | 29% | 100% | 29.5 | 45.9 |
| oracle full (i,M) — CEILING | 100% | 100% | 100% | 100% | 100% | **91.0** | 100.0 |

**Findings.** (1) **The entire 2.4→91 filler gap is the *unextracted* slot:** G8 emits
`position_context` for **0/35** fillers, and the NL query carries storey+class only (no positional
cue) → the slot is a *genuinely visual* target (no text shortcut; justifies the M1b image
detector). (2) **Decomposition — *i* is the bigger and harder lever:** knowing the ordering index
alone (oracle-i) lifts Top-1 to **29.5** vs **18.8** for the count *M* alone; *M* is partly a prior
(modal=17 covers 10/35) and free once the host wall is identified, whereas exact-*i* sits at 23%
under the prior. ⇒ **M1b should spend its budget on the visual *i*-ordering along the host wall.**

> Caveats: prior is in-sample modal (a floor reference, mildly optimistic). Downstream scores each
> candidate's *true* slot against the *predicted* key (no self-match artefact); abstain falls back
> to G8's realised ranking. Leakage exclusion (`leakage_excluded_train_ids.txt`) does not touch
> these 35 (0 overlap) — it binds only the M4 *training* set.

---

## M1b probe — what's detectable for the image slot detector (2026-06-10)
`eval/m1b_probe.py`. Empirical characterization done *before* building the detector. Three
findings:
1. **Marked patch occludes openings.** `floorplans/<id>_floorplan.png` paints the target wall
   SOLID red (anchor solid orange) — windows/doors are covered (window-glyphs visible inside the
   patch ≈ 0). ⇒ the slot cannot be read from the marked patch; it gives host-wall identity +
   target location only.
2. **Clean plan color-codes openings** (window=blue, door=green) as discrete segments →
   directly color-segmentable, no fragile gap-detection. Counts: First Floor 46w/70d, Level 1
   31w/45d, Garage 0w/45d. Detector is **feasible** here.
3. **Coverage = 3/7 storeys → 17/35 fillers.** Only First Floor / Garage / Level 1 have a clean
   plan — a *deliberate* 3-storey scope cut in the dataset renderer
   (`data_curation/scripts/synth/3c_render_full_storeys.py` L155-166, "Phase 6 T1 scope"),
   deferred as F2 future work, **not** a fundamental limit. The other 18 fillers (Second/Third/
   Fourth/Fifth Floor) have no clean plan.

**M1b reshape:** the detector is a COLOR-based opening finder (blue/green) on the clean plan →
group collinear openings per host wall → order along wall axis → (i, M), scored on the
`slot_extractor_m1` harness. **Open coverage decision** (regenerate the 4 missing storeys' clean
plans — cheap, unlocks all 35 + the demo's honest arm — vs build on the 17-subset now vs pivot to
the learned/site-photo arm). Site photo alone can't give M (perspective/occlusion — spec Risk #4).

---

## M1b v0 — deterministic color-based slot detector (2026-06-10)
`eval/slot_detector_cv.py` (+ 3 tests). Honest image extractor (no IFC answer): project target →
plan pixel → color-detect openings (window=blue, door=green) → wall axis from the **target
opening's own elongation** (junction-robust) → order along axis → (i, M). Covered fillers = the 17
on clean-plan storeys; abstains on the 18 un-rendered (Floors 2-5).

| over all 35 fillers | coverage | exact_i | exact_M | joint | **Top-1** | Top-10 |
|---|--:|--:|--:|--:|--:|--:|
| realized floor (G8) | 0% | 0% | 0% | 0% | 2.4 | 24.4 |
| **M1b CV v0** | 49% | 9% | 14% | 3% | **4.9** | 26.0 |
| oracle full | 100% | 100% | 100% | 100% | 91.0 | 100.0 |

On the **covered 17** (orientation-agnostic): exact_M 5/17, exact_i 7/17 — the detector genuinely
reads clean small-M walls (e.g. AP_SK_234: 3-window wall, M✓ i✓). **Top-1 doubles (2.4→4.9).**

**Findings / bottlenecks (the honest realizable picture).** (1) **Wall orientation is the dominant
loss:** canonical exact_i 9% vs orientation-agnostic ~41% on covered — the image can't tell which
wall-end is index 0 (the IFC local +X frame is not image-recoverable); resolving it needs an extra
cue (e.g. a corner/anchor reference). (2) **Long walls over/under-count** (M=14 → ±2) — the
perp-band picks up/loses openings where walls bend or run close to a parallel wall. (3) **Coverage
18/35** blocked by the F2 multi-storey re-render. ⇒ next: orientation resolution (biggest lever),
then long-wall robustness; M is otherwise free once the host wall is known (M1a). This is the RQ2
"oracle 91 → realizable" gap, with its bottleneck named and measured.

---

## M1b v1 — wall-orientation resolution (2026-06-10)
The v0 bottleneck was the arbitrary PCA/IFC axis SIGN (canonical exact_i 9% vs orientation-agnostic
~41%): the image can't see the IFC wall's local +X. **Diagnosis:** along any global world direction
walls are monotonic but the sign is split per-wall (~9 fwd / 15 rev for +X) — `wdir`'s sign is an
arbitrary authoring choice, not globally predictable, and the orientation-invariant "fold" slot
`min(i,M-1-i)` craters the ceiling (91→51). **Fix:** order along the wall's own axis with the sign
fixed by a GLOBAL world reference (`axis·(1,0.3)>0`) — a convention both GT and the image detector
can apply. Validated **discrimination-neutral: oracle filler Top-1 stays 91.0** under the relabel
(`build_global_slot`, offline from element_index — no ifcopenshell; canonical `position_index`
untouched).

| filler Top-1 | Top-10 | note |
|---|--:|---|
| realized floor (G8) | 2.4 / 24.4 | slot empty |
| M1b v0 (orientation arbitrary) | 4.9 / 26.0 | mirror ambiguity |
| **M1b v1 (orientation resolved)** | **9.1 / 32.0** | sign fixed by global ref |
| oracle | 91.0 / 100.0 | |

**Result:** orientation now contributes **zero** loss — on the covered 17, `exact_i (resolved) ==
exact_i (agnostic) == exact_M` (every correct-count case also gets i right, no mirror). Top-1
nearly doubled again (4.9→9.1). **The bottleneck has shifted to M-counting** (exact_M 4/17:
long/curved walls over/under-count) and coverage (17/35). Next levers: M-count robustness, then the
F2 re-render for the 18 uncovered fillers.

---

## M1b v2 — M-counting robustness (2026-06-10)
Diagnosing the v1 M-count bottleneck surfaced **two** issues:

1. **GT bug (fixed):** `build_global_slot` grouped fillers by `wall_guid` only, merging multi-storey
   walls across floors → inflated GT M (85/50/20 vs canonical 17/10/4). The First-Floor "massive
   under-counts" were a GT artefact. Fixed to group by **(wall, storey)** like `position_index`
   (regression test: M now == canonical for all fillers). *(v1's Top-1 9.1 was partly against the
   inflated GT — superseded.)*
2. **Detector over-counting (fixed):** with correct GT, **every** error was an over-count —
   collinear ≠ same wall. The straight perp-band grabbed openings from *different* walls that line
   up along a corridor (AP_SK_078: a 2-filler wall read as the whole corridor door-run). **Fix:**
   **wall-continuity truncation** — keep only the run around the target where consecutive openings
   are joined by continuous wall poché (a corridor/junction gap = open floor = break).

| filler Top-1 | Top-10 | exact_M (covered) |
|---|--:|--:|
| M1b v1 (orientation, inflated GT) | 9.1 / 32.0 | — |
| **M1b v2 (continuity + GT fix)** | **20.1 / 42.9** | **12/17** |
| oracle | 91.0 / 100.0 | 17/17 |

**Result:** exact_M 5→**12/17**, Top-1 **9.1→20.1** (Top-10 32→43). Residual errors all bounded:
4× **+1 corner end-effect** (wall turns; one collinear+connected opening past the corner) + 1
**corridor pathology** (AP_SK_078, 2-filler wall collinear with a continuous corridor wall) + a
**~3-case orientation sign ambiguity** on near-⊥-to-ref walls (image axis sign disagrees with the
GT PCA sign). Next levers: corner detection (stop at the wall turn) and the F2 re-render for the 18
uncovered fillers. M-counting is no longer the dominant loss; coverage (17/35) now is.

---

## M1b coverage — F2 upper-storey re-render (2026-06-10)
`scripts/render_upper_storeys.py` (reuses the dataset's own `render_one`, frozen tree untouched).
The 18 uncovered fillers were on Floors 2-5, whose host walls are multi-storey walls contained in
"Level 1" → storey-containment gave wall-less plans (the author's deferred "F2"). Fix: per upper
floor, pull each window's **host wall** via FILLS→VOIDS and render walls+windows together →
byte-matches `floorplans_full/` (blue/green/dark + world_bbox json), consumed by the detector
unchanged. **Coverage 17/35 → 35/35.**

| subset | Top-1 | Top-10 | exact_M |
|---|--:|--:|--:|
| **orig-17 (realistic, cluttered)** | **39.1** | 65.3 | 12/17 |
| new-18 (sparse host-wall renders) | 94.6 | 95.7 | 17/18 |
| all-35 (aggregate) | 67.6 | 80.9 | 29/35 |
| oracle | 91.0 | 100.0 | 35/35 |

**⚠️ Honesty caveat (load-bearing).** The new upper-floor plans contain **only the host walls +
windows** (the multi-storey walls aren't storey-contained, so only host walls are pull-able) → they
are **sparser/easier than realistic cluttered floors** (no corridors/doors/interior walls to confuse
collinearity). So **94.6 is an optimistic ceiling**, and the **realistic deployable number is the
cluttered-floor 39.1** (floor 2.4 → 39.1 = 16× on realistic plans; aggregate 67.6 is flattered by a
half-sparse test set — report the split, not the aggregate alone). A fully-realistic upper-floor
render needs the multi-storey-wall→floor assignment (genuine future work). Full M1b arc on realistic
plans: floor 2.4 → 39.1.

---

## P1 Step B (diagnostic) — ECE gate on raw M1b confidence (2026-06-11, exploratory)

`eval/calibration_diag.py` (+ `eval/field_contract.py`, Step A contract bridge). Ran the
calibration gate (enhanced-module L180) on the raw M1b slot confidence over the 35 held-out
fillers, BEFORE any routing. Confidence = `min(1, len(seq)/max(spread/40,1))`
(`slot_detector_cv.py:202`). **Scored against the convention-consistent GT `gslot`
(`build_global_slot`), the same GLOBAL_REF orientation the detector uses.**

| metric | value | reading |
|---|--:|---|
| n (non-abstain fillers) | 35 | full coverage post-F2 |
| joint (i,M) accuracy vs gslot | 0.743 | exact_M 83% · exact_i 74% |
| **ECE** (5 equal-width bins) | **0.206** | moderately mis-calibrated, monotone-usable |
| **AUROC** P[conf(correct)>conf(wrong)] | **0.80** | **+correlated** (≫0.5) |
| mean conf — correct / wrong | 0.63 / 0.46 | higher conf ⇒ more likely correct |

**Verdict — GATE PASSES.** The raw confidence is positively discriminative (AUROC 0.80) and
only moderately mis-calibrated (ECE 0.206) → temperature scaling is applicable; Step C proceeds
with calibrate → soft-rerank (no L188 contingency, no geometry-margin swap needed). Figure:
`output/calibration_diag.png`. 3 tests.

> ⚠️ **Eval-harness bug found & fixed same-day (do not repeat).** A first pass scored the pairs
> against the raw wdir-based `position_index` (`pos`), not `gslot`. The two disagree on **16/35**
> fillers because `wall_position_index` is defined by the wall's **IFC local-X sign** — an
> arbitrary modelling artefact the image cannot recover — whereas the detector and `gslot` both
> orient by the image-recoverable GLOBAL_REF rule. That mismatch spuriously reported joint 0.343 /
> ECE 0.409 / AUROC 0.31 ("anti-correlated"). **Lesson: the position-slot address is only
> image-recoverable under the GLOBAL_REF convention; always evaluate i against `gslot`, never the
> wdir `pos`.** Codified in `field_contract.collect_pairs` (now requires `gslot`) + 2 regression tests.

---

## P1 Step C — calibrated soft-rerank + selective prediction (2026-06-11, exploratory)

`eval/calibrate_rerank.py`. RQ2 mechanism on the position-slot, scored against `gslot` (n=35
fillers, GT-in-pool). Temperature scaling (pure-python NLL min) → recall-safe soft-rerank →
selective prediction.

| | Top-1 | Top-10 | note |
|---|--:|--:|---|
| floor (prior) | 6.6 | 27.6 | |
| hard slot-match | **67.6** | 80.9 | the slot evidence itself (floor 6.6 → 67.6) |
| raw-soft (w=conf) | 67.6 | 80.9 | = hard |
| calib-soft (w=σ(logit(c)/T)) | 67.6 | 80.9 | = hard |

Calibration: T=0.30 (genuine NLL min), **ECE 0.206 → 0.172** (modest; small-n).

**Finding 1 — soft-rerank == hard (no gain, no harm).** The slot is the *finest* tiebreaker
(storey+class are +1 each; the slot term breaks ties within a storey×class bucket). Any
**positive** weight boosts a slot-matching candidate identically, so continuous reweighting
cannot reorder — only *removing* the term (deferral) changes the result. So the calibrated
confidence's value is NOT in the rerank weight.

**Finding 2 — selective prediction is where calibration pays (the practical story, L183).**
Deferring the least-confident cases lifts Top-1 on the answered subset:

| coverage | τ (calib conf) | Top-1 on answered |
|--:|--:|--:|
| 1.00 | 0.00 | 67.6 |
| 0.91 | ~0.10 | 74.0 |
| **0.80** | **0.40** | **80.6** |

(Below cov 0.5 the curve is noisy — n=35.) **Headline operating point: defer the bottom ~20%
→ Top-1 67.6 → 80.6 (+13pp).** This matches L102 (don't lead with calibration; soft-rerank is
the frame) + L183 (defer = first-class outcome, the clearest triage value prop). Figure:
`output/calibrate_rerank.png`. 4 tests (46 total).

**Worked examples (for the demo cards + RQ2 section; reproducible via `eval/build_demo.py`).**
| case | predicted (i,M) | GT (gslot) | raw conf → calibrated (T=0.30) | decision (τ=0.40) |
|---|---|---|---|---|
| AP_SK_102 (filler, Second Floor) | (2, 17) | (2, 17) ✓ | 0.52 → 0.57 | **ANSWER** (correct) |
| AP_SK_092 (filler, First Floor) | (1, 10) | (8, 10) ✗ | 0.29 → 0.05 | **DEFER** (wrong-but-low-conf → abstains) |

AP_SK_092 is the selective-prediction headline case: the extractor is wrong (1 of 10 vs GT 8 of
10) but its calibrated confidence (0.05) is below τ, so the system defers and returns candidates
rather than a confident wrong GUID. Cards: `output/demo/case_AP_SK_{102,092}.png`.
