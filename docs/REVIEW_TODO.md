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
| 5 | Text-only lexical/dense baselines don't test the visual claim. | **Decision: add a zero-shot Qwen2.5-VL reranker baseline** (the fair "can a strong general matcher do it" control). CLIP is **not** suitable (candidates are graph nodes with no images; identical sibling text → ties). Needs Modal/GPU → scoped, not yet run. | 🟡 |
| 6 | Oracle (78.5) vs realized (67.6, filler subset) blurred in abstract. | Abstract + contributions relabeled: 78.5 = oracle ceiling (all 60); 67.6 = realized, filler subset n=35. | ✅ |
| 7 | Wall fingerprint (64.2) presented as a working contribution but is oracle-only / not image-realizable. | Flagged explicitly in abstract + contribution #2. | ✅ |
| 8 | Detector pixel thresholds (NEAR_R/PERP_TOL/MATCH_MAX) hardcoded → overfit risk. | Added `eval/slot_detector_sensitivity.py` (±25% one-at-a-time + joint grid). Result: see `output/slot_detector_sensitivity.json`. | ✅ |
| 9 | Universe size inconsistent (1,257 vs 1,233 vs 852). | Verified from `element_index.jsonl` → **1,233**. Fixed `03_evaluation.tex` (was 1,257). 852 = edge-filtered depth subgraph (different scope, OK). | ✅ |
| 10 | Direction "82%" (accuracy, thesis) vs "57%" (held-out) conflated. `vlm_profile.py:44` `dir` is an **emission rate** (`any(direction)`), not accuracy. | Clarified in `03_evaluation.tex §eval-neural`: 57% = emission rate, not the 82% accuracy; not comparable. | ✅ |

## Reranker feasibility verdict (#1)
- **Data exists** to train one: 312 site images + `element_index` candidate text + GT guids + siblings as negatives.
- **But** candidate graph nodes carry no images and siblings share identical text, so a learned matcher must recover the relational signal from the image alone — exactly the configuration the paper argues against, and expected to plateau. High cost (GPU + infra), low information.
- **Verdict:** do not build from scratch. Instead add a **zero-shot VLM reranker** as the off-the-shelf upper-bound of the end-to-end family (ties to #5).

## Deferred — "等下再做" (do later)
| # | Finding | Plan |
|---|---------|------|
| 11 | `references.bib` has unresolved TODOs: self-thesis title/year unconfirmed (`references.bib:85-95`), `[CITATION NEEDED]` in `01_introduction.tex:71`. | Confirm before camera-ready. |
| 12 | No single consolidated main results table (methods × {GT-in-pool, Top-1/5/10, MRR} × CI). Numbers scattered in prose. | Add Table 1. |
| 13 | `external_baseline.py:73-77` dense cache appends text as guid (cosmetic, works by accident). | Tidy. |
