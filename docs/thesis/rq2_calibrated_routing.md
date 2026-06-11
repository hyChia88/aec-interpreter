# RQ2 — From an Oracle Ceiling to a Realizable, Auditable Address: Calibrated Soft-Routing

> **Thesis section draft.** Intended placement: the mechanism chapter, immediately after
> the spatial-address representation (RQ1) and its oracle ceiling have been established, and
> after [`why_not_end_to_end.md`](why_not_end_to_end.md) has motivated the decomposition.
> RQ1 asks *what* the minimal sufficient address is; RQ2 asks *how much of it survives
> extraction noise, and how to use a partly-recoverable address without losing recall.*
> Numbers are held-out (Tier-3, n = 60 cases / 59 elements; 35 addressable fillers) and trace
> to `docs/results_ledger.md` (P1 Steps B/C). Figures: `output/pipeline.png` (method spine),
> `output/calibration_diag.png` (ECE gate), `output/calibrate_rerank.png` (soft-rerank +
> selective prediction), `output/demo/case_AP_SK_092.png` (a worked DEFER case). `[CITE]`
> marks references to fill. Prose is in thesis register — edit to taste.

---

## The question RQ2 must answer

The representation chapter (RQ1) establishes that a type-conditional spatial address — the
position-slot `(i, M)` for a filler, the connectivity fingerprint for a wall — collapses the
visual-confusable set almost completely *when supplied at an oracle level*: the retrieved pool
(median 76, ground truth in-pool 100 %) reorders from a realized Top-1 of 6.7 % to **78.5 %**
(fillers to 91 %), with the ground truth in the pool throughout.
That ceiling is a statement about *information*: the address, if known, suffices. It says
nothing about whether the address can be **recovered** from a site photograph and a plan, nor
how a *noisily* recovered address should be used. RQ2 is the gap between the two:

> *How much of the oracle ceiling is realizable once the address is extracted by a real,
> imperfect detector — and how is a partly-reliable address consumed without destroying the
> recall that the pool guarantees?*

The honest baseline is stark. The thesis reranker (G8) emits the position field as free text
and, on the held-out fillers, recovers a usable slot in **0 of 35** cases. With no slot signal
the pool-ranking falls back to storey and class, a Top-1 of **2.4 %**; even a modal-prior slot
guess — the most generous floor — reaches only **6.6 %** (G8's overall held-out Top-1 is 6.7 %).
The oracle says 91; the system delivers single digits. RQ2 is the work of closing that.

## The recall constraint: why the address must be a soft prior, not a hard filter

The intuitive way to use an extracted address is to *filter* the pool by it — keep only
candidates whose slot matches. This is exactly wrong, and the measurement says why. Treating
each extracted field as a hard constraint multiplies the per-field recall: with measured
single-field reliabilities (storey ≈ 0.66, class ≈ 0.50), the joint recall of a hard
conjunction *over the measured attribute fields* collapses toward **∏ r ≈ 0.009**; the
position-slot's own extraction reliability is unmeasured, but its realized 0-of-35 recovery
makes it no exception. The filter evicts the ground
truth from the pool far more often than it removes a distractor, and the 100 %-recall
guarantee that made the task tractable is gone. Hard determinism and recall are in direct
opposition.

The resolution — and the first refinement RQ2 forces on its own original "deterministic
retrieval" framing — is to relocate determinism. **The executor is deterministic given the
structured record; the *ranking* is a calibrated soft prior inside a recall-fixed pool.** The
address never removes a candidate; it re-weights one. Recall stays at 100 % by construction,
and the unreliable signal is spent only on *ordering*. This is the mechanism the rest of the
section makes precise and measures.

## The mechanism: a per-field confidence contract, calibrated, routed

Every extracted field is emitted as a uniform record `{value, confidence, source}` (the
contract invariant; it closes the two extraction-confidence gaps noted in the system's own
limitations — confidence underused, and no per-model calibration). The position-slot detector, a deterministic
OpenCV specialist that color-segments the plan's openings and orders them along the host wall,
produces `value = (i, M)`, a `confidence`, and `source = opencv`. A routing policy assigns each
field a role and a weight; the recovered slot enters the rerank as a confidence-weighted prior,
and — crucially — a low-confidence extraction can route to **defer** ("I am not sure; here are
the candidates") rather than to a confident wrong answer. The pipeline is summarized in
`output/pipeline.png`, with the confidence-routing path traced from the detector's
`{confidence}` to the answer/defer gate; that path *is* the determinism↔adaptivity mechanism.

We report four results.

**(1) One realizable extractor closes most of the oracle gap.** The position-slot detector,
scored against the image-recoverable convention (below), recovers the opening count exactly in
**83 %** of cases (29/35) and the full slot in **74 %** (joint `(i, M)`). Fed into the soft
rerank, it lifts filler Top-1 from the **6.6 %** modal-prior floor to **67.6 %**, and Top-10 to
**80.9 %**, at zero recall cost — the floor-to-realized arc the oracle gap predicted, now
delivered by a real detector rather than an oracle. The *count* is reliable; what residual
error remains is concentrated in the ordering index, not in the perception of the openings.

**(2) The confidence is calibratable — the routing premise holds, and is not assumed.** Before
any routing we gate on calibration `[CITE: Guo et al.]`: a routing layer is only legitimate if
its confidence tracks correctness. On the held-out fillers the raw detector confidence is
positively discriminative (AUROC **0.80**: more-confident extractions are more often correct)
and only moderately mis-calibrated (ECE **0.206**); temperature scaling reduces it to **0.172**
(`output/calibration_diag.png`). The premise is established empirically, not asserted. We note
this gate is load-bearing: had the confidence been anti-correlated, no monotone recalibration
could rescue it, and the gain would have shifted to the schema-alignment and visual specialists
(the contingency we named in advance and did not need to invoke).

**(3) An honest negative: continuous reweighting is a no-op — the calibration does not pay off
as a rerank weight.** With storey and class contributing integer agreement and the slot acting
as the *finest* tiebreaker, any strictly-positive weight on a slot match induces the identical
ordering within a storey×class bucket; the hard match (weight 1), the raw-confidence weight,
and the temperature-calibrated weight all yield the same **67.6 %** Top-1. Reweighting cannot
reorder what only a *removal* of the term would change. We report this rather than bury it:
the value of the calibrated confidence is not in the soft weight.

**(4) The payoff is selective prediction — the practical mechanism and the triage value
proposition.** The calibrated confidence pays off as a *deferral* threshold. Sweeping it traces
a coverage–accuracy curve (`output/calibrate_rerank.png`): deferring the least-confident ~20 %
of cases lifts Top-1 on the answered subset from **67.6 % to 80.6 %**. The system does not
return a confident wrong GUID; it abstains and surfaces the candidates. A worked case makes the
mechanism concrete (`output/demo/case_AP_SK_092.png`): the detector predicts slot 1 of 10 where
the truth is 8 of 10 — an error — but its calibrated confidence is **0.05**, below threshold, so
the case routes to *defer* rather than to a confident mistake. For a triage tool whose output
carries downstream consequence, "here are the nine candidates" at a known accuracy is the
correct behavior, and the coverage–accuracy curve — not a single point estimate — is the honest
way to report it `[CITE: selective prediction]`.

## A representational prerequisite: the address must be image-recoverable, not model-arbitrary

Realizability has a precondition that the oracle analysis hides. The ground-truth slot index in
the source data is numbered along each wall's **IFC local-X axis** — a modelling artefact whose
sign is invisible in any image. A detector reading the plan cannot recover which end of the wall
the modeller chose as "first"; scored against that convention, the detector and ground truth
disagree on **16 of 35** fillers, *all* exact mirrors `i ↦ M-1-i` (the count `M` is identical).
The index, so defined, fails the address's own *image-recoverable* criterion. The remedy is to
fix the slot's orientation by an **image-coordinate** convention — number from a world reference
direction shared by both the detector and the ground truth — under which the disagreement
vanishes and joint accuracy rises from an apparent 34 % to the true **74 %**. This is not
bookkeeping: it is a substantive constraint on what a deployable spatial address may be. An
address field is realizable only if it is defined in a frame the evidence carries; a field keyed
to an arbitrary modelling choice is, by construction, unrecoverable. The same property is what
lets the index survive the eventual patch-upload setting — a north-up plan crop encodes the
reference orientation, whereas the IFC local axis never appears in any image.

## The honest boundary of the claim

Three caveats bound the result. *Statistical power:* the calibration and coverage–accuracy
estimates rest on 35 addressable fillers; the curve is clean down to ~0.74 coverage and noisy
below, and the temperature estimate carries small-n uncertainty — we report the operating point
(defer ~20 % → 80.6 %), not a precise optimal threshold. *Scope:* we realize and calibrate the
single highest-value extractor (the position-slot); the wall fingerprint and the remaining
address descriptors are demonstrated only at oracle level, and their realization is future work.
*Mechanism honesty:* the headline is selective prediction, not soft reweighting — the latter we
report as a measured no-op, and we explicitly do *not* lead with "we added calibration", which
the calibratability gate supports but does not, on its own, deliver.

## Conclusion

RQ2 asked how much of the oracle ceiling is realizable, and how a noisy address is used without
losing recall. The answers are concrete and, where they cut against the obvious design, honest.
Recall is preserved by making the address a soft prior inside a recall-fixed pool, never a hard
filter (the ∏ r collapse forbids the latter). One real extractor closes most of the oracle gap
(6.6 → 67.6 % Top-1). Its confidence is calibratable (AUROC 0.80; ECE 0.206 → 0.172), so the
routing premise holds. Reweighting that confidence is a no-op; its genuine payoff is selective
prediction, where deferring the least-confident fifth lifts answered-set accuracy to 80.6 %.
And realizability itself imposes a representational constraint — the address must be defined in
an image-recoverable frame — without which the apparent accuracy is halved by a convention the
camera cannot see. The mechanism is therefore not "deterministic retrieval" but its disciplined
replacement: **auditable, deterministic execution over a calibrated, recall-safe, selectively-
predicted spatial address.**
