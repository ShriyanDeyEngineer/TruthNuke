"""
Property-based tests for Classifier output validity.

This module tests:
- Property 7: Classification output validity

**Validates: Requirements 5.1, 5.2**
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
    SearchResult,
)
from app.services.classifier import Classifier
from app.services.llm_client import LLMClient


# Define valid claim types as per the design document
VALID_CLAIM_TYPES = ["banking", "market", "investment", "crypto", "economic"]

# Define valid classification labels
VALID_CLASSIFICATION_LABELS = ["VERIFIED", "MISLEADING", "LIKELY_FALSE", "HARMFUL"]


# ============================================================================
# Hypothesis Strategies
# ============================================================================


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


# Strategy for generating valid classification labels
classification_label_strategy = st.sampled_from(VALID_CLASSIFICATION_LABELS)


# Strategy for generating non-empty reasoning strings
reasoning_strategy = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())


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
    start_index = draw(st.integers(min_value=0, max_value=10000))
    end_index = draw(st.integers(min_value=start_index + 1, max_value=start_index + 10001))
    
    return Claim(
        id=claim_id,
        text=text,
        start_index=start_index,
        end_index=end_index,
        type=claim_type,
        entities=entities,
    )


@st.composite
def search_result_strategy(draw):
    """
    Hypothesis composite strategy for generating valid SearchResult objects.
    """
    title = draw(st.text(min_size=1, max_size=100).filter(lambda s: s.strip()))
    source = draw(st.text(min_size=1, max_size=50).filter(lambda s: s.strip()))
    summary = draw(st.text(min_size=1, max_size=300).filter(lambda s: s.strip()))
    timestamp = draw(st.datetimes().map(lambda dt: dt.isoformat() + "Z"))
    relevance_score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    
    return SearchResult(
        title=title,
        source=source,
        summary=summary,
        timestamp=timestamp,
        relevance_score=relevance_score,
    )


@st.composite
def evidence_set_strategy(draw):
    """
    Hypothesis composite strategy for generating valid EvidenceSet objects.
    
    Generates evidence sets with 0-5 search results.
    """
    results = draw(st.lists(search_result_strategy(), min_size=0, max_size=5))
    insufficient_evidence = len(results) == 0
    
    return EvidenceSet(
        results=results,
        insufficient_evidence=insufficient_evidence,
    )


@st.composite
def evidence_set_with_results_strategy(draw):
    """
    Hypothesis composite strategy for generating EvidenceSet objects with at least one result.
    """
    results = draw(st.lists(search_result_strategy(), min_size=1, max_size=5))
    
    return EvidenceSet(
        results=results,
        insufficient_evidence=False,
    )


def empty_evidence_set_strategy():
    """
    Hypothesis strategy for generating empty EvidenceSet objects.
    """
    return st.just(EvidenceSet(
        results=[],
        insufficient_evidence=True,
    ))


# ============================================================================
# Property 7: Classification output validity
# ============================================================================


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
    mock_label=classification_label_strategy,
    mock_reasoning=reasoning_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_output_validity(
    claim: Claim,
    evidence: EvidenceSet,
    mock_label: str,
    mock_reasoning: str,
):
    """
    Property 7: Classification output validity.
    
    For any ClassificationResult produced by the Classifier:
    - The `label` must be exactly one of {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}
    - The `reasoning` must be a non-empty string
    
    This test mocks the LLM to return valid labels and generates random Claims
    and EvidenceSets to verify the classifier always produces valid output.
    
    **Validates: Requirements 5.1, 5.2**
    """
    # Create a mock LLM client that returns the generated label and reasoning
    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.complete_json = AsyncMock(return_value={
        "label": mock_label,
        "reasoning": mock_reasoning,
    })
    
    # Create the classifier with the mock client
    classifier = Classifier(llm_client=mock_llm_client)
    
    # Classify the claim
    result = await classifier.classify(claim, evidence)
    
    # Assert the result is a ClassificationResult
    assert isinstance(result, ClassificationResult), \
        f"Expected ClassificationResult, got {type(result)}"
    
    # Assert the label is in the valid set (Req 5.1)
    assert result.label in ClassificationLabel, \
        f"Label {result.label} is not a valid ClassificationLabel"
    
    assert result.label.value in VALID_CLASSIFICATION_LABELS, \
        f"Label value '{result.label.value}' is not in valid set {VALID_CLASSIFICATION_LABELS}"
    
    # Assert the reasoning is non-empty (Req 5.2)
    assert result.reasoning is not None, "Reasoning must not be None"
    assert isinstance(result.reasoning, str), "Reasoning must be a string"
    assert len(result.reasoning.strip()) > 0, "Reasoning must be non-empty"
    
    # Assert the claim_id matches the input claim's id
    assert result.claim_id == claim.id, \
        f"claim_id mismatch: expected '{claim.id}', got '{result.claim_id}'"


@given(
    claim=claim_strategy(),
    evidence=evidence_set_with_results_strategy(),
    mock_label=classification_label_strategy,
    mock_reasoning=reasoning_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_output_validity_with_evidence(
    claim: Claim,
    evidence: EvidenceSet,
    mock_label: str,
    mock_reasoning: str,
):
    """
    Property 7 (variant): Classification output validity with non-empty evidence.
    
    Tests classification output validity specifically when evidence is present.
    
    **Validates: Requirements 5.1, 5.2**
    """
    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.complete_json = AsyncMock(return_value={
        "label": mock_label,
        "reasoning": mock_reasoning,
    })
    
    classifier = Classifier(llm_client=mock_llm_client)
    result = await classifier.classify(claim, evidence)
    
    # Verify label validity (Req 5.1)
    assert result.label.value in VALID_CLASSIFICATION_LABELS
    
    # Verify reasoning is non-empty (Req 5.2)
    assert len(result.reasoning.strip()) > 0
    
    # Verify claim_id matches
    assert result.claim_id == claim.id


@given(
    claim=claim_strategy(),
    evidence=empty_evidence_set_strategy(),
    mock_label=classification_label_strategy,
    mock_reasoning=reasoning_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_output_validity_with_empty_evidence(
    claim: Claim,
    evidence: EvidenceSet,
    mock_label: str,
    mock_reasoning: str,
):
    """
    Property 7 (variant): Classification output validity with empty evidence.
    
    Tests classification output validity specifically when no evidence is available.
    The classifier should still produce valid output even with insufficient evidence.
    
    **Validates: Requirements 5.1, 5.2**
    """
    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.complete_json = AsyncMock(return_value={
        "label": mock_label,
        "reasoning": mock_reasoning,
    })
    
    classifier = Classifier(llm_client=mock_llm_client)
    result = await classifier.classify(claim, evidence)
    
    # Verify label validity (Req 5.1)
    assert result.label.value in VALID_CLASSIFICATION_LABELS
    
    # Verify reasoning is non-empty (Req 5.2)
    assert len(result.reasoning.strip()) > 0
    
    # Verify claim_id matches
    assert result.claim_id == claim.id


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_label_is_exactly_one_from_valid_set(
    claim: Claim,
    evidence: EvidenceSet,
):
    """
    Property 7 (variant): Classification assigns exactly one label from the valid set.
    
    Tests that for each classification, exactly one label is assigned (not multiple,
    not none) and it is from the valid set {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}.
    
    **Validates: Requirements 5.1**
    """
    # Test with each valid label to ensure all are accepted
    for expected_label in VALID_CLASSIFICATION_LABELS:
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": expected_label,
            "reasoning": "Test reasoning for classification.",
        })
        
        classifier = Classifier(llm_client=mock_llm_client)
        result = await classifier.classify(claim, evidence)
        
        # Verify exactly one label is assigned
        assert result.label is not None, "Label must not be None"
        
        # Verify the label matches what was returned by the LLM
        assert result.label.value == expected_label, \
            f"Expected label '{expected_label}', got '{result.label.value}'"
        
        # Verify it's in the valid set
        assert result.label.value in VALID_CLASSIFICATION_LABELS


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
    mock_label=classification_label_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_handles_empty_reasoning_from_llm(
    claim: Claim,
    evidence: EvidenceSet,
    mock_label: str,
):
    """
    Property 7 (variant): Classification handles empty reasoning gracefully.
    
    When the LLM returns empty reasoning, the classifier should provide
    a default non-empty reasoning string.
    
    **Validates: Requirements 5.2**
    """
    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.complete_json = AsyncMock(return_value={
        "label": mock_label,
        "reasoning": "",  # Empty reasoning
    })
    
    classifier = Classifier(llm_client=mock_llm_client)
    result = await classifier.classify(claim, evidence)
    
    # Verify label is still valid (Req 5.1)
    assert result.label.value in VALID_CLASSIFICATION_LABELS
    
    # Verify reasoning is non-empty even when LLM returns empty (Req 5.2)
    # The classifier should provide a default reasoning
    assert result.reasoning is not None
    assert len(result.reasoning.strip()) > 0, \
        "Reasoning must be non-empty even when LLM returns empty reasoning"


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
    mock_label=classification_label_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_handles_whitespace_only_reasoning(
    claim: Claim,
    evidence: EvidenceSet,
    mock_label: str,
):
    """
    Property 7 (variant): Classification handles whitespace-only reasoning.
    
    When the LLM returns whitespace-only reasoning, the classifier should
    provide a default non-empty reasoning string.
    
    **Validates: Requirements 5.2**
    """
    mock_llm_client = MagicMock(spec=LLMClient)
    mock_llm_client.complete_json = AsyncMock(return_value={
        "label": mock_label,
        "reasoning": "   \t\n   ",  # Whitespace-only reasoning
    })
    
    classifier = Classifier(llm_client=mock_llm_client)
    result = await classifier.classify(claim, evidence)
    
    # Verify label is still valid (Req 5.1)
    assert result.label.value in VALID_CLASSIFICATION_LABELS
    
    # Verify reasoning is non-empty (Req 5.2)
    assert result.reasoning is not None
    assert len(result.reasoning.strip()) > 0, \
        "Reasoning must be non-empty even when LLM returns whitespace-only reasoning"


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
    mock_reasoning=reasoning_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_label_case_insensitivity(
    claim: Claim,
    evidence: EvidenceSet,
    mock_reasoning: str,
):
    """
    Property 7 (variant): Classification handles case variations in labels.
    
    The classifier should accept labels in any case (lowercase, uppercase, mixed)
    and normalize them to the correct ClassificationLabel enum value.
    
    **Validates: Requirements 5.1**
    """
    # Test various case variations
    case_variations = [
        ("verified", ClassificationLabel.VERIFIED),
        ("VERIFIED", ClassificationLabel.VERIFIED),
        ("Verified", ClassificationLabel.VERIFIED),
        ("misleading", ClassificationLabel.MISLEADING),
        ("MISLEADING", ClassificationLabel.MISLEADING),
        ("Misleading", ClassificationLabel.MISLEADING),
        ("likely_false", ClassificationLabel.LIKELY_FALSE),
        ("LIKELY_FALSE", ClassificationLabel.LIKELY_FALSE),
        ("Likely_False", ClassificationLabel.LIKELY_FALSE),
        ("harmful", ClassificationLabel.HARMFUL),
        ("HARMFUL", ClassificationLabel.HARMFUL),
        ("Harmful", ClassificationLabel.HARMFUL),
    ]
    
    for label_input, expected_label in case_variations:
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": label_input,
            "reasoning": mock_reasoning,
        })
        
        classifier = Classifier(llm_client=mock_llm_client)
        result = await classifier.classify(claim, evidence)
        
        # Verify the label is normalized correctly
        assert result.label == expected_label, \
            f"Label '{label_input}' should normalize to {expected_label}, got {result.label}"


@given(
    claim=claim_strategy(),
    evidence=evidence_set_strategy(),
    mock_reasoning=reasoning_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_classification_label_whitespace_handling(
    claim: Claim,
    evidence: EvidenceSet,
    mock_reasoning: str,
):
    """
    Property 7 (variant): Classification handles whitespace in labels.
    
    The classifier should trim whitespace from labels before validation.
    
    **Validates: Requirements 5.1**
    """
    # Test labels with leading/trailing whitespace
    whitespace_variations = [
        ("  VERIFIED  ", ClassificationLabel.VERIFIED),
        ("\tMISLEADING\t", ClassificationLabel.MISLEADING),
        ("\n LIKELY_FALSE \n", ClassificationLabel.LIKELY_FALSE),
        ("  HARMFUL", ClassificationLabel.HARMFUL),
    ]
    
    for label_input, expected_label in whitespace_variations:
        mock_llm_client = MagicMock(spec=LLMClient)
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": label_input,
            "reasoning": mock_reasoning,
        })
        
        classifier = Classifier(llm_client=mock_llm_client)
        result = await classifier.classify(claim, evidence)
        
        # Verify the label is trimmed and normalized correctly
        assert result.label == expected_label, \
            f"Label '{label_input}' should normalize to {expected_label}, got {result.label}"
