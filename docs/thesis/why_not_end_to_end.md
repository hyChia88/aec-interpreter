# Why Not End-to-End Matching? — The Central Baseline

> **Thesis section draft.** Intended placement: immediately after the problem
> formulation / system overview, as the *motivating* argument for the structured
> spatial-address decomposition (before the methods chapters). It pre-empts the single
> most important reviewer question and converts it into the thesis motivation. Numbers
> are the held-out (Tier-3, n=60 cases / 59 elements) measurements; `[CITE]` marks
> references to fill. Prose is in thesis register — edit to taste.

---

## Framing

The grounding task reduces, at the final stage, to selecting one IFC element from a
retrieved candidate pool (median 76, ground-truth in-pool 100%). Stated this way, an
obvious objection arises, and it is the strongest objection the design must answer:

> *If the answer is already in the pool, why decompose the problem into an explicit,
> hand-specified spatial address (a wall slot, a connectivity fingerprint)? Why not
> train a single cross-attention model to compare the site evidence against the
> candidates directly and rank them end-to-end?*

This is not a strawman. It is the natural reflex of any reader with a machine-learning
background, and in its strongest "bitter-lesson" form [CITE: Sutton] it argues that
hand-engineered intermediate representations are an unnecessary bottleneck — that a
sufficiently large model should learn whatever internal representation the task
requires. We take the objection at full strength and answer it on four grounds, three
of which are empirical rather than rhetorical.

We first separate two distinct proposals that the term "cross-attention matching"
conflates. The first is **dense visual localization** — matching an evidence patch
against a floor plan to recover a metric position; we treat that separately (it is
precision-hungry and does not transfer across the image–graph boundary, §[localization
ablation]). The objection that concerns us here is the second: **end-to-end candidate
ranking** — skipping the structured address and learning to score the pool directly.

## The objection answered

**(1) The candidates are graph nodes, not images, and image-space matching does not
reach a GUID.** The retrieved candidates are nodes in the IFC graph; they carry no
photograph and no patch. To "compare patches" one must first *render* each candidate,
which presupposes the very registration the deployment setting denies, and which pits a
real site photograph against synthetic renders across a large domain gap. More
fundamentally, referring-expression and cross-attention grounding produce an answer in
*image* space — a region in the photograph or plan — whereas the target identity (the
GUID) lives in *graph* space, and the two are not co-registered. A model that grounds
perfectly in the image still stops at the image boundary. The only bridge that crosses
it is a representation that is independent of the image's coordinate frame: a
**coordinate-free relational address**. End-to-end matching does not remove this bridge;
it simply leaves it unbuilt.

**(2) The discriminative signal is relational, not pixel-local — so the end-to-end model
must reconstruct it anyway, only implicitly and unreliably.** What separates two
visually identical windows is not in either window's pixels; it is in the graph topology
("the third of five fillers along an external wall", "a wall of connection degree three").
A pixel-level matcher therefore has to *re-derive* this topological structure inside its
own weights — the very thing that is hard to do reliably from images, as the classical
opening-count baseline (~27% accuracy [CITE: thesis baseline]) illustrates. The
structured decomposition does not avoid the difficulty; it relocates it into an explicit,
inspectable, and reliable form. The contribution is to make explicit the relational
feature that a black-box matcher would otherwise have to rediscover with no guarantee and
no audit trail.

**(3) The end-to-end matcher is already our baseline, and it plateaus — for exactly this
reason.** The system's strongest purely-learned configuration (G8, a fine-tuned
multimodal reranker that consumes the site photograph, the text query, and the plan, and
re-orders the candidate pool) belongs to precisely the family this objection proposes.
On the held-out (Tier-3) set it reaches **Top-1 6.7% and Top-10 30.0%**, despite the
ground truth being present in the pool in **100%** of cases. The bottleneck is not recall
but ranking *inside* the pool. The diagnostic explains why: when the discriminating
spatial address is supplied at an oracle level, the same pool is reordered to **Top-1
78.5% / Top-10 98.1%** — a more than tenfold lift on Top-1 at zero recall cost — and the
gain is concentrated in exactly the address that the learned reranker fails to recover
(fillers reach Top-1 91%, walls 64%). The end-to-end approach is therefore not a
hypothetical alternative we declined to try; it is the measured baseline whose failure
mode the structured address is designed to repair.

**(4) Convenience is the wrong axis; the deployment constraints are auditability,
calibration, and transfer.** Even were a black-box matcher to match the structured
system on raw accuracy, a scalar matching score (e.g. 0.87) is not auditable, not
correctable, and cannot be gated by per-field calibrated confidence. The structured
address is the artefact that makes the rest of the architecture possible: a per-field
`{value, confidence, source}` contract, selective prediction with an explicit
coverage–accuracy trade-off [CITE: selective prediction], a symbolic guardrail that
cannot emit an element type absent from the ontology, and an explanation a domain user
can verify ("selected because the evidence indicates the third of five windows on the
external wall"). In a setting where element identification carries downstream
consequences, this is not a convenience to be traded away — it is the requirement.
Relatedly, the address transfers: "the third of five along the host wall" is computable
on any IFC model with no retraining, whereas a matcher trained on one project's geometry
and visual style must be retrained for the next. The decomposition buys zero-shot
cross-project generalization; the dense matcher does not.

## The honest boundary of the claim

We do not claim that the structured decomposition beats end-to-end matching on raw
accuracy in the large-data, large-model limit; the bitter lesson may well hold there. We
make a narrower and, we argue, more relevant claim along three axes. *Data regime:* paired
(site-evidence, ground-truth-element) supervision is genuinely scarce in cold-start AEC
deployments, and in the regime we can actually measure, the end-to-end model plateaus
(6.7%). *Deployment:* even at parity, auditability, calibration, and cross-project
transfer are hard constraints a black-box score cannot satisfy. *Scientific contribution:*
the result we report — *what* the minimal sufficient spatial address is for a given
confusable set, and *where* an end-to-end matcher fails to recover it — is knowledge that
stands independently of which method wins a leaderboard.

## Conclusion

The "why not end-to-end?" question is real, and it is the central tension of the work:
end-to-end accuracy versus auditable, transferable grounding. Rather than avoid it, we
adopt the end-to-end multimodal matcher as our explicit baseline, show empirically that
it plateaus with the answer already in the pool, demonstrate via oracle analysis that the
missing ingredient is the reliably-recovered relational address, and argue that even at
accuracy parity the structured intermediate is required by the deployment constraints and
by the image-to-graph gap that no image-space matcher can cross. The objection, answered
this way, is not a weakness of the design but its motivation.
