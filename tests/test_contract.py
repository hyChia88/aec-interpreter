"""Per-field confidence contract: adapter from legacy Constraints + invariants."""
from aec_interpreter.neurosym.types import Constraints, SpatialTriplet
from aec_interpreter.schema.contract import ConstraintContract, FieldValue, from_legacy


def _legacy() -> Constraints:
    return Constraints(
        storey_name="1",
        ifc_class="IfcWallStandardCase",
        position_context="3rd of 17 openings",
        position_context_confidence=0.9,
        position_context_source="opencv",
        size_band="window_M",
        size_band_confidence=0.8,
        size_band_source="resnet_opencv",
        spatial_relations=[
            SpatialTriplet(subject_type="IfcWindow", predicate="ADJACENT_TO",
                           object_type="IfcRailing", confidence=0.7)
        ],
        source="lora",
    )


def test_adapter_carries_value_confidence_source():
    c = from_legacy(_legacy())
    # field with no legacy confidence: value carried, confidence None, source from extractor
    assert c.ifc_class.value == "IfcWallStandardCase"
    assert c.ifc_class.confidence is None
    assert c.ifc_class.source == "vlm"  # source=="lora" -> vlm
    # position_context: confidence + specialist source carried
    assert c.position_context.confidence == 0.9
    assert c.position_context.source == "opencv"
    # size_band: confidence + resnet source
    assert c.size_band.confidence == 0.8
    assert c.size_band.source == "resnet_opencv"
    assert c.extraction_source == "lora"


def test_spatial_triplets_carry_their_confidence():
    c = from_legacy(_legacy())
    assert len(c.spatial_relations) == 1
    sr = c.spatial_relations[0]
    assert sr.confidence == 0.7
    assert sr.source == "vlm"
    assert sr.value["predicate"] == "ADJACENT_TO"


def test_routable_fields_only_present():
    c = from_legacy(_legacy())
    routable = c.routable_fields()
    assert "ifc_class" in routable and "storey_name" in routable
    assert "space_name" not in routable  # absent in legacy -> not routable


def test_field_defaults_and_role():
    fv = FieldValue()
    assert fv.value is None and fv.confidence is None
    assert fv.source == "unknown" and fv.role == "unset"
    assert not fv.present
    assert FieldValue(value="x").present


def test_empty_contract_is_valid():
    c = ConstraintContract()
    assert c.routable_fields() == {}
    assert c.spatial_relations == []
