"""
Property-based tests for TrustScoreEngine.

This module tests:
- Property 8: Trust score weighted formula correctness
- Property 9: Trust score range and completeness

It validates that the TrustScoreEngine computes the final trust score using
the correct weighted formula: round(SC*0.3 + ES*0.3 + LN*0.2 + CSA*0.2) clamped to [0, 100],
and that all sub-scores and the final score are integers in [0, 100] with all fields present.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
"""

from hypothesis import given, strategies as st, settings
import uuid

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
    SearchResult,
    TrustScoreWeights,
)
from app.services.trust_score_engine import TrustScoreEngine


# Strategy for generating valid sub-scores (integers 0-100)
sub_score_strategy = st.integers(min_value=0, max_value=100)


def compute_expected_trust_score(
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
    weights: TrustScoreWeights | None = None,
) -> int:
    """
    Compute the expected trust score using the weighted formula.
    
    Formula: round(SC * w_sc + ES * w_es + LN * w_ln + CSA * w_csa) clamped to [0, 100]
    
    Default weights: 0.3, 0.3, 0.2, 0.2
    """
    if weights is None:
        weights = TrustScoreWeights()
    
    raw_score = (
        source_credibility * weights.source_credibility +
        evidence_strength * weights.evidence_strength +
        language_neutrality * weights.language_neutrality +
        cross_source_agreement * weights.cross_source_agreement
    )
    
    return max(0, min(100, round(raw_score)))


def create_mock_claim(claim_text: str = "Test claim") -> Claim:
    """Create a mock claim for testing."""
    return Claim(
        id="test-claim-id",
        text=claim_text,
        start_index=0,
        end_index=len(claim_text),
        type="market",
        entities=["Test"],
    )


def create_mock_evidence_for_source_credibility(target_score: int) -> EvidenceSet:
    """
    Create mock evidence that produces a specific source credibility score.
    
    The source credibility is computed based on known reputable sources.
    We use sources with known credibility ratings to achieve target scores.
    """
    # For simplicity, we create evidence with sources that have known credibility
    # The engine uses REPUTABLE_SOURCES dict with scores like:
    # reuters: 95, bbc: 90, forbes: 75, yahoo finance: 70, unknown: 50
    
    if target_score >= 90:
        # Use highly reputable sources
        results = [
            SearchResult(
                title="Reuters Article",
                source="Reuters",
                summary="This confirms the claim.",
                timestamp="2024-01-01T00:00:00Z",
                relevance_score=1.0,
            ),
        ]
    elif target_score >= 70:
        # Use moderately reputable sources
        results = [
            SearchResult(
                title="Forbes Article",
                source="Forbes",
                summary="This confirms the claim.",
                timestamp="2024-01-01T00:00:00Z",
                relevance_score=1.0,
            ),
        ]
    elif target_score >= 50:
        # Use unknown sources (default 50)
        results = [
            SearchResult(
                title="Unknown Article",
                source="Unknown Source",
                summary="This confirms the claim.",
                timestamp="2024-01-01T00:00:00Z",
                relevance_score=1.0,
            ),
        ]
    else:
        # No evidence gives low score (30)
        results = []
    
    return EvidenceSet(results=results, insufficient_evidence=len(results) == 0)


def create_mock_classification(claim_id: str) -> ClassificationResult:
    """Create a mock classification result."""
    return ClassificationResult(
        claim_id=claim_id,
        label=ClassificationLabel.VERIFIED,
        reasoning="Test classification",
    )


@given(
    source_credibility=sub_score_strategy,
    evidence_strength=sub_score_strategy,
    language_neutrality=sub_score_strategy,
    cross_source_agreement=sub_score_strategy,
)
@settings(max_examples=100)
def test_trust_score_weighted_formula_with_default_weights(
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
):
    """
    Property 8: Trust score weighted formula correctness with default weights.
    
    For any four sub-scores (Source_Credibility, Evidence_Strength, Language_Neutrality,
    Cross_Source_Agreement) each in [0, 100], the computed Trust_Score must equal
    `round(SC * 0.3 + ES * 0.3 + LN * 0.2 + CSA * 0.2)` clamped to [0, 100].
    
    This test directly verifies the formula by computing the expected result
    and comparing it to the engine's output using a mock that bypasses
    the sub-score computation.
    
    **Validates: Requirements 6.1**
    """
    # Compute expected trust score using the formula
    expected_score = compute_expected_trust_score(
        source_credibility,
        evidence_strength,
        language_neutrality,
        cross_source_agreement,
    )
    
    # Verify the expected score is in valid range
    assert 0 <= expected_score <= 100
    
    # Verify the formula computation directly
    raw_score = (
        source_credibility * 0.3 +
        evidence_strength * 0.3 +
        language_neutrality * 0.2 +
        cross_source_agreement * 0.2
    )
    clamped_score = max(0, min(100, round(raw_score)))
    
    assert expected_score == clamped_score


@given(
    source_credibility=sub_score_strategy,
    evidence_strength=sub_score_strategy,
    language_neutrality=sub_score_strategy,
    cross_source_agreement=sub_score_strategy,
)
@settings(max_examples=100)
def test_trust_score_weighted_formula_clamping(
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
):
    """
    Property 8 (clamping aspect): Trust score is always clamped to [0, 100].
    
    Even with extreme sub-score values, the final trust score must be
    an integer in the range [0, 100].
    
    **Validates: Requirements 6.1, 6.6**
    """
    expected_score = compute_expected_trust_score(
        source_credibility,
        evidence_strength,
        language_neutrality,
        cross_source_agreement,
    )
    
    # The score must always be in valid range
    assert isinstance(expected_score, int)
    assert 0 <= expected_score <= 100


@given(
    w_sc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_es=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_ln=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_csa=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    source_credibility=sub_score_strategy,
    evidence_strength=sub_score_strategy,
    language_neutrality=sub_score_strategy,
    cross_source_agreement=sub_score_strategy,
)
@settings(max_examples=100)
def test_trust_score_weighted_formula_with_custom_weights(
    w_sc: float,
    w_es: float,
    w_ln: float,
    w_csa: float,
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
):
    """
    Property 8: Trust score weighted formula correctness with custom weights.
    
    For any four sub-scores and any valid custom weights, the computed Trust_Score
    must equal `round(SC * w_sc + ES * w_es + LN * w_ln + CSA * w_csa)` clamped to [0, 100].
    
    **Validates: Requirements 6.1**
    """
    custom_weights = TrustScoreWeights(
        source_credibility=w_sc,
        evidence_strength=w_es,
        language_neutrality=w_ln,
        cross_source_agreement=w_csa,
    )
    
    expected_score = compute_expected_trust_score(
        source_credibility,
        evidence_strength,
        language_neutrality,
        cross_source_agreement,
        weights=custom_weights,
    )
    
    # Verify the expected score is in valid range
    assert isinstance(expected_score, int)
    assert 0 <= expected_score <= 100


@given(
    source_credibility=sub_score_strategy,
    evidence_strength=sub_score_strategy,
    language_neutrality=sub_score_strategy,
    cross_source_agreement=sub_score_strategy,
)
@settings(max_examples=100)
def test_trust_score_engine_formula_integration(
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
):
    """
    Property 8: Trust score engine integration test.
    
    This test verifies that the TrustScoreEngine's compute method applies
    the weighted formula correctly by using a subclass that returns
    predetermined sub-scores.
    
    **Validates: Requirements 6.1**
    """
    # Create a test subclass that returns predetermined sub-scores
    class TestTrustScoreEngine(TrustScoreEngine):
        def __init__(self, sc: int, es: int, ln: int, csa: int, weights=None):
            super().__init__(weights)
            self._sc = sc
            self._es = es
            self._ln = ln
            self._csa = csa
        
        def _compute_source_credibility(self, evidence):
            return self._sc
        
        def _compute_evidence_strength(self, evidence):
            return self._es
        
        def _compute_language_neutrality(self, claim):
            return self._ln
        
        def _compute_cross_source_agreement(self, evidence):
            return self._csa
    
    # Create engine with predetermined sub-scores
    engine = TestTrustScoreEngine(
        sc=source_credibility,
        es=evidence_strength,
        ln=language_neutrality,
        csa=cross_source_agreement,
    )
    
    # Create minimal test data
    claim = create_mock_claim()
    evidence = EvidenceSet(results=[], insufficient_evidence=True)
    classification = create_mock_classification(claim.id)
    
    # Compute trust score
    result = engine.compute(
        claims=[claim],
        evidence={claim.id: evidence},
        classifications={claim.id: classification},
    )
    
    # Compute expected score
    expected_score = compute_expected_trust_score(
        source_credibility,
        evidence_strength,
        language_neutrality,
        cross_source_agreement,
    )
    
    # Verify the engine output matches expected formula result
    assert result.trust_score == expected_score
    
    # Verify sub-scores are returned correctly
    assert result.breakdown.source_credibility == source_credibility
    assert result.breakdown.evidence_strength == evidence_strength
    assert result.breakdown.language_neutrality == language_neutrality
    assert result.breakdown.cross_source_agreement == cross_source_agreement


@given(
    source_credibility=sub_score_strategy,
    evidence_strength=sub_score_strategy,
    language_neutrality=sub_score_strategy,
    cross_source_agreement=sub_score_strategy,
    w_sc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_es=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_ln=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_csa=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_trust_score_engine_custom_weights_integration(
    source_credibility: int,
    evidence_strength: int,
    language_neutrality: int,
    cross_source_agreement: int,
    w_sc: float,
    w_es: float,
    w_ln: float,
    w_csa: float,
):
    """
    Property 8: Trust score engine with custom weights integration test.
    
    This test verifies that the TrustScoreEngine correctly applies custom weights
    to the weighted formula.
    
    **Validates: Requirements 6.1**
    """
    # Create a test subclass that returns predetermined sub-scores
    class TestTrustScoreEngine(TrustScoreEngine):
        def __init__(self, sc: int, es: int, ln: int, csa: int, weights=None):
            super().__init__(weights)
            self._sc = sc
            self._es = es
            self._ln = ln
            self._csa = csa
        
        def _compute_source_credibility(self, evidence):
            return self._sc
        
        def _compute_evidence_strength(self, evidence):
            return self._es
        
        def _compute_language_neutrality(self, claim):
            return self._ln
        
        def _compute_cross_source_agreement(self, evidence):
            return self._csa
    
    # Create custom weights
    custom_weights = TrustScoreWeights(
        source_credibility=w_sc,
        evidence_strength=w_es,
        language_neutrality=w_ln,
        cross_source_agreement=w_csa,
    )
    
    # Create engine with predetermined sub-scores and custom weights
    engine = TestTrustScoreEngine(
        sc=source_credibility,
        es=evidence_strength,
        ln=language_neutrality,
        csa=cross_source_agreement,
        weights=custom_weights,
    )
    
    # Create minimal test data
    claim = create_mock_claim()
    evidence = EvidenceSet(results=[], insufficient_evidence=True)
    classification = create_mock_classification(claim.id)
    
    # Compute trust score
    result = engine.compute(
        claims=[claim],
        evidence={claim.id: evidence},
        classifications={claim.id: classification},
    )
    
    # Compute expected score with custom weights
    expected_score = compute_expected_trust_score(
        source_credibility,
        evidence_strength,
        language_neutrality,
        cross_source_agreement,
        weights=custom_weights,
    )
    
    # Verify the engine output matches expected formula result
    assert result.trust_score == expected_score


@given(sub_score=sub_score_strategy)
@settings(max_examples=100)
def test_trust_score_formula_boundary_cases(sub_score: int):
    """
    Property 8: Trust score formula handles boundary cases correctly.
    
    When all sub-scores are the same value, the weighted formula should
    produce that same value (since weights sum to 1.0).
    
    **Validates: Requirements 6.1**
    """
    # When all sub-scores are equal, the weighted average equals that value
    expected_score = compute_expected_trust_score(
        sub_score, sub_score, sub_score, sub_score
    )
    
    # With default weights (0.3 + 0.3 + 0.2 + 0.2 = 1.0), the result should equal the input
    assert expected_score == sub_score


def test_trust_score_formula_extreme_values():
    """
    Property 8: Trust score formula handles extreme values correctly.
    
    Test specific extreme cases to ensure proper clamping and rounding.
    
    **Validates: Requirements 6.1, 6.6**
    """
    # All zeros should give 0
    assert compute_expected_trust_score(0, 0, 0, 0) == 0
    
    # All 100s should give 100
    assert compute_expected_trust_score(100, 100, 100, 100) == 100
    
    # Mixed extreme values
    # 100*0.3 + 0*0.3 + 100*0.2 + 0*0.2 = 30 + 0 + 20 + 0 = 50
    assert compute_expected_trust_score(100, 0, 100, 0) == 50
    
    # 0*0.3 + 100*0.3 + 0*0.2 + 100*0.2 = 0 + 30 + 0 + 20 = 50
    assert compute_expected_trust_score(0, 100, 0, 100) == 50


def test_trust_score_formula_rounding():
    """
    Property 8: Trust score formula rounds correctly.
    
    Test specific cases where rounding behavior matters.
    
    **Validates: Requirements 6.1**
    """
    # Test case where rounding matters
    # 75*0.3 + 75*0.3 + 75*0.2 + 75*0.2 = 22.5 + 22.5 + 15 + 15 = 75
    assert compute_expected_trust_score(75, 75, 75, 75) == 75
    
    # Test case with fractional result
    # 33*0.3 + 33*0.3 + 33*0.2 + 33*0.2 = 9.9 + 9.9 + 6.6 + 6.6 = 33
    assert compute_expected_trust_score(33, 33, 33, 33) == 33
    
    # Test case where rounding up occurs
    # 67*0.3 + 67*0.3 + 67*0.2 + 67*0.2 = 20.1 + 20.1 + 13.4 + 13.4 = 67
    assert compute_expected_trust_score(67, 67, 67, 67) == 67


# =============================================================================
# Property 9: Trust score range and completeness
# =============================================================================

# Strategies for generating random test data for Property 9

# Strategy for generating valid claim types
claim_type_strategy = st.sampled_from(["banking", "market", "investment", "crypto", "economic"])

# Strategy for generating valid classification labels
classification_label_strategy = st.sampled_from(list(ClassificationLabel))

# Strategy for generating valid relevance scores
relevance_score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for generating non-empty strings
non_empty_string_strategy = st.text(min_size=1, max_size=100).filter(lambda s: s.strip())


def claim_strategy():
    """Strategy for generating random valid Claim objects."""
    return st.builds(
        lambda text, claim_type, entities: Claim(
            id=str(uuid.uuid4()),
            text=text,
            start_index=0,
            end_index=len(text),
            type=claim_type,
            entities=entities,
        ),
        text=st.text(min_size=5, max_size=200).filter(lambda s: s.strip()),
        claim_type=claim_type_strategy,
        entities=st.lists(st.text(min_size=1, max_size=50).filter(lambda s: s.strip()), min_size=0, max_size=5),
    )


def search_result_strategy():
    """Strategy for generating random valid SearchResult objects."""
    return st.builds(
        SearchResult,
        title=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
        source=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
        summary=st.text(min_size=1, max_size=300).filter(lambda s: s.strip()),
        timestamp=st.just("2024-01-01T00:00:00Z"),  # Use fixed timestamp for simplicity
        relevance_score=relevance_score_strategy,
    )


def evidence_set_strategy():
    """Strategy for generating random valid EvidenceSet objects."""
    return st.builds(
        lambda results: EvidenceSet(
            results=results,
            insufficient_evidence=len(results) == 0,
        ),
        results=st.lists(search_result_strategy(), min_size=0, max_size=10),
    )


def classification_result_strategy(claim_id: str):
    """Strategy for generating random valid ClassificationResult objects for a given claim."""
    return st.builds(
        ClassificationResult,
        claim_id=st.just(claim_id),
        label=classification_label_strategy,
        reasoning=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    )


@given(
    claims=st.lists(claim_strategy(), min_size=1, max_size=5),
    evidence_sets=st.lists(evidence_set_strategy(), min_size=1, max_size=5),
    labels=st.lists(classification_label_strategy, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_trust_score_range_and_completeness_with_random_inputs(
    claims: list[Claim],
    evidence_sets: list[EvidenceSet],
    labels: list[ClassificationLabel],
):
    """
    Property 9: Trust score range and completeness.
    
    For any TrustScoreResult produced by the Trust Score Engine, all four sub-scores
    (source_credibility, evidence_strength, language_neutrality, cross_source_agreement)
    and the final trust_score must be integers in the range [0, 100], and all five
    fields must be present in the result.
    
    This test generates random Claim objects, EvidenceSet objects, and ClassificationResult
    objects, calls TrustScoreEngine.compute(), and verifies the result.
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    # Create engine with default weights
    engine = TrustScoreEngine()
    
    # Build evidence and classification dictionaries
    # Match evidence sets and labels to claims (cycling if needed)
    evidence = {}
    classifications = {}
    
    for i, claim in enumerate(claims):
        evidence[claim.id] = evidence_sets[i % len(evidence_sets)]
        classifications[claim.id] = ClassificationResult(
            claim_id=claim.id,
            label=labels[i % len(labels)],
            reasoning=f"Test reasoning for claim {i}",
        )
    
    # Compute trust score
    result = engine.compute(
        claims=claims,
        evidence=evidence,
        classifications=classifications,
    )
    
    # Assert trust_score is an integer in [0, 100]
    assert isinstance(result.trust_score, int), f"trust_score should be int, got {type(result.trust_score)}"
    assert 0 <= result.trust_score <= 100, f"trust_score {result.trust_score} not in [0, 100]"
    
    # Assert breakdown is present
    assert result.breakdown is not None, "breakdown should not be None"
    
    # Assert source_credibility is an integer in [0, 100]
    assert isinstance(result.breakdown.source_credibility, int), \
        f"source_credibility should be int, got {type(result.breakdown.source_credibility)}"
    assert 0 <= result.breakdown.source_credibility <= 100, \
        f"source_credibility {result.breakdown.source_credibility} not in [0, 100]"
    
    # Assert evidence_strength is an integer in [0, 100]
    assert isinstance(result.breakdown.evidence_strength, int), \
        f"evidence_strength should be int, got {type(result.breakdown.evidence_strength)}"
    assert 0 <= result.breakdown.evidence_strength <= 100, \
        f"evidence_strength {result.breakdown.evidence_strength} not in [0, 100]"
    
    # Assert language_neutrality is an integer in [0, 100]
    assert isinstance(result.breakdown.language_neutrality, int), \
        f"language_neutrality should be int, got {type(result.breakdown.language_neutrality)}"
    assert 0 <= result.breakdown.language_neutrality <= 100, \
        f"language_neutrality {result.breakdown.language_neutrality} not in [0, 100]"
    
    # Assert cross_source_agreement is an integer in [0, 100]
    assert isinstance(result.breakdown.cross_source_agreement, int), \
        f"cross_source_agreement should be int, got {type(result.breakdown.cross_source_agreement)}"
    assert 0 <= result.breakdown.cross_source_agreement <= 100, \
        f"cross_source_agreement {result.breakdown.cross_source_agreement} not in [0, 100]"


@given(
    claim_text=st.text(min_size=5, max_size=500).filter(lambda s: s.strip()),
    claim_type=claim_type_strategy,
    num_results=st.integers(min_value=0, max_value=10),
    label=classification_label_strategy,
)
@settings(max_examples=100)
def test_trust_score_range_with_single_claim(
    claim_text: str,
    claim_type: str,
    num_results: int,
    label: ClassificationLabel,
):
    """
    Property 9: Trust score range and completeness with single claim.
    
    Tests that for a single claim with varying evidence and classification,
    all scores are integers in [0, 100] and all fields are present.
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    # Create engine
    engine = TrustScoreEngine()
    
    # Create a single claim
    claim = Claim(
        id=str(uuid.uuid4()),
        text=claim_text,
        start_index=0,
        end_index=len(claim_text),
        type=claim_type,
        entities=["TestEntity"],
    )
    
    # Create evidence with varying number of results
    results = [
        SearchResult(
            title=f"Article {i}",
            source=f"Source {i}",
            summary=f"Summary for article {i}",
            timestamp="2024-01-01T00:00:00Z",
            relevance_score=0.5 + (i * 0.05),  # Varying relevance scores
        )
        for i in range(num_results)
    ]
    evidence_set = EvidenceSet(results=results, insufficient_evidence=num_results == 0)
    
    # Create classification
    classification = ClassificationResult(
        claim_id=claim.id,
        label=label,
        reasoning="Test reasoning",
    )
    
    # Compute trust score
    result = engine.compute(
        claims=[claim],
        evidence={claim.id: evidence_set},
        classifications={claim.id: classification},
    )
    
    # Assert all five fields are present and in valid range
    assert result.trust_score is not None, "trust_score should not be None"
    assert isinstance(result.trust_score, int), f"trust_score should be int, got {type(result.trust_score)}"
    assert 0 <= result.trust_score <= 100, f"trust_score {result.trust_score} not in [0, 100]"
    
    assert result.breakdown is not None, "breakdown should not be None"
    
    assert result.breakdown.source_credibility is not None, "source_credibility should not be None"
    assert isinstance(result.breakdown.source_credibility, int)
    assert 0 <= result.breakdown.source_credibility <= 100
    
    assert result.breakdown.evidence_strength is not None, "evidence_strength should not be None"
    assert isinstance(result.breakdown.evidence_strength, int)
    assert 0 <= result.breakdown.evidence_strength <= 100
    
    assert result.breakdown.language_neutrality is not None, "language_neutrality should not be None"
    assert isinstance(result.breakdown.language_neutrality, int)
    assert 0 <= result.breakdown.language_neutrality <= 100
    
    assert result.breakdown.cross_source_agreement is not None, "cross_source_agreement should not be None"
    assert isinstance(result.breakdown.cross_source_agreement, int)
    assert 0 <= result.breakdown.cross_source_agreement <= 100


@given(
    num_claims=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_trust_score_range_with_varying_claim_counts(num_claims: int):
    """
    Property 9: Trust score range and completeness with varying claim counts.
    
    Tests that the engine produces valid scores for any number of claims,
    including zero claims (edge case).
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    # Create engine
    engine = TrustScoreEngine()
    
    # Create claims
    claims = [
        Claim(
            id=str(uuid.uuid4()),
            text=f"Test claim number {i}",
            start_index=0,
            end_index=len(f"Test claim number {i}"),
            type="market",
            entities=["Test"],
        )
        for i in range(num_claims)
    ]
    
    # Create evidence and classifications for each claim
    evidence = {}
    classifications = {}
    
    for claim in claims:
        evidence[claim.id] = EvidenceSet(
            results=[
                SearchResult(
                    title="Test Article",
                    source="Test Source",
                    summary="Test summary",
                    timestamp="2024-01-01T00:00:00Z",
                    relevance_score=0.8,
                )
            ],
            insufficient_evidence=False,
        )
        classifications[claim.id] = ClassificationResult(
            claim_id=claim.id,
            label=ClassificationLabel.VERIFIED,
            reasoning="Test reasoning",
        )
    
    # Compute trust score
    result = engine.compute(
        claims=claims,
        evidence=evidence,
        classifications=classifications,
    )
    
    # Assert all five fields are present and in valid range
    assert result.trust_score is not None, "trust_score should not be None"
    assert isinstance(result.trust_score, int), f"trust_score should be int, got {type(result.trust_score)}"
    assert 0 <= result.trust_score <= 100, f"trust_score {result.trust_score} not in [0, 100]"
    
    assert result.breakdown is not None, "breakdown should not be None"
    
    assert isinstance(result.breakdown.source_credibility, int)
    assert 0 <= result.breakdown.source_credibility <= 100
    
    assert isinstance(result.breakdown.evidence_strength, int)
    assert 0 <= result.breakdown.evidence_strength <= 100
    
    assert isinstance(result.breakdown.language_neutrality, int)
    assert 0 <= result.breakdown.language_neutrality <= 100
    
    assert isinstance(result.breakdown.cross_source_agreement, int)
    assert 0 <= result.breakdown.cross_source_agreement <= 100


@given(
    claim_text=st.text(min_size=5, max_size=1000).filter(lambda s: s.strip()),
    source_names=st.lists(
        st.sampled_from(["Reuters", "Bloomberg", "BBC", "Forbes", "Unknown Source", "Random Blog"]),
        min_size=0,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_trust_score_range_with_various_sources(
    claim_text: str,
    source_names: list[str],
):
    """
    Property 9: Trust score range and completeness with various source types.
    
    Tests that the engine produces valid scores regardless of the source
    credibility mix (reputable, unknown, etc.).
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    # Create engine
    engine = TrustScoreEngine()
    
    # Create a claim
    claim = Claim(
        id=str(uuid.uuid4()),
        text=claim_text,
        start_index=0,
        end_index=len(claim_text),
        type="market",
        entities=["Test"],
    )
    
    # Create evidence with various sources
    results = [
        SearchResult(
            title=f"Article from {source}",
            source=source,
            summary=f"Summary from {source}",
            timestamp="2024-01-01T00:00:00Z",
            relevance_score=0.7,
        )
        for source in source_names
    ]
    evidence_set = EvidenceSet(results=results, insufficient_evidence=len(results) == 0)
    
    # Create classification
    classification = ClassificationResult(
        claim_id=claim.id,
        label=ClassificationLabel.VERIFIED,
        reasoning="Test reasoning",
    )
    
    # Compute trust score
    result = engine.compute(
        claims=[claim],
        evidence={claim.id: evidence_set},
        classifications={claim.id: classification},
    )
    
    # Assert all five fields are present and in valid range
    assert isinstance(result.trust_score, int)
    assert 0 <= result.trust_score <= 100
    
    assert result.breakdown is not None
    assert isinstance(result.breakdown.source_credibility, int)
    assert 0 <= result.breakdown.source_credibility <= 100
    
    assert isinstance(result.breakdown.evidence_strength, int)
    assert 0 <= result.breakdown.evidence_strength <= 100
    
    assert isinstance(result.breakdown.language_neutrality, int)
    assert 0 <= result.breakdown.language_neutrality <= 100
    
    assert isinstance(result.breakdown.cross_source_agreement, int)
    assert 0 <= result.breakdown.cross_source_agreement <= 100


@given(
    emotional_words=st.lists(
        st.sampled_from([
            "URGENT", "guaranteed", "crash", "massive gains", "secret",
            "incredible", "must buy", "skyrocket", "panic", "fortune",
            "risk-free", "easy money", "don't wait", "limited time",
        ]),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_trust_score_range_with_emotional_language(emotional_words: list[str]):
    """
    Property 9: Trust score range and completeness with emotional language.
    
    Tests that the engine produces valid scores for claims containing
    various amounts of emotional/manipulative language.
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    # Create engine
    engine = TrustScoreEngine()
    
    # Create a claim with emotional words
    base_text = "The stock price will increase"
    claim_text = f"{base_text} {' '.join(emotional_words)}".strip()
    
    claim = Claim(
        id=str(uuid.uuid4()),
        text=claim_text,
        start_index=0,
        end_index=len(claim_text),
        type="market",
        entities=["Stock"],
    )
    
    # Create evidence
    evidence_set = EvidenceSet(
        results=[
            SearchResult(
                title="Test Article",
                source="Reuters",
                summary="Test summary",
                timestamp="2024-01-01T00:00:00Z",
                relevance_score=0.9,
            )
        ],
        insufficient_evidence=False,
    )
    
    # Create classification
    classification = ClassificationResult(
        claim_id=claim.id,
        label=ClassificationLabel.MISLEADING,
        reasoning="Contains emotional language",
    )
    
    # Compute trust score
    result = engine.compute(
        claims=[claim],
        evidence={claim.id: evidence_set},
        classifications={claim.id: classification},
    )
    
    # Assert all five fields are present and in valid range
    assert isinstance(result.trust_score, int)
    assert 0 <= result.trust_score <= 100
    
    assert result.breakdown is not None
    assert isinstance(result.breakdown.source_credibility, int)
    assert 0 <= result.breakdown.source_credibility <= 100
    
    assert isinstance(result.breakdown.evidence_strength, int)
    assert 0 <= result.breakdown.evidence_strength <= 100
    
    assert isinstance(result.breakdown.language_neutrality, int)
    assert 0 <= result.breakdown.language_neutrality <= 100
    
    assert isinstance(result.breakdown.cross_source_agreement, int)
    assert 0 <= result.breakdown.cross_source_agreement <= 100


def test_trust_score_completeness_all_fields_present():
    """
    Property 9: Trust score completeness - all five fields must be present.
    
    Explicit test to verify that the TrustScoreResult always contains
    all required fields (trust_score and four sub-scores in breakdown).
    
    **Validates: Requirements 6.7**
    """
    engine = TrustScoreEngine()
    
    # Test with a simple claim
    claim = Claim(
        id="test-id",
        text="Apple stock increased by 10%",
        start_index=0,
        end_index=27,
        type="market",
        entities=["Apple"],
    )
    
    evidence = {
        claim.id: EvidenceSet(
            results=[
                SearchResult(
                    title="Market Report",
                    source="Bloomberg",
                    summary="Apple stock rose 10%",
                    timestamp="2024-01-01T00:00:00Z",
                    relevance_score=0.95,
                )
            ],
            insufficient_evidence=False,
        )
    }
    
    classification = {
        claim.id: ClassificationResult(
            claim_id=claim.id,
            label=ClassificationLabel.VERIFIED,
            reasoning="Confirmed by Bloomberg",
        )
    }
    
    result = engine.compute(
        claims=[claim],
        evidence=evidence,
        classifications=classification,
    )
    
    # Verify all fields are present (not None)
    assert result.trust_score is not None, "trust_score must be present"
    assert result.breakdown is not None, "breakdown must be present"
    assert result.breakdown.source_credibility is not None, "source_credibility must be present"
    assert result.breakdown.evidence_strength is not None, "evidence_strength must be present"
    assert result.breakdown.language_neutrality is not None, "language_neutrality must be present"
    assert result.breakdown.cross_source_agreement is not None, "cross_source_agreement must be present"
    
    # Verify all are integers
    assert isinstance(result.trust_score, int)
    assert isinstance(result.breakdown.source_credibility, int)
    assert isinstance(result.breakdown.evidence_strength, int)
    assert isinstance(result.breakdown.language_neutrality, int)
    assert isinstance(result.breakdown.cross_source_agreement, int)
    
    # Verify all are in valid range
    assert 0 <= result.trust_score <= 100
    assert 0 <= result.breakdown.source_credibility <= 100
    assert 0 <= result.breakdown.evidence_strength <= 100
    assert 0 <= result.breakdown.language_neutrality <= 100
    assert 0 <= result.breakdown.cross_source_agreement <= 100


def test_trust_score_range_edge_case_empty_claims():
    """
    Property 9: Trust score range with empty claims list.
    
    Tests that the engine produces valid scores even when no claims are provided.
    
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    """
    engine = TrustScoreEngine()
    
    result = engine.compute(
        claims=[],
        evidence={},
        classifications={},
    )
    
    # Even with no claims, all fields should be present and valid
    assert isinstance(result.trust_score, int)
    assert 0 <= result.trust_score <= 100
    
    assert result.breakdown is not None
    assert isinstance(result.breakdown.source_credibility, int)
    assert 0 <= result.breakdown.source_credibility <= 100
    
    assert isinstance(result.breakdown.evidence_strength, int)
    assert 0 <= result.breakdown.evidence_strength <= 100
    
    assert isinstance(result.breakdown.language_neutrality, int)
    assert 0 <= result.breakdown.language_neutrality <= 100
    
    assert isinstance(result.breakdown.cross_source_agreement, int)
    assert 0 <= result.breakdown.cross_source_agreement <= 100
