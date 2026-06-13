# Technical review — findings & status (2026-06-12)

AI-Scientist review of repo + paper + site. Items numbered as in the review. Status legend:
✅ done · 🟡 partial/assessed · ⬜ deferred ("等下再做").

## Resolved in this pass

| # | Finding | Action taken | Status |
|---|---------|-------------|--------|
| 1 | Baseline mislabeled as "fine-tuned end-to-end multimodal reranker" (6.7%). It is actually G8 = fine-tuned-VLM extraction → deterministic retrieval, **no within-pool rerank** (`STATUS.md:14`). No true cross-attention pool-matcher was trained. | Relabeled in `01_introduction.tex` + `02_system_design.tex §rationale`; added note that a zero-shot VLM reranker is the fair upper-bound baseline to add. **Decision: do NOT train a from-scratch reranker** (see below). | ✅ |
| 2 | Paper claimed "no case overlap"; repo audit shows **element-level leakage 12/59** (9 fillers, 3 walls). | Disclosed in `03_evaluation.tex §eval-setup`. Verified leakage-clean 48-case re-profile is **unchanged** (storey/class 100%, slot/size 0%). Realized (OpenCV) + oracle (graph-only) results are leakage-proof by construction. | ✅ |
| 3 | Realized 67.6 / AUROC 0.80 / ECE had **no CIs** (while `run_benchmark.py` bootstraps elsewhere). | Added bootstrap CIs to `calibration_diag.py` & `calibrate_rerank.py`. Top-1 67.6 **CI [53.6, 81.6]**; AUROC 0.80 **CI [0.58, 0.99]**; ECE 0.206 **CI [0.09, 0.32]**. Added to paper. | ✅ |
| 4 | 116-case cross-IFC benchmark mentioned but never reported. | User: dataset is old/non-standard → **removed** from `02_system_design.tex §synth` and `03_evaluation.tex §eval-failure`. | ✅ |
| 5 | Text-only lexical/dense baselines don't test the visual claim. | **Done: zero-shot Qwen2.5-VL reranker baseline run on Modal** (CLIP rejected — graph nodes have no images; identical sibling text → ties). `BaseVLMReranker` (base model, **no adapter**) + `eval/vlm_reranker_baseline.py`. **Result: stays at chance** — full pool Top-1 **3.3%** (chance 1.8%), fillers **2.9%** (chance 2.4%); siblings-shortlist identical. Raw outputs show positional/degenerate rankings, not grounding. Added both rows to `external_baseline.{py,png}` + a paragraph & caption in `03_evaluation.tex`. **Backbone can't recover the slot; the structured address can (78.5% oracle).** | ✅ |
| 6 | Oracle (78.5) vs realized (67.6, filler subset) blurred in abstract. | Abstract + contributions relabeled: 78.5 = oracle ceiling (all 60); 67.6 = realized, filler subset n=35. | ✅ |
| 7 | Wall fingerprint (64.2) presented as a working contribution but is oracle-only / not image-realizable. | Flagged explicitly in abstract + contribution #2. | ✅ |
| 8 | Detector pixel thresholds (NEAR_R/PERP_TOL/MATCH_MAX) hardcoded → overfit risk. | Added `eval/slot_detector_sensitivity.py` (±25% one-at-a-time + joint grid). Result: see `output/slot_detector_sensitivity.json`. | ✅ |
| 9 | Universe size inconsistent (1,257 vs 1,233 vs 852). | Verified from `element_index.jsonl` → **1,233**. Fixed `03_evaluation.tex` (was 1,257). 852 = edge-filtered depth subgraph (different scope, OK). | ✅ |
| 10 | Direction "82%" (accuracy, thesis) vs "57%" (held-out) conflated. `vlm_profile.py:44` `dir` is an **emission rate** (`any(direction)`), not accuracy. | Clarified in `03_evaluation.tex §eval-neural`: 57% = emission rate, not the 82% accuracy; not comparable. | ✅ |

## Reranker feasibility verdict (#1)
- **Data exists** to train one: 312 site images + `element_index` candidate text + GT guids + siblings as negatives.
- **But** candidate graph nodes carry no images and siblings share identical text, so a learned matcher must recover the relational signal from the image alone — exactly the configuration the paper argues against, and expected to plateau. High cost (GPU + infra), low information.
- **Verdict:** do not build from scratch. Instead add a **zero-shot VLM reranker** as the off-the-shelf upper-bound of the end-to-end family (ties to #5).

## Running the zero-shot VLM reranker (#5)
Files: `master_thesis/mscd_demo/training/inference.py::BaseVLMReranker` (serve) · `eval/vlm_reranker_baseline.py` (eval).
```bash
# 0) validate harness locally, no GPU (lexical stand-in):
.venv/bin/python eval/vlm_reranker_baseline.py --stub --limit 5
# 1) deploy the base-model reranker alongside G8 (one Modal app):
modal deploy master_thesis/mscd_demo/training/inference.py
# 2) run the real baseline (A100; ~60 warm calls):
.venv/bin/python eval/vlm_reranker_baseline.py            # → output/vlm_reranker_baseline.json
# 3) paste the printed ledger row into external_baseline.py and re-make the figure.
```
**Confirmed (2026-06-13):** stays at **chance** in both scopes (full pool Top-1 3.3% / chance 1.8%; fillers 2.9% / chance 2.4%; sibling shortlist identical). The base VLM emits positional/degenerate rankings (`[2,3,4,…]`, arithmetic sequences) rather than grounding; the per-case shuffle makes that score at chance. → a strong general VLM cannot recover the relational slot from the image alone. `output/vlm_reranker_baseline.json` holds the full per-case dump.

## Deferred — "等下再做" (do later)
| # | Finding | Plan |
|---|---------|------|
| 11 | ✅ **Done.** User clarified this paper *is* the MSCD thesis project → it must not self-cite. **Removed all 7 `\citep{chiahuiyen_mscd_thesis}`** (2 in system_design, 5 in evaluation) + deleted the bib entry; those findings now read as our own work. For the intro `[CITATION NEEDED]`: mined the thesis bibliography — the scene-graph sentence is **Wang et al. 2024** (ref [39], *VLM-based scene graph generation for industrial spatial intelligence*, SSRN 4926945), now added + cited. The "Li et al. 2024" (ref [31]) is a multi-agent-systems survey, **not** pixels-to-graphs → does not fit that sentence, intentionally not cited. Build clean, 0 undefined citations. | done |
| 12 | ✅ **Done.** Added consolidated **Table~\ref{tab:main}** to `03_evaluation.tex` (end of §eval-setup): 4 grouped panels (external baselines / G8 realized / oracle ceiling / realized fillers) × {GT-in-Pool, Top-1, Top-10, MRR}, realized Top-1 67.6 with bootstrap CI in subscript. Compiles, 19 pp. Note: Top-5 column omitted (not measured); GT-in-Pool=100 throughout isolates ranking. | done |
| 13 | ✅ **Done.** Rewrote `external_baseline.dense_scores`: removed the misleading `guids` list (it held text, not guids), cache is now explicitly keyed by candidate text with a clean dedupe. Same results, compiles. | done |
