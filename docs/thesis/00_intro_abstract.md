# Abstract & Introduction — AEC Interpreter

> **Thesis front-matter draft.** The abstract follows the 5-sentence formula (Farquhar); the
> introduction states one contribution, lists it as bullets, and threads the three research
> questions (RQ1 representation → RQ2 mechanism → RQ3 architecture). Figure 1 = `output/pipeline.png`
> (the method spine). All numbers trace to `docs/results_ledger.md`; citations are verified `\cite{}`
> keys in `references.bib`. Prose is in thesis register — edit to taste.

---

## Abstract

We introduce a neuro-symbolic method that grounds a construction-site photograph and a
natural-language note to a *unique* element in a building's IFC model — answering "*which* element
is this?" with a single GUID — using only the BIM model itself for supervision, with no real on-site
labels. The task is hard for three reasons that defeat an end-to-end matcher: the discriminating
elements are *visually identical* (a façade is a row of indistinguishable windows), the answer lives
in *graph* space while the evidence lives in *image* space, and a cold-start deployment has *no
paired training data*. Our method recovers a **type-conditional spatial address** — a class-specific,
relational key (the ordinal position-slot for an opening, a connectivity fingerprint for a wall) that
is computable from the raw IFC model and recoverable from the image — reconstructs it with
deterministic visual specialists, and consumes it through a per-field `{value, confidence, source}`
contract with a calibrated, recall-safe soft-rerank and selective prediction. Supplied at an oracle
level the address lifts pool Top-1 from 4.9 % to **78.5 %** at zero recall cost; a single realizable
extractor lifts the addressable subset from a 6.6 % floor to **67.6 %**, its confidence passes an ECE
calibration gate (AUROC 0.80), and deferring the least-confident fifth raises answered-set Top-1 to
**80.6 %**. The system thus converts a 6.7 % end-to-end baseline into an auditable grounder that knows
when to abstain — and, by a measured depth law, keeps the address shallow enough to actually recover.

## Introduction

**One-sentence contribution.** Grounding a site observation to a unique BIM element reduces to
recovering a *type-conditional spatial address* — a class-specific, image-recoverable relational key —
and a calibrated, recall-safe routing layer turns that address from an oracle ceiling into a
realizable, selectively-predictive grounding system.

The setting is a cold-start one. A construction or facilities team has a complete IFC/BIM model but no
history of labelled site imagery; on day one they want to point a phone at an element, add a short
note, and be told *which* modelled element it is. The final step is a selection from a retrieved
candidate pool in which the ground truth is almost always present (median 76, in-pool 100 %), so the
difficulty is not retrieval but **discrimination among visually identical siblings**, in a regime with
no paired supervision to learn that discrimination from. The natural baseline — fine-tune a multimodal
reranker to score the pool end-to-end — is exactly the configuration that plateaus: it reaches Top-1
6.7 % with the answer already in the pool, because the signal that separates two identical windows is
not in either window's pixels but in the building's relational structure, which a black-box matcher
must reconstruct internally and unreliably (we develop this central baseline in §[why-not-end-to-end]
\cite{sutton2019bitter}).

This thesis makes one contribution — the type-conditional spatial address and the calibrated routing
that makes it usable — developed through three research questions:

- **RQ1 — Representation (§[rq1]).** *What is the minimal sufficient spatial address?* We show it is
  **type-conditional**: a coarse ontological prefix (storey + class) that is necessary but saturated,
  completed by a class-specific topological body — the position-slot `(i, M)` for fillers, a
  connectivity fingerprint for walls. At an oracle level it reorders the pool from Top-1 4.9 % to
  **78.5 %**, with the gain partitioned by element type (fillers 91 %, walls 64 %).

- **RQ2 — Mechanism (§[rq2]).** *How is a noisily-recovered address used without losing recall, and
  how much of the ceiling is realizable?* Hard filtering destroys recall, so the address is a
  **soft prior in a recall-fixed pool**; one real extractor lifts the addressable Top-1 from 6.6 % to
  **67.6 %**, its confidence passes an ECE gate (AUROC 0.80), and — since reweighting a finest-grained
  prior is a no-op — its payoff is **selective prediction**: deferring the least-confident ~20 % raises
  answered-set Top-1 to **80.6 %** \cite{guo2017calibration, geifman2017selective}.

- **RQ3 — Architecture (§[rq3]).** *Where should the relational context live — extracted deep at
  inference, or compiled into the node?* A **depth law**: deeper context is informationally more
  discriminative but its recovery collapses with depth (per-hop reliability 0.40 → 0.05 → 0), so the
  realizable confusable set saturates at one hop (median 13 → 8.2 → 8.1). The architecture therefore
  compiles depth into the node and extracts at depth ≤ 1, placing learning at the neural→symbolic
  interface \cite{mao2019nscl}.

Figure 1 (the method spine) traces a single case through the pipeline: site photo and marked plan →
per-field extraction (each field `{value, confidence, source}`) → the depth-1 spatial-address record →
calibrated routing → the IFC-graph pool collapse to a GUID, with the confidence-routing path that
binds the answer/defer decision highlighted.

**Scope, stated up front.** Two honesty boundaries frame every result. First, the diagnostic ceilings
(RQ1, and the oracle rows of RQ2/RQ3) assume perfect extraction; the realizable numbers come from one
deterministic extractor (the position-slot), with the wall fingerprint and remaining descriptors
demonstrated at oracle level only — full realization is future work. Second, all measurements are on a
single synthetic project (cold-start by design); the *form* of the contribution — a type-conditional,
shallow, image-recoverable, calibrated-soft address — is general, but the specific reliabilities are
project-specific. We do not claim to beat an end-to-end matcher in the large-data limit; we claim that
in the cold-start regime we can actually measure, the structured address is what makes grounding
realizable, auditable, and transferable.
