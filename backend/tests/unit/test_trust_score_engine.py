"""Unit tests for TrustScoreEngine.

This module tests the trust score computation logic including:
- Weighted formula computation
- Sub-score calculations
- Deduction reference recording
- Edge cases and boundary conditions

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 28.1, 28.2, 28.3, 28.7
"""

import pytest

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    DeductionReference,
    EvidenceSet,
    NoCorroborationDeduction,
    SearchResult,
    TrustScoreWeights,
)
from app.services.trust_score_engine import TrustScoreEngine, TrustScoreResult


@pytest.fixture
def engine():
    """Create a TrustScoreEngine with default weights."""
    return TrustScoreEngine()


@pytest.fixture
def sample_claim():
    """Create a sample claim for testing."""
    return Claim(
        id="claim-1",
        text="Apple stock will rise 50% next quarter.",
        start_index=0,
        end_index=42,
        type="market",
        entities=["Apple"],
    )


@pytest.fixture
def sample_evidence():
    """Create sample evidence for testing."""
    return EvidenceSet(
        results=[
            SearchResult(
                title="Apple Q3 Earnings Report",
                source="Reuters",
                summary="Apple reported strong earnings, beating analyst expectations.",
                timestamp="2024-01-15T10:00:00Z",
                relevance_score=0.9,
            ),
            SearchResult(
                title="Tech Stocks Analysis",
                source="Bloomberg",
                summary="Analysts confirm positive outlook for Apple stock.",
                timestamp="2024-01-14T08:00:00Z",
                relevance_score=0.85,
            ),
        ],
        insufficient_evidence=False,
    )


@pytest.fixture
def sample_classification():
    """Create a sample classification for testing."""
    return ClassificationResult(
        claim_id="claim-1",
        label=ClassificationLabel.VERIFIED,
        reasoning="The claim is supported by credible sources.",
    )


class TestTrustScoreEngineInit:
    """Tests for TrustScoreEngine initialization."""
    
    def test_default_weights(self, engine):
        """Test that default weights are applied correctly."""
        assert engine.weights.source_credibility == 0.3
        assert engine.weights.evidence_strength == 0.3
        assert engine.weights.language_neutrality == 0.2
        assert engine.weights.cross_source_agreement == 0.2
    
    def test_custom_weights(self):
        """Test that custom weights can be provided."""
        custom_weights = TrustScoreWeights(
            source_credibility=0.4,
            evidence_strength=0.3,
            language_neutrality=0.15,
            cross_source_agreement=0.15,
        )
        engine = TrustScoreEngine(weights=custom_weights)
        
        assert engine.weights.source_credibility == 0.4
        assert engine.weights.evidence_strength == 0.3
        assert engine.weights.language_neutrality == 0.15
        assert engine.weights.cross_source_agreement == 0.15


class TestComputeMethod:
    """Tests for the main compute method."""
    
    def test_compute_returns_trust_score_result(
        self, engine, sample_claim, sample_evidence, sample_classification
    ):
        """Test that compute returns a TrustScoreResult."""
        result = engine.compute(
            claims=[sample_claim],
            evidence={sample_claim.id: sample_evidence},
            classifications={sample_claim.id: sample_classification},
        )
        
        assert isinstance(result, TrustScoreResult)
        assert isinstance(result.trust_score, int)
        assert result.breakdown is not None
    
    def test_trust_score_in_valid_range(
        self, engine, sample_claim, sample_evidence, sample_classification
    ):
        """Test that trust score is in [0, 100] range (Req 6.6)."""
        result = engine.compute(
            claims=[sample_claim],
            evidence={sample_claim.id: sample_evidence},
            classifications={sample_claim.id: sample_classification},
        )
        
        assert 0 <= result.trust_score <= 100
    
    def test_all_sub_scores_returned(
        self, engine, sample_claim, sample_evidence, sample_classification
    ):
        """Test that all four sub-scores are returned (Req 6.7)."""
        result = engine.compute(
            claims=[sample_claim],
            evidence={sample_claim.id: sample_evidence},
            classifications={sample_claim.id: sample_classification},
        )
        
        assert hasattr(result.breakdown, 'source_credibility')
        assert hasattr(result.breakdown, 'evidence_strength')
        assert hasattr(result.breakdown, 'language_neutrality')
        assert hasattr(result.breakdown, 'cross_source_agreement')
    
    def test_sub_scores_in_valid_range(
        self, engine, sample_claim, sample_evidence, sample_classification
    ):
        """Test that all sub-scores are in [0, 100] range (Req 6.2-6.5)."""
        result = engine.compute(
            claims=[sample_claim],
            evidence={sample_claim.id: sample_evidence},
            classifications={sample_claim.id: sample_classification},
        )
        
        assert 0 <= result.breakdown.source_credibility <= 100
        assert 0 <= result.breakdown.evidence_strength <= 100
        assert 0 <= result.breakdown.language_neutrality <= 100
        assert 0 <= result.breakdown.cross_source_agreement <= 100
    
    def test_empty_claims_returns_neutral_score(self, engine):
        """Test that empty claims list returns neutral score."""
        result = engine.compute(
            claims=[],
            evidence={},
            classifications={},
        )
        
        assert result.trust_score == 50
        assert result.breakdown.source_credibility == 50
        assert result.breakdown.evidence_strength == 50
        assert result.breakdown.language_neutrality == 50
        assert result.breakdown.cross_source_agreement == 50


class TestWeightedFormula:
    """Tests for the weighted formula computation (Req 6.1)."""
    
    def test_weighted_formula_correctness(self):
        """Test that the weighted formula is applied correctly."""
        # Create engine with default weights (0.3, 0.3, 0.2, 0.2)
        engine = TrustScoreEngine()
        
        # Create a claim with neutral language
        claim = Claim(
            id="test-claim",
            text="The company reported quarterly earnings.",
            start_index=0,
            end_index=40,
            type="market",
            entities=["company"],
        )
        
        # Create evidence from reputable sources
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test Article",
                    source="Reuters",
                    summary="The company confirms earnings report.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=1.0,
                ),
            ],
            insufficient_evidence=False,
        )
        
        classification = ClassificationResult(
            claim_id="test-claim",
            label=ClassificationLabel.VERIFIED,
            reasoning="Verified by credible source.",
        )
        
        result = engine.compute(
            claims=[claim],
            evidence={claim.id: evidence},
            classifications={claim.id: classification},
        )
        
        # Verify the formula: round(SC*0.3 + ES*0.3 + LN*0.2 + CSA*0.2)
        expected_raw = (
            result.breakdown.source_credibility * 0.3 +
            result.breakdown.evidence_strength * 0.3 +
            result.breakdown.language_neutrality * 0.2 +
            result.breakdown.cross_source_agreement * 0.2
        )
        expected_score = max(0, min(100, round(expected_raw)))
        
        assert result.trust_score == expected_score


class TestSourceCredibility:
    """Tests for source credibility sub-score computation (Req 6.2)."""
    
    def test_reputable_source_high_score(self, engine):
        """Test that reputable sources get high credibility scores."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test",
                    source="Reuters",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=1.0,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_source_credibility(evidence)
        assert score >= 80  # Reuters should have high credibility
    
    def test_unknown_source_moderate_score(self, engine):
        """Test that unknown sources get moderate credibility scores."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test",
                    source="Unknown Blog",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=1.0,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_source_credibility(evidence)
        assert 40 <= score <= 60  # Unknown source should be moderate
    
    def test_no_evidence_low_score(self, engine):
        """Test that no evidence results in low credibility score."""
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        score = engine._compute_source_credibility(evidence)
        assert score <= 40


class TestEvidenceStrength:
    """Tests for evidence strength sub-score computation (Req 6.3)."""
    
    def test_multiple_high_relevance_sources(self, engine):
        """Test that multiple high-relevance sources get high strength score."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title=f"Article {i}",
                    source=f"Source {i}",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                )
                for i in range(5)
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_evidence_strength(evidence)
        assert score >= 70
    
    def test_single_source_moderate_score(self, engine):
        """Test that single source gets moderate strength score."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Single Article",
                    source="Source",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_evidence_strength(evidence)
        assert 40 <= score <= 70
    
    def test_insufficient_evidence_low_score(self, engine):
        """Test that insufficient evidence gets low strength score."""
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        score = engine._compute_evidence_strength(evidence)
        assert score <= 30


class TestLanguageNeutrality:
    """Tests for language neutrality sub-score computation (Req 6.4)."""
    
    def test_neutral_language_high_score(self, engine):
        """Test that neutral language gets high neutrality score."""
        claim = Claim(
            id="test",
            text="The company reported quarterly earnings of $2.5 billion.",
            start_index=0,
            end_index=50,
            type="market",
            entities=["company"],
        )
        
        score = engine._compute_language_neutrality(claim)
        assert score >= 80
    
    def test_emotional_language_low_score(self, engine):
        """Test that emotional language gets lower neutrality score."""
        claim = Claim(
            id="test",
            text="URGENT! This stock will SKYROCKET! Don't miss out on MASSIVE GAINS!!!",
            start_index=0,
            end_index=70,
            type="market",
            entities=["stock"],
        )
        
        score = engine._compute_language_neutrality(claim)
        assert score <= 50
    
    def test_manipulative_language_low_score(self, engine):
        """Test that manipulative language gets lower neutrality score."""
        claim = Claim(
            id="test",
            text="This secret insider tip is guaranteed to make you rich!",
            start_index=0,
            end_index=55,
            type="investment",
            entities=[],
        )
        
        score = engine._compute_language_neutrality(claim)
        assert score <= 60


class TestCrossSourceAgreement:
    """Tests for cross-source agreement sub-score computation (Req 6.5)."""
    
    def test_agreeing_sources_high_score(self, engine):
        """Test that agreeing sources get high agreement score."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Article 1",
                    source="Source 1",
                    summary="The report confirms the company's strong performance.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Article 2",
                    source="Source 2",
                    summary="Analysts agree with the positive outlook.",
                    timestamp="2024-01-14T10:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_cross_source_agreement(evidence)
        assert score >= 70
    
    def test_contradicting_sources_low_score(self, engine):
        """Test that contradicting sources get lower agreement score."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Article 1",
                    source="Source 1",
                    summary="The claim is accurate according to our analysis.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Article 2",
                    source="Source 2",
                    summary="However, this contradicts official data.",
                    timestamp="2024-01-14T10:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_cross_source_agreement(evidence)
        assert score <= 70
    
    def test_single_source_neutral_score(self, engine):
        """Test that single source gets neutral agreement score."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Single Article",
                    source="Source",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
            ],
            insufficient_evidence=False,
        )
        
        score = engine._compute_cross_source_agreement(evidence)
        assert score == 50  # Neutral for single source


class TestDeductionReferences:
    """Tests for deduction reference recording (Req 28.1, 28.2, 28.3, 28.7)."""
    
    def test_deduction_reference_for_misleading_claim(self, engine):
        """Test that deduction references are recorded for misleading claims."""
        claim = Claim(
            id="claim-1",
            text="This stock is guaranteed to double.",
            start_index=0,
            end_index=35,
            type="investment",
            entities=["stock"],
        )
        
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Fact Check",
                    source="Reuters",
                    summary="This claim contradicts market analysis.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
            ],
            insufficient_evidence=False,
        )
        
        classification = ClassificationResult(
            claim_id="claim-1",
            label=ClassificationLabel.MISLEADING,
            reasoning="The claim is misleading.",
        )
        
        result = engine.compute(
            claims=[claim],
            evidence={claim.id: evidence},
            classifications={claim.id: classification},
        )
        
        assert len(result.deduction_references) > 0
        deduction = result.deduction_references[0]
        assert isinstance(deduction, DeductionReference)
        assert deduction.claim_id == claim.id
    
    def test_no_corroboration_deduction_for_insufficient_evidence(self, engine):
        """Test that NoCorroborationDeduction is recorded when no evidence found."""
        claim = Claim(
            id="claim-1",
            text="This obscure stock will triple.",
            start_index=0,
            end_index=32,
            type="investment",
            entities=["stock"],
        )
        
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        classification = ClassificationResult(
            claim_id="claim-1",
            label=ClassificationLabel.LIKELY_FALSE,
            reasoning="No evidence found to support this claim.",
        )
        
        result = engine.compute(
            claims=[claim],
            evidence={claim.id: evidence},
            classifications={claim.id: classification},
        )
        
        assert len(result.deduction_references) > 0
        deduction = result.deduction_references[0]
        assert isinstance(deduction, NoCorroborationDeduction)
        assert deduction.claim_id == claim.id
        assert "lack of corroborating evidence" in deduction.rationale
    
    def test_no_deductions_for_verified_claim(self, engine, sample_claim, sample_evidence):
        """Test that no deductions are recorded for verified claims."""
        classification = ClassificationResult(
            claim_id=sample_claim.id,
            label=ClassificationLabel.VERIFIED,
            reasoning="The claim is verified.",
        )
        
        result = engine.compute(
            claims=[sample_claim],
            evidence={sample_claim.id: sample_evidence},
            classifications={sample_claim.id: classification},
        )
        
        assert len(result.deduction_references) == 0
    
    def test_deduction_reference_contains_required_fields(self, engine):
        """Test that DeductionReference contains all required fields (Req 28.2)."""
        claim = Claim(
            id="claim-1",
            text="False claim about market.",
            start_index=0,
            end_index=25,
            type="market",
            entities=[],
        )
        
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Debunking Article",
                    source="Bloomberg",
                    summary="This claim is false and misleading.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
            ],
            insufficient_evidence=False,
        )
        
        classification = ClassificationResult(
            claim_id="claim-1",
            label=ClassificationLabel.LIKELY_FALSE,
            reasoning="The claim is false.",
        )
        
        result = engine.compute(
            claims=[claim],
            evidence={claim.id: evidence},
            classifications={claim.id: classification},
        )
        
        assert len(result.deduction_references) > 0
        deduction = result.deduction_references[0]
        
        if isinstance(deduction, DeductionReference):
            assert deduction.source_name is not None
            assert deduction.url is not None
            assert deduction.summary is not None
            assert deduction.contradiction_rationale is not None
