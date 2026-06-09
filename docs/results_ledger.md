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
