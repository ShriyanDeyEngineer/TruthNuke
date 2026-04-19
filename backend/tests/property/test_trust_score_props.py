"""
Property-based tests for TrustScoreBreakdown model serialization.

This module tests the round-trip serialization property for TrustScoreBreakdown objects,
ensuring that serializing to JSON and deserializing back produces equivalent objects.

**Validates: Requirements 15.1, 15.2**
"""

from hypothesis import given, strategies as st, settings

from app.models.schemas import TrustScoreBreakdown


# Strategy for generating valid sub-scores (integers 0-100)
sub_score_strategy = st.integers(min_value=0, max_value=100)


@st.composite
def trust_score_breakdown_strategy(draw):
    """
    Hypothesis composite strategy for generating valid TrustScoreBreakdown objects.
    
    Ensures that all four sub-scores are integers in the range [0, 100].
    """
    source_credibility = draw(sub_score_strategy)
    evidence_strength = draw(sub_score_strategy)
    language_neutrality = draw(sub_score_strategy)
    cross_source_agreement = draw(sub_score_strategy)
    
    return TrustScoreBreakdown(
        source_credibility=source_credibility,
        evidence_strength=evidence_strength,
        language_neutrality=language_neutrality,
        cross_source_agreement=cross_source_agreement,
    )


@given(breakdown=trust_score_breakdown_strategy())
@settings(max_examples=100)
def test_trust_score_serialization_round_trip(breakdown: TrustScoreBreakdown):
    """
    Property 11: TrustScore serialization round-trip.
    
    For any valid TrustScoreBreakdown object, serializing it to JSON and then
    deserializing the JSON string back into a TrustScoreBreakdown object should
    produce an object equivalent to the original.
    
    **Validates: Requirements 15.1, 15.2**
    
    This property ensures:
    1. TrustScoreBreakdown objects can be reliably serialized to JSON (Req 15.1)
    2. Deserialized TrustScoreBreakdown objects are equivalent to originals (Req 15.2)
    """
    # Serialize the TrustScoreBreakdown to JSON
    json_str = breakdown.model_dump_json()
    
    # Deserialize the JSON back to a TrustScoreBreakdown object
    deserialized_breakdown = TrustScoreBreakdown.model_validate_json(json_str)
    
    # Assert equivalence - all fields should match
    assert deserialized_breakdown.source_credibility == breakdown.source_credibility
    assert deserialized_breakdown.evidence_strength == breakdown.evidence_strength
    assert deserialized_breakdown.language_neutrality == breakdown.language_neutrality
    assert deserialized_breakdown.cross_source_agreement == breakdown.cross_source_agreement
    
    # Also verify full object equality
    assert deserialized_breakdown == breakdown


@given(breakdown=trust_score_breakdown_strategy())
@settings(max_examples=100)
def test_trust_score_dict_round_trip(breakdown: TrustScoreBreakdown):
    """
    Additional property: TrustScoreBreakdown dict serialization round-trip.
    
    For any valid TrustScoreBreakdown object, converting to dict and back should
    produce an equivalent object. This tests the model_dump/model_validate path.
    
    **Validates: Requirements 15.1, 15.2**
    """
    # Convert to dict
    breakdown_dict = breakdown.model_dump()
    
    # Reconstruct from dict
    reconstructed_breakdown = TrustScoreBreakdown.model_validate(breakdown_dict)
    
    # Assert equivalence
    assert reconstructed_breakdown == breakdown


@given(breakdown=trust_score_breakdown_strategy())
@settings(max_examples=100)
def test_trust_score_constraints_preserved(breakdown: TrustScoreBreakdown):
    """
    Property: TrustScoreBreakdown constraints are preserved through serialization.
    
    After round-trip serialization, all sub-scores should still be integers
    in the range [0, 100].
    
    **Validates: Requirements 15.1, 15.2**
    """
    # Serialize and deserialize
    json_str = breakdown.model_dump_json()
    deserialized_breakdown = TrustScoreBreakdown.model_validate_json(json_str)
    
    # Verify all sub-scores are integers in valid range
    assert isinstance(deserialized_breakdown.source_credibility, int)
    assert isinstance(deserialized_breakdown.evidence_strength, int)
    assert isinstance(deserialized_breakdown.language_neutrality, int)
    assert isinstance(deserialized_breakdown.cross_source_agreement, int)
    
    assert 0 <= deserialized_breakdown.source_credibility <= 100
    assert 0 <= deserialized_breakdown.evidence_strength <= 100
    assert 0 <= deserialized_breakdown.language_neutrality <= 100
    assert 0 <= deserialized_breakdown.cross_source_agreement <= 100
