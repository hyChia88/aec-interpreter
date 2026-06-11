# RQ3 — Where Relational Context Belongs: A Depth Law for the Spatial Address

> **Thesis section draft.** Intended placement: the architecture/principle section, after the
> representation ([`rq1_spatial_address.md`](rq1_spatial_address.md)) and mechanism
> ([`rq2_calibrated_routing.md`](rq2_calibrated_routing.md)) chapters — it justifies an
> architectural choice both rely on. RQ3 asks *where* the relational context of the address should
> live: extracted as a multi-hop chain at inference, or compiled into the target node ahead of
> time. Numbers are from `eval/depth_saturation.py` (oracle and reliability-weighted median
> confusable-set size by relational depth, AP held-out) and trace to `docs/results_ledger.md` /
> `docs/ROADMAP.md`; the training-side findings are from the author's prior MSCD thesis
> \cite{chiahuiyen_mscd_thesis}. External citations are verified `\cite{}` keys in
> `references.bib`. Prose is in thesis register — edit to taste.

---

## The architectural question

The spatial address is relational: a filler is pinned by its place *along a wall*, a wall by *what
it connects to*. A relational representation forces an architectural decision about **where the
relational context is computed**. One option is to extract it *at inference time* as a multi-hop
graph traversal — "the window next to the door that opens onto the stair that leads to the lobby" —
letting the model recover an arbitrarily deep chain from the evidence. The other is to *precompute*
the relational context into the target node as a fixed feature, so inference only reads a node
attribute. The choice is not cosmetic: it determines how much the runtime extractor must recover
from a noisy image, how the learned components allocate capacity, and whether the system is
auditable. RQ3 asks which is right, and answers it with a measurement rather than a preference.

## Information is not realizability: the central distinction

The tempting argument for deep extraction is informational. Deeper relational context *is* more
discriminative: under an oracle that recovers every relation perfectly, the confusable set keeps
shrinking with depth — a Weisfeiler–Leman-style refinement drives it toward singletons, so in the
limit *deeper context uniquely identifies the target*. If information were the only consideration,
the architecture should extract as deep as possible.

It is not, because **the relations must be recovered from an image, and recovery reliability
collapses with depth**. The two curves diverge sharply. Measured on the held-out set, the oracle
confusable set falls with depth (information says deeper is unique), but the *realizable* confusable
set — weighting each hop by the measured reliability of recovering it from evidence — saturates
almost immediately:

| relational depth | realizable median \|C\| |
|---|---|
| attributes only (depth 0) | 13 |
| **+ 1 hop** | **8.2** |
| + 2 hops | 8.1 |
| + 3 hops | 8.1 |

Per-hop extraction reliability falls as **0.40 → 0.05 → 0**: a one-hop relation is recovered ~40 %
of the time, a two-hop predicate ~5 %, a three-hop predicate essentially never. The product that
governs a realized multi-hop chain therefore decays geometrically, and **all realizable
discrimination is captured at depth 1** (median 8.2, near the oracle-L3 value of ~9); depths 2 and 3
add nothing a real extractor can use. This is the depth law: *deeper context is informative but not
recoverable, so the realizable address is shallow.* The failure mode is the well-documented error
compounding of multi-hop reasoning over knowledge graphs, where each additional hop multiplies the
chance of an unrecoverable or hallucinated link \cite{chakraborty2024multihop}.

## The training-side corroboration

The depth law is not only an inference-time observation; the author's prior thesis found its
training-time shadow \cite{chiahuiyen_mscd_thesis}. Supervising the model on depth-3 relational
chains *wasted* the supervision — the realizable improvement was ≈ 0 — and worse, it **cost
capacity**: under a constrained adapter (LoRA rank 16) the depth-≥2 chains competed with and
degraded the model's recovery of the coarse `ifc_class` field, and the deep-chain extraction itself
ran at ~5 % accuracy and *hurt* end-to-end performance by ~13 points. Two independent measurements —
the inference-time reliability collapse and the training-time capacity conflict — point to the same
conclusion, which makes the architectural prescription **subtractive**: not "add deeper reasoning"
but "stop training depth-≥2 chains and reallocate the freed capacity to the fields that are
recoverable."

## The answer: compile depth into the node

The architecture therefore precomputes. Relational context is **compiled into the target node** as
the distilled `node.val` address (the position-slot, the connectivity fingerprint), computed once
from the BIM model at ingestion, and the runtime extractor recovers only what is recoverable: a
single hop of context. This is consistent with the dual representation of RQ1 — a depth-1 sub-graph
and the node attributes it distils into carry the same information — and it places the learned
component exactly where a neuro-symbolic system should: at the *neural→symbolic interface*, recovering
shallow node-level evidence that a deterministic symbolic layer then executes, rather than asking a
network to perform deep relational inference internally \cite{mao2019nscl}. The principle the system
follows is concise: **extract at depth ≤ 1; go richer at depth 1, never deeper; compile depth into
the node.** A single concession is allowed — a depth-1-to-landmark relation may be used when the
landmark anchor is *independently* grounded (so the second hop carries no extraction risk) — but the
default is shallow.

## The honest boundary of the claim

Three caveats bound the depth law. *Descriptor and project specificity:* the saturation is measured
on this synthetic AP export and this address-descriptor family; the *form* of the law — realizable
discrimination saturates where per-hop reliability decays — is general, but the exact saturation
depth could differ for a model with reliably-recoverable deep relations (e.g. strong named
landmarks). *Reliability estimates:* the per-hop reliabilities (0.40 / 0.05 / 0) are measured on the
current extractors; a substantially better multi-hop extractor would push the realizable curve
rightward, though the oracle–realizable gap is large enough that depth-1 dominance is robust to
moderate improvement. *Oracle refinement:* the WL-style uniqueness at depth is an informational
upper bound, not a claim that any system should pursue it. None of these undercuts the operative
result: for the address and the evidence at hand, the realizable representation is a shallow node,
not a deep path.

## Conclusion

RQ3 asked where the address's relational context belongs — extracted deep at inference, or compiled
into the node. The measurement separates information from realizability: deeper context is
informationally more discriminative (oracle refinement toward singletons), but its recovery from an
image collapses with depth (per-hop reliability 0.40 → 0.05 → 0), so the realizable confusable set
saturates at one hop (median 13 → 8.2 → 8.1). The prior thesis's training-time finding corroborates
it — depth-≥2 supervision is wasted and costs `ifc_class` capacity — making the prescription
subtractive. The architecture therefore compiles depth into the node and extracts at depth ≤ 1,
placing learning at the neural→symbolic interface where shallow, recoverable evidence meets a
deterministic executor. The depth law is the architectural principle that makes the representation
of RQ1 and the mechanism of RQ2 realizable rather than merely informative.
