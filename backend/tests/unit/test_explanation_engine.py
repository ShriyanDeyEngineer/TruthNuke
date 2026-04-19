"""Unit tests for the ExplanationEngine.

Tests cover:
- Explanation generation with various inputs
- Emotional/manipulative language detection
- Evidence analysis (missing, conflicting, supporting)
- Fallback explanation generation
- Source name references
- Uncertainty language usage

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
    SearchResult,
    TrustScoreBreakdown,
)
from app.services.explanation_engine import (
    ExplanationEngine,
    FALLBACK_EXPLANATIONS,
)
from app.services.llm_client import LLMClient, LLMUnavailableError


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LLMClient)
    client.complete = AsyncMock(return_value="This is a test explanation.")
    return client


@pytest.fixture
def explanation_engine(mock_llm_client):
    """Create an ExplanationEngine with a mock LLM client."""
    return ExplanationEngine(mock_llm_client)


@pytest.fixture
def sample_claim():
    """Create a sample claim for testing."""
    return Claim(
        id="claim-123",
        text="The stock market will crash by 50% next month.",
        start_index=0,
        end_index=47,
        type="market",
        entities=["stock market"],
    )


@pytest.fixture
def sample_classification():
    """Create a sample classification result."""
    return ClassificationResult(
        claim_id="claim-123",
        label=ClassificationLabel.MISLEADING,
        reasoning="The claim makes an extreme prediction without supporting evidence.",
    )


@pytest.fixture
def sample_trust_score_breakdown():
    """Create a sample trust score breakdown."""
    return TrustScoreBreakdown(
        source_credibility=60,
        evidence_strength=40,
        language_neutrality=30,
        cross_source_agreement=50,
    )


@pytest.fixture
def sample_evidence():
    """Create a sample evidence set."""
    return EvidenceSet(
        results=[
            SearchResult(
                title="Market Analysis Report",
                source="Reuters",
                summary="Market analysts suggest moderate volatility ahead but no major crash expected.",
                timestamp="2024-01-15T10:00:00Z",
                relevance_score=0.85,
            ),
            SearchResult(
                title="Economic Outlook",
                source="Bloomberg",
                summary="Economic indicators remain stable with no signs of imminent market collapse.",
                timestamp="2024-01-14T14:30:00Z",
                relevance_score=0.78,
            ),
        ],
        insufficient_evidence=False,
    )


class TestExplanationEngineInit:
    """Tests for ExplanationEngine initialization."""
    
    def test_init_with_llm_client(self, mock_llm_client):
        """Test that ExplanationEngine initializes with an LLM client."""
        engine = ExplanationEngine(mock_llm_client)
        assert engine.llm_client == mock_llm_client


class TestGenerateExplanation:
    """Tests for the generate_explanation method."""
    
    @pytest.mark.asyncio
    async def test_generate_explanation_calls_llm(
        self,
        explanation_engine,
        mock_llm_client,
        sample_claim,
        sample_classification,
        sample_trust_score_breakdown,
        sample_evidence,
    ):
        """Test that generate_explanation calls the LLM client."""
        result = await explanation_engine.generate_explanation(
            claim=sample_claim,
            classification=sample_classification,
            trust_score=45,
            trust_score_breakdown=sample_trust_score_breakdown,
            evidence=sample_evidence,
        )
        
        mock_llm_client.complete.assert_called_once()
        assert result == "This is a test explanation."
    
    @pytest.mark.asyncio
    async def test_generate_explanation_returns_fallback_on_empty_response(
        self,
        explanation_engine,
        mock_llm_client,
        sample_claim,
        sample_classification,
        sample_trust_score_breakdown,
        sample_evidence,
    ):
        """Test that fallback is returned when LLM returns empty response (Req 7.5)."""
        mock_llm_client.complete = AsyncMock(return_value="")
        
        result = await explanation_engine.generate_explanation(
            claim=sample_claim,
            classification=sample_classification,
            trust_score=45,
            trust_score_breakdown=sample_trust_score_breakdown,
            evidence=sample_evidence,
        )
        
        # Should contain fallback text for MISLEADING classification
        assert "misleading" in result.lower() or "may contain" in result.lower()
    
    @pytest.mark.asyncio
    async def test_generate_explanation_returns_fallback_on_whitespace_response(
        self,
        explanation_engine,
        mock_llm_client,
        sample_claim,
        sample_classification,
        sample_trust_score_breakdown,
        sample_evidence,
    ):
        """Test that fallback is returned when LLM returns whitespace-only response."""
        mock_llm_client.complete = AsyncMock(return_value="   \n\t  ")
        
        result = await explanation_engine.generate_explanation(
            claim=sample_claim,
            classification=sample_classification,
            trust_score=45,
            trust_score_breakdown=sample_trust_score_breakdown,
            evidence=sample_evidence,
        )
        
        # Should contain fallback text
        assert len(result) > 0
        assert result.strip() != ""
    
    @pytest.mark.asyncio
    async def test_generate_explanation_raises_on_llm_unavailable(
        self,
        explanation_engine,
        mock_llm_client,
        sample_claim,
        sample_classification,
        sample_trust_score_breakdown,
        sample_evidence,
    ):
        """Test that LLMUnavailableError is re-raised."""
        mock_llm_client.complete = AsyncMock(
            side_effect=LLMUnavailableError("Service unavailable")
        )
        
        with pytest.raises(LLMUnavailableError):
            await explanation_engine.generate_explanation(
                claim=sample_claim,
                classification=sample_classification,
                trust_score=45,
                trust_score_breakdown=sample_trust_score_breakdown,
                evidence=sample_evidence,
            )
    
    @pytest.mark.asyncio
    async def test_generate_explanation_returns_fallback_on_unexpected_error(
        self,
        explanation_engine,
        mock_llm_client,
        sample_claim,
        sample_classification,
        sample_trust_score_breakdown,
        sample_evidence,
    ):
        """Test that fallback is returned on unexpected errors."""
        mock_llm_client.complete = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        
        result = await explanation_engine.generate_explanation(
            claim=sample_claim,
            classification=sample_classification,
            trust_score=45,
            trust_score_breakdown=sample_trust_score_breakdown,
            evidence=sample_evidence,
        )
        
        # Should return fallback instead of raising
        assert len(result) > 0


class TestDetectEmotionalPatterns:
    """Tests for emotional/manipulative language detection (Req 7.3)."""
    
    def test_detect_urgency_patterns(self, explanation_engine):
        """Test detection of urgency language."""
        text = "Act now! This is urgent and you must buy immediately!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "urgency" in categories
    
    def test_detect_hype_patterns(self, explanation_engine):
        """Test detection of hype language."""
        text = "This is a guaranteed way to get rich with risk-free returns!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "hype" in categories
    
    def test_detect_fear_patterns(self, explanation_engine):
        """Test detection of fear-inducing language."""
        text = "The market will crash and collapse into a disaster!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "fear-inducing" in categories
    
    def test_detect_greed_patterns(self, explanation_engine):
        """Test detection of greed-inducing language."""
        text = "Massive gains ahead! This stock will skyrocket to the moon!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "greed-inducing" in categories
    
    def test_detect_manipulation_patterns(self, explanation_engine):
        """Test detection of manipulation language."""
        text = "This is a secret insider tip they don't want you to know!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "manipulation" in categories
    
    def test_detect_excessive_punctuation(self, explanation_engine):
        """Test detection of excessive punctuation."""
        text = "Buy now!!! This is amazing???"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "excessive punctuation" in categories
    
    def test_detect_emphatic_capitalization(self, explanation_engine):
        """Test detection of emphatic capitalization (excluding acronyms)."""
        text = "This is ABSOLUTELY INCREDIBLE news!"
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        categories = [p["category"] for p in patterns]
        assert "emphatic capitalization" in categories
    
    def test_ignore_common_acronyms(self, explanation_engine):
        """Test that common financial acronyms are not flagged."""
        text = "The NYSE and NASDAQ are regulated by the SEC."
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        # Should not detect emphatic capitalization for acronyms
        categories = [p["category"] for p in patterns]
        assert "emphatic capitalization" not in categories
    
    def test_no_patterns_in_neutral_text(self, explanation_engine):
        """Test that neutral text has no detected patterns."""
        text = "The company reported quarterly earnings of $2.50 per share."
        patterns = explanation_engine._detect_emotional_patterns(text)
        
        assert len(patterns) == 0


class TestAnalyzeEvidence:
    """Tests for evidence analysis (Req 7.1, 7.2, 12.2)."""
    
    def test_analyze_empty_evidence(self, explanation_engine):
        """Test analysis of empty evidence set."""
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        analysis = explanation_engine._analyze_evidence(evidence)
        
        assert analysis["has_evidence"] is False
        assert analysis["insufficient_evidence"] is True
        assert analysis["source_count"] == 0
    
    def test_analyze_supporting_evidence(self, explanation_engine):
        """Test detection of supporting sources."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Report",
                    source="Reuters",
                    summary="This report confirms the claim is accurate.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
            ],
            insufficient_evidence=False,
        )
        analysis = explanation_engine._analyze_evidence(evidence)
        
        assert len(analysis["supporting_sources"]) == 1
        assert analysis["supporting_sources"][0]["name"] == "Reuters"
    
    def test_analyze_conflicting_evidence(self, explanation_engine):
        """Test detection of conflicting sources (Req 12.2)."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Fact Check",
                    source="AP",
                    summary="This claim contradicts official data and is misleading.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.95,
                ),
            ],
            insufficient_evidence=False,
        )
        analysis = explanation_engine._analyze_evidence(evidence)
        
        assert len(analysis["conflicting_sources"]) == 1
        assert analysis["conflicting_sources"][0]["name"] == "AP"
    
    def test_analyze_mixed_evidence(self, explanation_engine):
        """Test analysis with both supporting and conflicting sources."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Support",
                    source="Source A",
                    summary="This confirms the claim.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.8,
                ),
                SearchResult(
                    title="Conflict",
                    source="Source B",
                    summary="This contradicts the claim.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.85,
                ),
                SearchResult(
                    title="Neutral",
                    source="Source C",
                    summary="Related market data.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.7,
                ),
            ],
            insufficient_evidence=False,
        )
        analysis = explanation_engine._analyze_evidence(evidence)
        
        assert len(analysis["supporting_sources"]) == 1
        assert len(analysis["conflicting_sources"]) == 1
        assert len(analysis["neutral_sources"]) == 1


class TestFallbackExplanation:
    """Tests for fallback explanation generation (Req 7.5)."""
    
    def test_fallback_for_verified(self, explanation_engine):
        """Test fallback explanation for VERIFIED classification."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.VERIFIED, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=False)
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "supported" in result.lower() or "verify" in result.lower()
    
    def test_fallback_for_misleading(self, explanation_engine):
        """Test fallback explanation for MISLEADING classification."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.MISLEADING, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=False)
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "misleading" in result.lower()
    
    def test_fallback_for_likely_false(self, explanation_engine):
        """Test fallback explanation for LIKELY_FALSE classification."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.LIKELY_FALSE, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=False)
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "conflict" in result.lower() or "not be accurate" in result.lower()
    
    def test_fallback_for_harmful(self, explanation_engine):
        """Test fallback explanation for HARMFUL classification."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.HARMFUL, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=False)
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "harmful" in result.lower() or "caution" in result.lower()
    
    def test_fallback_includes_source_names(self, explanation_engine):
        """Test that fallback includes source names when available (Req 7.5)."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.VERIFIED, reasoning="Test"
        )
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Report",
                    source="Reuters",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Analysis",
                    source="Bloomberg",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "Reuters" in result
        assert "Bloomberg" in result
    
    def test_fallback_mentions_insufficient_evidence(self, explanation_engine):
        """Test that fallback mentions insufficient evidence (Req 7.1)."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.MISLEADING, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, []
        )
        
        assert "limited evidence" in result.lower() or "insufficient" in result.lower()
    
    def test_fallback_mentions_emotional_patterns(self, explanation_engine):
        """Test that fallback mentions detected emotional patterns (Req 7.3)."""
        claim = Claim(
            id="1", text="Test claim", start_index=0, end_index=10,
            type="market", entities=[]
        )
        classification = ClassificationResult(
            claim_id="1", label=ClassificationLabel.MISLEADING, reasoning="Test"
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=False)
        patterns = [
            {"category": "urgency", "matched_text": "act now"},
            {"category": "hype", "matched_text": "guaranteed"},
        ]
        
        result = explanation_engine._generate_fallback_explanation(
            claim, classification, evidence, patterns
        )
        
        assert "language" in result.lower() or "pattern" in result.lower()


class TestPromptBuilding:
    """Tests for prompt building methods."""
    
    def test_format_evidence_section_with_no_evidence(self, explanation_engine):
        """Test evidence section formatting with no evidence."""
        analysis = {
            "has_evidence": False,
            "insufficient_evidence": True,
            "source_count": 0,
            "supporting_sources": [],
            "conflicting_sources": [],
            "neutral_sources": [],
        }
        
        result = explanation_engine._format_evidence_section(analysis)
        
        assert "No evidence was found" in result
    
    def test_format_evidence_section_with_sources(self, explanation_engine):
        """Test evidence section formatting with sources."""
        analysis = {
            "has_evidence": True,
            "insufficient_evidence": False,
            "source_count": 2,
            "supporting_sources": [
                {"name": "Reuters", "title": "Report", "summary": "Confirms claim", "relevance": 0.9}
            ],
            "conflicting_sources": [
                {"name": "AP", "title": "Fact Check", "summary": "Contradicts claim", "relevance": 0.85}
            ],
            "neutral_sources": [],
        }
        
        result = explanation_engine._format_evidence_section(analysis)
        
        assert "Reuters" in result
        assert "AP" in result
        assert "Supporting sources" in result
        assert "Conflicting sources" in result
    
    def test_format_patterns_section_with_no_patterns(self, explanation_engine):
        """Test patterns section formatting with no patterns."""
        result = explanation_engine._format_patterns_section([])
        
        assert "No concerning language patterns detected" in result
    
    def test_format_patterns_section_with_patterns(self, explanation_engine):
        """Test patterns section formatting with patterns."""
        patterns = [
            {"category": "urgency", "matched_text": "act now"},
            {"category": "urgency", "matched_text": "immediately"},
            {"category": "hype", "matched_text": "guaranteed"},
        ]
        
        result = explanation_engine._format_patterns_section(patterns)
        
        assert "Urgency" in result
        assert "Hype" in result
    
    def test_format_score_section(self, explanation_engine, sample_trust_score_breakdown):
        """Test score section formatting."""
        result = explanation_engine._format_score_section(45, sample_trust_score_breakdown)
        
        assert "Source Credibility: 60/100" in result
        assert "Evidence Strength: 40/100" in result
        assert "Language Neutrality: 30/100" in result
        assert "Cross-Source Agreement: 50/100" in result
        assert "Moderate trust score" in result  # 45 is in moderate range
    
    def test_format_score_section_high_score(self, explanation_engine):
        """Test score section formatting for high trust score."""
        breakdown = TrustScoreBreakdown(
            source_credibility=80,
            evidence_strength=85,
            language_neutrality=90,
            cross_source_agreement=75,
        )
        
        result = explanation_engine._format_score_section(82, breakdown)
        
        assert "High trust score" in result
    
    def test_format_score_section_low_score(self, explanation_engine):
        """Test score section formatting for low trust score."""
        breakdown = TrustScoreBreakdown(
            source_credibility=20,
            evidence_strength=25,
            language_neutrality=30,
            cross_source_agreement=15,
        )
        
        result = explanation_engine._format_score_section(22, breakdown)
        
        assert "Low trust score" in result


class TestSystemPrompt:
    """Tests for system prompt generation."""
    
    def test_system_prompt_contains_key_principles(self, explanation_engine):
        """Test that system prompt contains key principles."""
        prompt = explanation_engine._get_system_prompt()
        
        # Should mention uncertainty language (Req 7.4, 11.2)
        assert "uncertainty" in prompt.lower() or "absolute" in prompt.lower()
        
        # Should mention sources (Req 7.5)
        assert "source" in prompt.lower()
        
        # Should mention educational aspect (Req 11.2)
        assert "educational" in prompt.lower() or "help" in prompt.lower()
