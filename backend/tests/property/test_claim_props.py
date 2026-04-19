"""
Property-based tests for Claim model serialization and index validation.

This module tests:
- Round-trip serialization property for Claim objects (Property 10)
- Claim index invariant and substring correspondence (Property 3)

**Validates: Requirements 2.3, 2.4, 14.1, 14.2**
"""

from hypothesis import given, strategies as st, settings

from app.models.schemas import Claim
from app.services.claim_extractor import ClaimExtractor


# Define valid claim types as per the design document
VALID_CLAIM_TYPES = ["banking", "market", "investment", "crypto", "economic"]


# Strategy for generating valid UUIDs as strings
uuid_strategy = st.uuids().map(str)


# Strategy for generating non-empty text strings
text_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


# Strategy for generating entity lists
entities_strategy = st.lists(
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    min_size=0,
    max_size=5,
)


# Strategy for generating valid claim types
claim_type_strategy = st.sampled_from(VALID_CLAIM_TYPES)


@st.composite
def claim_strategy(draw):
    """
    Hypothesis composite strategy for generating valid Claim objects.
    
    Ensures that:
    - start_index >= 0
    - end_index > start_index (so end_index > 0)
    - All required fields are populated with valid values
    """
    claim_id = draw(uuid_strategy)
    text = draw(text_strategy)
    claim_type = draw(claim_type_strategy)
    entities = draw(entities_strategy)
    
    # Generate valid index pair where start_index >= 0 and start_index < end_index
    # We use a reasonable range for indices
    start_index = draw(st.integers(min_value=0, max_value=10000))
    # end_index must be greater than start_index (and thus > 0)
    end_index = draw(st.integers(min_value=start_index + 1, max_value=start_index + 10001))
    
    return Claim(
        id=claim_id,
        text=text,
        start_index=start_index,
        end_index=end_index,
        type=claim_type,
        entities=entities,
    )


@given(claim=claim_strategy())
@settings(max_examples=100)
def test_claim_serialization_round_trip(claim: Claim):
    """
    Property 10: Claim serialization round-trip.
    
    For any valid Claim object, serializing it to JSON and then deserializing
    the JSON string back into a Claim object should produce an object
    equivalent to the original.
    
    **Validates: Requirements 14.1, 14.2**
    
    This property ensures:
    1. Claim objects can be reliably serialized to JSON (Req 14.1)
    2. Deserialized Claims are equivalent to originals (Req 14.2)
    """
    # Serialize the Claim to JSON
    json_str = claim.model_dump_json()
    
    # Deserialize the JSON back to a Claim object
    deserialized_claim = Claim.model_validate_json(json_str)
    
    # Assert equivalence - all fields should match
    assert deserialized_claim.id == claim.id
    assert deserialized_claim.text == claim.text
    assert deserialized_claim.start_index == claim.start_index
    assert deserialized_claim.end_index == claim.end_index
    assert deserialized_claim.type == claim.type
    assert deserialized_claim.entities == claim.entities
    
    # Also verify full object equality
    assert deserialized_claim == claim


@given(claim=claim_strategy())
@settings(max_examples=100)
def test_claim_dict_round_trip(claim: Claim):
    """
    Additional property: Claim dict serialization round-trip.
    
    For any valid Claim object, converting to dict and back should produce
    an equivalent object. This tests the model_dump/model_validate path.
    
    **Validates: Requirements 14.1, 14.2**
    """
    # Convert to dict
    claim_dict = claim.model_dump()
    
    # Reconstruct from dict
    reconstructed_claim = Claim.model_validate(claim_dict)
    
    # Assert equivalence
    assert reconstructed_claim == claim


@given(claim=claim_strategy())
@settings(max_examples=100)
def test_claim_index_constraints_preserved(claim: Claim):
    """
    Property: Claim index constraints are preserved through serialization.
    
    After round-trip serialization, the index constraints should still hold:
    - start_index >= 0
    - end_index > start_index (which implies end_index > 0)
    
    **Validates: Requirements 14.1, 14.2**
    """
    # Serialize and deserialize
    json_str = claim.model_dump_json()
    deserialized_claim = Claim.model_validate_json(json_str)
    
    # Verify index constraints are preserved
    assert deserialized_claim.start_index >= 0
    assert deserialized_claim.end_index > 0
    assert deserialized_claim.start_index < deserialized_claim.end_index


# ============================================================================
# Property 3: Claim index invariant and substring correspondence
# ============================================================================


@st.composite
def text_with_valid_indices_strategy(draw):
    """
    Hypothesis composite strategy for generating random text with valid index pairs.
    
    Generates:
    - A random text string (at least 1 character)
    - A valid start_index (>= 0)
    - A valid end_index (> start_index and <= len(text))
    
    Returns a tuple of (text, start_index, end_index).
    """
    # Generate a non-empty text string
    text = draw(st.text(min_size=1, max_size=500))
    
    # Generate valid index pair within the text bounds
    text_len = len(text)
    
    # start_index must be >= 0 and < text_len (to allow at least one character)
    start_index = draw(st.integers(min_value=0, max_value=text_len - 1))
    
    # end_index must be > start_index and <= text_len
    end_index = draw(st.integers(min_value=start_index + 1, max_value=text_len))
    
    return (text, start_index, end_index)


@given(data=text_with_valid_indices_strategy())
@settings(max_examples=100)
def test_claim_index_invariant_and_substring_correspondence(data):
    """
    Property 3: Claim index invariant and substring correspondence.
    
    For any valid Claim produced by the Claim Extractor against a source text:
    - start_index must be >= 0
    - start_index must be < end_index
    - source_text[start_index:end_index] must equal claim.text
    
    This test generates random text and valid index pairs, constructs Claim objects
    with the substring as the text, and uses ClaimExtractor._validate_claim_indices()
    to validate the claim.
    
    **Validates: Requirements 2.3, 2.4**
    """
    text, start_index, end_index = data
    
    # Extract the substring from the text using the indices
    claim_text = text[start_index:end_index]
    
    # Create a Claim object with the substring as the text
    claim = Claim(
        id="test-claim-id",
        text=claim_text,
        start_index=start_index,
        end_index=end_index,
        type="economic",  # Valid claim type
        entities=[],
    )
    
    # Verify the index invariants directly
    assert claim.start_index >= 0, "start_index must be >= 0"
    assert claim.start_index < claim.end_index, "start_index must be < end_index"
    assert text[claim.start_index:claim.end_index] == claim.text, \
        "substring must match claim text"
    
    # Use ClaimExtractor._validate_claim_indices() to validate the claim
    # This is a static method that can be called without an instance
    # We need to create a minimal extractor instance to call the method
    # Since _validate_claim_indices is an instance method, we'll call it directly
    # by creating a mock extractor or calling the validation logic
    
    # Create a minimal ClaimExtractor instance (llm_client is not used for validation)
    # We can pass None since _validate_claim_indices doesn't use llm_client
    extractor = ClaimExtractor(llm_client=None)  # type: ignore
    
    # Validate the claim indices using the extractor's validation method
    is_valid = extractor._validate_claim_indices(claim, text)
    
    assert is_valid, (
        f"Claim validation failed for text='{claim_text}', "
        f"start_index={start_index}, end_index={end_index}"
    )


@given(
    text=st.text(min_size=1, max_size=500),
    start_offset=st.integers(min_value=0, max_value=100),
    length=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100)
def test_claim_index_invariant_with_varying_lengths(text, start_offset, length):
    """
    Property 3 (variant): Claim index invariant with varying substring lengths.
    
    Tests the index invariant property with different substring lengths,
    ensuring that the validation works correctly for claims of various sizes.
    
    **Validates: Requirements 2.3, 2.4**
    """
    # Skip if text is too short for the requested indices
    if len(text) == 0:
        return
    
    # Adjust start_offset to be within text bounds
    start_index = start_offset % len(text)
    
    # Calculate end_index, ensuring it doesn't exceed text length
    # and is greater than start_index
    max_length = len(text) - start_index
    actual_length = min(length, max_length)
    
    # Ensure we have at least 1 character
    if actual_length < 1:
        return
    
    end_index = start_index + actual_length
    
    # Extract the substring
    claim_text = text[start_index:end_index]
    
    # Create the Claim object
    claim = Claim(
        id="test-claim-id",
        text=claim_text,
        start_index=start_index,
        end_index=end_index,
        type="market",
        entities=[],
    )
    
    # Verify invariants
    assert claim.start_index >= 0
    assert claim.start_index < claim.end_index
    assert text[claim.start_index:claim.end_index] == claim.text
    
    # Validate using ClaimExtractor
    extractor = ClaimExtractor(llm_client=None)  # type: ignore
    assert extractor._validate_claim_indices(claim, text)
