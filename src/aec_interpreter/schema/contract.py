"""
Per-field confidence contract — the enabling substrate for P1 calibrated routing.

The thesis carried confidence on only two fields (`position_context`, `size_band`) via
ad-hoc `_confidence` / `_source` suffixes. P1 routing needs EVERY routable field to carry
its confidence + provenance uniformly, so the policy can assign each a role
{hard_filter / soft_prior / drop / clarify}. This module defines that uniform contract
plus an adapter from the legacy flat `neurosym.types.Constraints`.

Design: one wrapper `FieldValue = {value, confidence, source, role}` per attribute.
Confidence sources differ per field (VLM logprob, OpenCV score, ResNet, schema-alignment)
— the contract only *carries* it; populating + calibrating it is the extractor/P1 job.

Closes `neurosym/README.md` limitations #4 (confidence underused) and #10 (no per-model
calibration) at the contract level.
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

# Routing role assigned by the P1 policy (controlled vocabulary we own; unset until routed).
FieldRole = Literal["hard_filter", "soft_prior", "drop", "clarify", "unset"]

# Provenance string — open-ended (legacy specialists emit values like "resnet_opencv",
# "resnet_oracle_centroid"). Conventional roots: vlm | opencv | resnet | schema_align |
# prompt | unknown. Kept as free str so real provenance strings pass through unchanged.
FieldSource = str


class FieldValue(BaseModel):
    """A single extracted attribute with routing-relevant metadata.

    value:      extracted value (None = not extracted / absent)
    confidence: [0,1], or None when no confidence signal exists for this field yet
    source:     provenance of the value/confidence
    role:       routing decision assigned by the P1 policy (unset until routed)
    """

    model_config = ConfigDict(extra="forbid")

    value: Optional[Any] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: FieldSource = "unknown"
    role: FieldRole = "unset"

    @property
    def present(self) -> bool:
        return self.value not in (None, "", [], {})


class ConstraintContract(BaseModel):
    """All routable constraints, each carrying {value, confidence, source, role}.

    `spatial_relations` is a list of FieldValue whose `value` is a spatial-triplet dict
    (each legacy SpatialTriplet already carries its own confidence).
    """

    model_config = ConfigDict(extra="forbid")

    storey_name: FieldValue = Field(default_factory=FieldValue)
    ifc_class: FieldValue = Field(default_factory=FieldValue)
    space_name: FieldValue = Field(default_factory=FieldValue)
    position_context: FieldValue = Field(default_factory=FieldValue)
    size_cluster: FieldValue = Field(default_factory=FieldValue)
    size_band: FieldValue = Field(default_factory=FieldValue)
    target_name_keyword: FieldValue = Field(default_factory=FieldValue)
    spatial_relations: List[FieldValue] = Field(default_factory=list)

    # extractor that produced this contract ("lora" | "prompt" | "gemini" | ...)
    extraction_source: str = "unknown"

    # ── routable scalar fields, in planner-priority-ish order ──
    SCALAR_FIELDS: ClassVar[Tuple[str, ...]] = (
        "storey_name", "ifc_class", "space_name",
        "position_context", "size_cluster", "size_band", "target_name_keyword",
    )

    def routable_fields(self) -> dict[str, FieldValue]:
        """Present scalar fields eligible for routing."""
        return {f: getattr(self, f) for f in self.SCALAR_FIELDS if getattr(self, f).present}


def from_legacy(constraints: Any) -> ConstraintContract:
    """Adapt a legacy `neurosym.types.Constraints` into the uniform contract.

    Carries through the two fields that already had confidence (position_context,
    size_band); other fields get confidence=None (no signal yet) with the legacy
    extraction source. Spatial triplets carry their per-triplet confidence.
    """
    src = getattr(constraints, "source", "unknown") or "unknown"
    legacy_src: FieldSource = "vlm" if src == "lora" else ("prompt" if src == "prompt" else "unknown")

    def fv(value: Any, confidence: Optional[float] = None,
           source: FieldSource = legacy_src) -> FieldValue:
        return FieldValue(value=value, confidence=confidence, source=source)

    spatial = [
        FieldValue(value=t.model_dump(), confidence=getattr(t, "confidence", None) or None, source="vlm")
        for t in getattr(constraints, "spatial_relations", []) or []
    ]

    return ConstraintContract(
        storey_name=fv(getattr(constraints, "storey_name", None)),
        ifc_class=fv(getattr(constraints, "ifc_class", None)),
        space_name=fv(getattr(constraints, "space_name", None)),
        position_context=fv(
            getattr(constraints, "position_context", None),
            getattr(constraints, "position_context_confidence", None),
            source=(getattr(constraints, "position_context_source", None) or "opencv")
            if getattr(constraints, "position_context", None) else legacy_src,
        ),
        size_cluster=fv(getattr(constraints, "size_cluster", None)),
        size_band=fv(
            getattr(constraints, "size_band", None),
            getattr(constraints, "size_band_confidence", None),
            source=(getattr(constraints, "size_band_source", None) or "resnet")
            if getattr(constraints, "size_band", None) else legacy_src,
        ),
        target_name_keyword=fv(getattr(constraints, "target_name_keyword", None)),
        spatial_relations=spatial,
        extraction_source=src,
    )
