# RQ1 — The Minimal Sufficient Spatial Address: A Type-Conditional, Image-Recoverable Key

> **Thesis section draft.** Intended placement: the first results chapter (representation),
> before the mechanism chapter ([`rq2_calibrated_routing.md`](rq2_calibrated_routing.md)) and
> after the central baseline ([`why_not_end_to_end.md`](why_not_end_to_end.md)). RQ1 asks *what*
> the discriminating representation is; RQ2 asks *how much of it survives extraction*. All numbers
> are oracle (r = 1) measurements on the AP held-out pools (60 targets / 59 elements, Tier-3) and
> trace to `docs/results_ledger.md` (Idea 3a attribute ceiling, Idea 3c spatial-address ceiling,
> depth-saturation). The single external citation (the IFC4x3 standard) is a verified `\cite{}`
> key in `references.bib`. Prose is in thesis register — edit to taste.

---

## The question: what uniquely identifies an element among its look-alikes?

The grounding task ends by selecting one IFC element from a retrieved candidate pool in which the
ground truth is always present (median 76, in-pool 100 %). The difficulty is not recall but
*discrimination among visually identical siblings*: a curtain-wall façade is a row of near-identical
windows; a floor is a run of indistinguishable doors. We formalize this as the **confusable set**.
For a target element *e*, let

> **C(e)** = the set of pool elements sharing *e*'s **coarse fingerprint** — same building storey
> and same IFC class — i.e. the elements a coarse ontological filter cannot tell apart.

RQ1 asks for the **minimal sufficient spatial address**: the smallest descriptor set that uniquely
identifies *e* within C(e), subject to two deployment constraints that make the address *usable*
rather than merely *distinguishing*. The address must be **IFC-computable** (derivable from the BIM
model with no human labelling, so it exists on day one of a cold-start deployment) and
**image-recoverable** (estimable from a site photograph and a plan, so a real extractor can in
principle recover it — the constraint RQ2 then tests). A descriptor that distinguishes but cannot be
computed, or computes but cannot be seen, does not answer RQ1.

## The coarse floor saturates: ontology alone cannot separate siblings

The natural first descriptor is the ontology itself — storey and IFC class. It is necessary but
nowhere near sufficient. Restricting the pool to the target's storey and class leaves a **median
confusable set of 46** (mean 112) and an oracle Top-1 of only **4.9 %** — *below* the realized
G8 reranker (6.7 %), and essentially equal to it on Top-10 (oracle 31.5 % vs realized 30.0 %). The
coarse fingerprint is **saturated**: supplying it at an oracle level buys nothing the learned system
does not already have, because it cannot separate elements that are, by construction, of the same
class on the same floor. Ontology is the *floor*, not the discriminator.

Adding the richest available *attribute* — the Revit family/type string `object_type` — shrinks the
confusable set to a **median of 13** (a 3.8× reduction) and lifts oracle Top-10 to 76 %, but it
plateaus on Top-1: only **2 of 60** targets are uniquely identified by attributes alone. Attributes
narrow; they do not single out. What remains after attributes is the irreducibly *relational*
residue — which of the thirteen identical-looking siblings is *this* one — and that residue is where
the address must live.

## The headline finding: the address is type-conditional

The central result of this chapter is that **the minimal sufficient address is not uniform across
element classes — it is conditional on the element's type**, because what makes two elements
distinguishable differs by what kind of thing they are. Two descriptors, each the address for its
class, close the gap:

- **Fillers (windows, doors)** are identified by their **position-slot** `(i, M)`: the target is the
  *i*-th of *M* openings ordered along its host wall. A window is pinned not by its own appearance
  but by its ordinal place in a row.
- **Walls** are identified by a **connectivity fingerprint** —
  `(connection_degree, hosted_opening_count, length_band, is_external)`: how many walls it joins, how
  many openings it hosts, its length band, and whether it is on the building envelope. Within the
  same-storey walls, this collapses a median confusable set of **110 → 2** (uniquely identifying
  10 of 22 walls, where `object_type` identifies 0).

Supplied at an oracle level, this type-conditional address takes the *real retrieved pool* from a
coarse Top-1 of 4.9 % to **78.5 %**, and Top-10 from 31.5 % to **98.1 %** (MRR 0.137 → 0.854), at
zero recall cost — a more than fifteen-fold lift on Top-1 over the coarse floor. The gain decomposes
exactly along the type-conditional split: **fillers reach Top-1 91.0 %** (position-slot),
**walls 64.2 %** (fingerprint). No single uniform descriptor achieves this; the position-slot is
meaningless for a wall, and the connectivity fingerprint is degenerate for a window. The answer to
"is the address element-class-conditional?" is an empirical *yes*, and the conditioning is the
contribution.

## Why depth-1 suffices: the address is a node, not a path

A relational address invites the question of *how relational* — how many hops of graph context the
representation needs. The measurement is decisive: the oracle confusable set shrinks from a median
of 13 (attributes) to **8.2 at one hop**, then to **8.1** and **8.1** at two and three hops. Almost
all realizable discrimination is recovered at **depth 1**, and deeper context adds essentially
nothing, because the per-hop reliability of recovering a *named* multi-hop relation from an image
collapses (the same evidence that motivates extracting at depth ≤ 1 in RQ3). The address therefore
has two equivalent forms — a **depth-1 sub-graph** (the target node, its directly-related neighbours,
and the edge types) and the **distilled `node.val` attributes** hung on the target — and the two
carry the same information. We match on the node attributes and derive them from the sub-graph; no
deep graph and no learned graph fusion is required. The relations needed are few:
`FILLS` and `NEXT_TO` for the filler address, `CONNECTS_TO` and the reverse of `FILLS` for the wall
address, with `ADJACENT_TO` as generic proximity — sufficient for the two solved classes.

## The address satisfies its own two constraints

The two deployment constraints are not assumed; they are checked.

**IFC-computable.** Every address field is reconstructed directly from the raw IFC model
(`AdvancedProject.ifc`) via `ifcopenshell` — the position-slot from the `IfcRelFillsElement` /
`IfcRelVoidsElement` chains, the wall fingerprint from `IfcRelConnectsPathElements` and the hosted
openings \cite{buildingsmart2024ifc4x3}. The reconstruction is validated against the dataset's own
skeleton: the recovered wall `connection_degree` matches the ground-truth skeleton in **14 of 14**
checked cases. The address exists for every element with no human annotation — the cold-start
property the system claims.

**Image-recoverable.** Each field is defined in a frame the evidence carries. The wall fingerprint's
constituents are visible structure (junctions, hosted openings, length, envelope position); the
position-slot is read by ordering the plan's openings along the host wall. Crucially, the slot's
ordinal must be numbered by an **image-coordinate** convention, not the wall's arbitrary IFC local
axis, or it ceases to be recoverable — the representational prerequisite established quantitatively
in RQ2. Image-recoverability is thus a *design constraint on the address*, not an afterthought: a
field keyed to an invisible modelling choice is excluded by construction.

## The honest boundary of the claim

Four caveats bound the representation result. *Oracle level:* every number here assumes perfect
extraction (r = 1); it establishes the *ceiling*, and what fraction is *realizable* under a real
detector is the separate question RQ2 answers (fillers: oracle 91 → realized 67.6). *Class coverage:*
the address is closed for fillers and walls — the bulk of the targets — but **3 "other"-class**
targets and room/space addressing remain open; notably the model exposes no `IfcRelSpaceBoundary`
(rooms are unnamed in this synthetic export), so space-relative addressing is future work, not a
claim of universal completeness. *Single project:* the ceiling is measured on one synthetic AP
model; the *form* of the address (type-conditional, topology-derived) is general, but the specific
descriptor reliabilities are project-specific. *Descriptor sweep:* we report the position-slot and
the connectivity fingerprint; a fuller sweep of candidate descriptors (junction type, generated
cell, landmark-relative) with per-descriptor extractability scoring is left to future work.

## Conclusion

RQ1 asked what minimally and sufficiently identifies an IFC element among its visual look-alikes,
under the constraints that the descriptor be model-computable and evidence-recoverable. The answer
is a **type-conditional spatial address**: a coarse ontological prefix (storey + class) that is
necessary but saturated, completed by a class-specific topological body — the position-slot for
fillers, the connectivity fingerprint for walls. Supplied at an oracle level it reorders the
candidate pool from Top-1 4.9 % to **78.5 %** at no recall cost, with the gain partitioned cleanly
by element type; the discrimination saturates at one graph hop, so the address compiles into a node
rather than a path; and it is verified to be both IFC-computable (14/14 against the skeleton) and
image-recoverable (under the right ordinal convention). The representation is the thesis's primary
contribution — *what* the minimal sufficient address is, and *that* it is class-conditional — and it
stands independently of how reliably any particular detector recovers it.
