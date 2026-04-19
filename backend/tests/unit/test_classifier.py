"""Unit tests for the Classifier.

Tests cover:
- Classification with valid evidence → correct label and reasoning
- Classification with empty evidence → includes "insufficient evidence" in reasoning
- Classification with conflicting evidence → reflects conflict in reasoning
- Invalid LLM label → ClassificationError
- Each valid classification label

Requirements: 5.1, 5.2, 5.3, 5.4, 12.2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
    SearchResult,
)
from app.services.classifier import Classifier, ClassificationError, VALID_LABELS
from app.services.llm_client import LLMClient, LLMParsingError, LLMUnavailableError


class TestClassifierInit:
    """Tests for Classifier initialization."""
    
    def test_init_with_llm_client(self):
        """Test that Classifier initializes with an LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        classifier = Classifier(llm_client=mock_client)
        assert classifier.llm_client is mock_client


class TestClassifierClassify:
    """Tests for Classifier.classify() method."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        return MagicMock(spec=LLMClient)
    
    @pytest.fixture
    def classifier(self, mock_llm_client):
        """Create a Classifier with mock LLM client."""
        return Classifier(llm_client=mock_llm_client)
    
    @pytest.fixture
    def sample_claim(self):
        """Create a sample claim for testing."""
        return Claim(
            id="test-claim-id",
            text="Apple stock rose 10% today.",
            start_index=0,
            end_index=27,
            type="market",
            entities=["Apple"]
        )
    
    @pytest.fixture
    def sample_evidence(self):
        """Create sample evidence for testing."""
        return EvidenceSet(
            results=[
                SearchResult(
                    title="Apple Reports Strong Q4 Earnings",
                    source="Reuters",
                    summary="Apple Inc. reported better-than-expected quarterly earnings, with stock rising 10%.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.95,
                ),
                SearchResult(
                    title="Tech Stocks Rally",
                    source="Bloomberg",
                    summary="Technology stocks including Apple saw significant gains today.",
                    timestamp="2024-01-15T11:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
    
    @pytest.fixture
    def empty_evidence(self):
        """Create empty evidence for testing."""
        return EvidenceSet(
            results=[],
            insufficient_evidence=True,
        )
    
    @pytest.mark.asyncio
    async def test_classify_returns_verified_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test classification returns VERIFIED label with reasoning.
        
        Validates: Requirements 5.1, 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED",
            "reasoning": "The claim is supported by multiple credible sources including Reuters and Bloomberg."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert isinstance(result, ClassificationResult)
        assert result.claim_id == "test-claim-id"
        assert result.label == ClassificationLabel.VERIFIED
        assert "supported" in result.reasoning.lower() or "credible" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_classify_returns_misleading_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test classification returns MISLEADING label.
        
        Validates: Requirements 5.1, 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "MISLEADING",
            "reasoning": "The claim contains some truth but omits important context about market conditions."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.MISLEADING
        assert len(result.reasoning) > 0
    
    @pytest.mark.asyncio
    async def test_classify_returns_likely_false_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test classification returns LIKELY_FALSE label.
        
        Validates: Requirements 5.1, 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "LIKELY_FALSE",
            "reasoning": "The claim contradicts available evidence from credible sources."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.LIKELY_FALSE
        assert len(result.reasoning) > 0
    
    @pytest.mark.asyncio
    async def test_classify_returns_harmful_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test classification returns HARMFUL label.
        
        Validates: Requirements 5.1, 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "HARMFUL",
            "reasoning": "The claim could cause financial harm if acted upon, resembling pump-and-dump scheme language."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.HARMFUL
        assert len(result.reasoning) > 0
    
    @pytest.mark.asyncio
    async def test_classify_with_empty_evidence_includes_insufficient_evidence(
        self, classifier, mock_llm_client, sample_claim, empty_evidence
    ):
        """Test classification with empty evidence includes 'insufficient evidence' in reasoning.
        
        Validates: Requirements 5.4
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "LIKELY_FALSE",
            "reasoning": "Due to insufficient evidence, the claim cannot be verified. No supporting sources were found."
        })
        
        result = await classifier.classify(sample_claim, empty_evidence)
        
        assert result.label == ClassificationLabel.LIKELY_FALSE
        # Verify the prompt included insufficient evidence note
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        assert "insufficient evidence" in call_kwargs["prompt"].lower() or "no evidence" in call_kwargs["prompt"].lower()
    
    @pytest.mark.asyncio
    async def test_classify_with_conflicting_evidence_reflects_conflict(
        self, classifier, mock_llm_client, sample_claim
    ):
        """Test classification with conflicting evidence reflects conflict in reasoning.
        
        Validates: Requirements 12.2
        """
        conflicting_evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Apple Stock Rises",
                    source="Reuters",
                    summary="Apple stock rose 10% following strong earnings.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.95,
                ),
                SearchResult(
                    title="Apple Stock Analysis",
                    source="Bloomberg",
                    summary="However, analysts dispute the 10% figure, citing only a 5% increase.",
                    timestamp="2024-01-15T11:00:00Z",
                    relevance_score=0.90,
                ),
            ],
            insufficient_evidence=False,
        )
        
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "MISLEADING",
            "reasoning": "Sources provide conflicting information about the exact percentage increase."
        })
        
        result = await classifier.classify(sample_claim, conflicting_evidence)
        
        # Verify the prompt included conflict note
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        assert "conflict" in call_kwargs["prompt"].lower()
    
    @pytest.mark.asyncio
    async def test_classify_raises_on_invalid_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that invalid LLM label raises ClassificationError.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "INVALID_LABEL",
            "reasoning": "Some reasoning"
        })
        
        with pytest.raises(ClassificationError, match="invalid classification label"):
            await classifier.classify(sample_claim, sample_evidence)
    
    @pytest.mark.asyncio
    async def test_classify_raises_on_empty_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that empty label raises ClassificationError.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "",
            "reasoning": "Some reasoning"
        })
        
        with pytest.raises(ClassificationError, match="invalid classification label"):
            await classifier.classify(sample_claim, sample_evidence)
    
    @pytest.mark.asyncio
    async def test_classify_raises_on_missing_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that missing label raises ClassificationError.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "reasoning": "Some reasoning"
        })
        
        with pytest.raises(ClassificationError, match="invalid classification label"):
            await classifier.classify(sample_claim, sample_evidence)
    
    @pytest.mark.asyncio
    async def test_classify_handles_lowercase_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that lowercase labels are accepted and normalized.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "verified",  # lowercase
            "reasoning": "The claim is verified."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.VERIFIED
    
    @pytest.mark.asyncio
    async def test_classify_handles_mixed_case_label(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that mixed case labels are accepted and normalized.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "Likely_False",  # mixed case
            "reasoning": "The claim is likely false."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.LIKELY_FALSE
    
    @pytest.mark.asyncio
    async def test_classify_handles_label_with_whitespace(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that labels with whitespace are trimmed.
        
        Validates: Requirements 5.1
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "  VERIFIED  ",  # with whitespace
            "reasoning": "The claim is verified."
        })
        
        result = await classifier.classify(sample_claim, sample_evidence)
        
        assert result.label == ClassificationLabel.VERIFIED
    
    @pytest.mark.asyncio
    async def test_classify_handles_empty_reasoning(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that empty reasoning gets default value.
        
        Validates: Requirements 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED",
            "reasoning": ""
        })
        
        with patch("app.services.classifier.logger") as mock_logger:
            result = await classifier.classify(sample_claim, sample_evidence)
            
            assert result.label == ClassificationLabel.VERIFIED
            assert len(result.reasoning) > 0  # Should have default reasoning
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_classify_handles_missing_reasoning(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that missing reasoning gets default value.
        
        Validates: Requirements 5.2
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED"
        })
        
        with patch("app.services.classifier.logger") as mock_logger:
            result = await classifier.classify(sample_claim, sample_evidence)
            
            assert result.label == ClassificationLabel.VERIFIED
            assert len(result.reasoning) > 0  # Should have default reasoning
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_classify_propagates_llm_unavailable_error(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that LLMUnavailableError is propagated."""
        mock_llm_client.complete_json = AsyncMock(
            side_effect=LLMUnavailableError("LLM service unavailable")
        )
        
        with pytest.raises(LLMUnavailableError):
            await classifier.classify(sample_claim, sample_evidence)
    
    @pytest.mark.asyncio
    async def test_classify_propagates_llm_parsing_error(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that LLMParsingError returns a fallback classification instead of crashing."""
        mock_llm_client.complete_json = AsyncMock(
            side_effect=LLMParsingError("Invalid JSON response")
        )
        
        result = await classifier.classify(sample_claim, sample_evidence)
        # Should return a fallback MISLEADING classification
        assert result.label == ClassificationLabel.MISLEADING
        assert "could not be fully determined" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_classify_includes_claim_entities_in_prompt(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that claim entities are included in the prompt."""
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED",
            "reasoning": "Verified."
        })
        
        await classifier.classify(sample_claim, sample_evidence)
        
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        assert "Apple" in call_kwargs["prompt"]
    
    @pytest.mark.asyncio
    async def test_classify_includes_evidence_sources_in_prompt(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that evidence sources are included in the prompt.
        
        Validates: Requirements 5.3
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED",
            "reasoning": "Verified."
        })
        
        await classifier.classify(sample_claim, sample_evidence)
        
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        assert "Reuters" in call_kwargs["prompt"]
        assert "Bloomberg" in call_kwargs["prompt"]
    
    @pytest.mark.asyncio
    async def test_classify_includes_claim_type_in_prompt(
        self, classifier, mock_llm_client, sample_claim, sample_evidence
    ):
        """Test that claim type is included in the prompt.
        
        Validates: Requirements 5.3
        """
        mock_llm_client.complete_json = AsyncMock(return_value={
            "label": "VERIFIED",
            "reasoning": "Verified."
        })
        
        await classifier.classify(sample_claim, sample_evidence)
        
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        assert "market" in call_kwargs["prompt"].lower()


class TestClassifierBuildPrompt:
    """Tests for Classifier._build_classification_prompt() method."""
    
    @pytest.fixture
    def classifier(self):
        """Create a Classifier with mock LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        return Classifier(llm_client=mock_client)
    
    @pytest.fixture
    def sample_claim(self):
        """Create a sample claim for testing."""
        return Claim(
            id="test-claim-id",
            text="Apple stock rose 10% today.",
            start_index=0,
            end_index=27,
            type="market",
            entities=["Apple"]
        )
    
    def test_build_prompt_with_evidence(self, classifier, sample_claim):
        """Test prompt building with evidence."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test Article",
                    source="Test Source",
                    summary="Test summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                )
            ],
            insufficient_evidence=False,
        )
        
        prompt = classifier._build_classification_prompt(sample_claim, evidence)
        
        assert "Apple stock rose 10% today." in prompt
        assert "market" in prompt.lower()
        assert "Apple" in prompt
        assert "Test Source" in prompt
        assert "Test Article" in prompt
        assert "Test summary" in prompt
    
    def test_build_prompt_with_empty_evidence(self, classifier, sample_claim):
        """Test prompt building with empty evidence."""
        evidence = EvidenceSet(
            results=[],
            insufficient_evidence=True,
        )
        
        prompt = classifier._build_classification_prompt(sample_claim, evidence)
        
        assert "Apple stock rose 10% today." in prompt
        assert "no evidence" in prompt.lower() or "insufficient evidence" in prompt.lower()
    
    def test_build_prompt_with_no_entities(self, classifier):
        """Test prompt building with claim that has no entities."""
        claim = Claim(
            id="test-id",
            text="The market is volatile.",
            start_index=0,
            end_index=23,
            type="market",
            entities=[]
        )
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        prompt = classifier._build_classification_prompt(claim, evidence)
        
        assert "The market is volatile." in prompt
        # Should not have "Entities mentioned" line when empty
        assert "Entities mentioned:" not in prompt


class TestClassifierDetectConflictingEvidence:
    """Tests for Classifier._detect_conflicting_evidence() method."""
    
    @pytest.fixture
    def classifier(self):
        """Create a Classifier with mock LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        return Classifier(llm_client=mock_client)
    
    def test_detect_no_conflict_with_single_result(self, classifier):
        """Test no conflict detected with single result."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test",
                    source="Source",
                    summary="Normal summary",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                )
            ],
            insufficient_evidence=False,
        )
        
        result = classifier._detect_conflicting_evidence(evidence)
        
        assert result is False
    
    def test_detect_no_conflict_with_empty_results(self, classifier):
        """Test no conflict detected with empty results."""
        evidence = EvidenceSet(results=[], insufficient_evidence=True)
        
        result = classifier._detect_conflicting_evidence(evidence)
        
        assert result is False
    
    def test_detect_conflict_with_contradiction_keyword(self, classifier):
        """Test conflict detected with contradiction keyword."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test 1",
                    source="Source 1",
                    summary="The stock rose 10%.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Test 2",
                    source="Source 2",
                    summary="However, other analysts dispute this figure.",
                    timestamp="2024-01-15T11:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        result = classifier._detect_conflicting_evidence(evidence)
        
        assert result is True
    
    def test_detect_conflict_with_contrary_keyword(self, classifier):
        """Test conflict detected with 'contrary' keyword."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test 1",
                    source="Source 1",
                    summary="The company reported profits.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Test 2",
                    source="Source 2",
                    summary="Contrary to reports, the company had losses.",
                    timestamp="2024-01-15T11:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        result = classifier._detect_conflicting_evidence(evidence)
        
        assert result is True
    
    def test_detect_no_conflict_with_agreeing_sources(self, classifier):
        """Test no conflict detected with agreeing sources."""
        evidence = EvidenceSet(
            results=[
                SearchResult(
                    title="Test 1",
                    source="Source 1",
                    summary="Apple stock rose 10% today.",
                    timestamp="2024-01-15T10:00:00Z",
                    relevance_score=0.9,
                ),
                SearchResult(
                    title="Test 2",
                    source="Source 2",
                    summary="Apple shares increased by 10% following earnings.",
                    timestamp="2024-01-15T11:00:00Z",
                    relevance_score=0.85,
                ),
            ],
            insufficient_evidence=False,
        )
        
        result = classifier._detect_conflicting_evidence(evidence)
        
        assert result is False


class TestClassificationError:
    """Tests for ClassificationError exception class."""
    
    def test_classification_error_message(self):
        """Test ClassificationError has correct message."""
        error = ClassificationError("Test error message")
        assert str(error) == "Test error message"
    
    def test_classification_error_is_exception(self):
        """Test ClassificationError is an Exception."""
        assert issubclass(ClassificationError, Exception)


class TestValidLabels:
    """Tests for VALID_LABELS constant."""
    
    def test_valid_labels_contains_all_classification_labels(self):
        """Test VALID_LABELS contains all ClassificationLabel values."""
        expected = {"VERIFIED", "MISLEADING", "LIKELY_FALSE", "HARMFUL"}
        assert VALID_LABELS == expected
    
    def test_valid_labels_matches_enum(self):
        """Test VALID_LABELS matches ClassificationLabel enum."""
        enum_values = {label.value for label in ClassificationLabel}
        assert VALID_LABELS == enum_values
