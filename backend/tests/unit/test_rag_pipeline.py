"""Unit tests for RAG Pipeline.

Tests the RAGPipeline class for evidence retrieval, ranking, and error handling.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.schemas import Claim, EvidenceSet, SearchResult
from app.services.rag_pipeline import RAGPipeline


def make_claim(
    claim_id: str = "test-claim-1",
    text: str = "The Federal Reserve raised interest rates by 0.25%",
    claim_type: str = "banking",
) -> Claim:
    """Create a test Claim object."""
    return Claim(
        id=claim_id,
        text=text,
        start_index=0,
        end_index=len(text),
        type=claim_type,
        entities=["Federal Reserve"],
    )


def make_search_result(
    title: str = "Test Article",
    source: str = "Test Source",
    relevance_score: float = 0.8,
) -> SearchResult:
    """Create a test SearchResult object."""
    return SearchResult(
        title=title,
        source=source,
        summary="Test summary about the topic.",
        timestamp=datetime.now(timezone.utc).isoformat(),
        relevance_score=relevance_score,
    )


class TestRAGPipelineInit:
    """Tests for RAGPipeline initialization."""

    def test_init_with_default_top_k(self) -> None:
        """Test initialization with default top_k value."""
        mock_provider = MagicMock()
        pipeline = RAGPipeline(search_provider=mock_provider)
        
        assert pipeline._search_provider is mock_provider
        assert pipeline._top_k == 5

    def test_init_with_custom_top_k(self) -> None:
        """Test initialization with custom top_k value."""
        mock_provider = MagicMock()
        pipeline = RAGPipeline(search_provider=mock_provider, top_k=10)
        
        assert pipeline._top_k == 10


class TestRAGPipelineRetrieveEvidence:
    """Tests for RAGPipeline.retrieve_evidence method."""

    @pytest.mark.asyncio
    async def test_retrieve_evidence_returns_evidence_set(self) -> None:
        """Test that retrieve_evidence returns an EvidenceSet with results."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            make_search_result(title="Article 1", relevance_score=0.9),
            make_search_result(title="Article 2", relevance_score=0.7),
        ]
        pipeline = RAGPipeline(search_provider=mock_provider)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert isinstance(result, EvidenceSet)
        assert len(result.results) == 2
        assert result.insufficient_evidence is False
        mock_provider.search.assert_called_once_with(
            query=claim.text,
            claim_type=claim.type,
        )

    @pytest.mark.asyncio
    async def test_retrieve_evidence_ranks_by_relevance_descending(self) -> None:
        """Test that results are ranked by relevance_score descending (Req 3.3)."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            make_search_result(title="Low", relevance_score=0.3),
            make_search_result(title="High", relevance_score=0.95),
            make_search_result(title="Medium", relevance_score=0.6),
        ]
        pipeline = RAGPipeline(search_provider=mock_provider)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        scores = [r.relevance_score for r in result.results]
        assert scores == sorted(scores, reverse=True)
        assert result.results[0].title == "High"
        assert result.results[1].title == "Medium"
        assert result.results[2].title == "Low"

    @pytest.mark.asyncio
    async def test_retrieve_evidence_returns_top_k_results(self) -> None:
        """Test that only top-k results are returned (Req 3.2)."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            make_search_result(title=f"Article {i}", relevance_score=0.9 - i * 0.1)
            for i in range(10)
        ]
        pipeline = RAGPipeline(search_provider=mock_provider, top_k=3)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert len(result.results) == 3
        # Should be the top 3 by relevance score
        assert result.results[0].relevance_score == 0.9
        assert result.results[1].relevance_score == 0.8
        assert result.results[2].relevance_score == 0.7

    @pytest.mark.asyncio
    async def test_retrieve_evidence_handles_fewer_than_top_k_results(self) -> None:
        """Test handling when fewer results than top_k are returned."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            make_search_result(title="Only One", relevance_score=0.8),
        ]
        pipeline = RAGPipeline(search_provider=mock_provider, top_k=5)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert len(result.results) == 1
        assert result.insufficient_evidence is False

    @pytest.mark.asyncio
    async def test_retrieve_evidence_no_results_sets_insufficient_evidence(self) -> None:
        """Test that empty results set insufficient_evidence flag (Req 3.4)."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = []
        pipeline = RAGPipeline(search_provider=mock_provider)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert isinstance(result, EvidenceSet)
        assert len(result.results) == 0
        assert result.insufficient_evidence is True

    @pytest.mark.asyncio
    async def test_retrieve_evidence_handles_search_provider_error(self) -> None:
        """Test that search provider errors are handled gracefully."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.side_effect = Exception("Network error")
        pipeline = RAGPipeline(search_provider=mock_provider)
        claim = make_claim()

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert isinstance(result, EvidenceSet)
        assert len(result.results) == 0
        assert result.insufficient_evidence is True

    @pytest.mark.asyncio
    async def test_retrieve_evidence_passes_claim_type_to_provider(self) -> None:
        """Test that claim type is passed to the search provider (Req 3.1)."""
        # Arrange
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [make_search_result()]
        pipeline = RAGPipeline(search_provider=mock_provider)
        claim = make_claim(claim_type="crypto")

        # Act
        await pipeline.retrieve_evidence(claim)

        # Assert
        mock_provider.search.assert_called_once_with(
            query=claim.text,
            claim_type="crypto",
        )


class TestRAGPipelineIntegrationWithMockProvider:
    """Integration tests with MockSearchProvider."""

    @pytest.mark.asyncio
    async def test_integration_with_mock_search_provider(self) -> None:
        """Test RAGPipeline works with actual MockSearchProvider."""
        from app.services.mock_search_provider import MockSearchProvider

        # Arrange
        mock_provider = MockSearchProvider(seed=42)
        pipeline = RAGPipeline(search_provider=mock_provider, top_k=3)
        claim = make_claim(claim_type="banking")

        # Act
        result = await pipeline.retrieve_evidence(claim)

        # Assert
        assert isinstance(result, EvidenceSet)
        assert len(result.results) <= 3
        assert result.insufficient_evidence is False
        
        # Verify results are sorted by relevance descending
        scores = [r.relevance_score for r in result.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_integration_different_claim_types(self) -> None:
        """Test that different claim types produce different evidence."""
        from app.services.mock_search_provider import MockSearchProvider

        # Arrange
        mock_provider = MockSearchProvider(seed=42)
        pipeline = RAGPipeline(search_provider=mock_provider)
        
        banking_claim = make_claim(claim_type="banking")
        crypto_claim = make_claim(claim_type="crypto")

        # Act
        banking_result = await pipeline.retrieve_evidence(banking_claim)
        crypto_result = await pipeline.retrieve_evidence(crypto_claim)

        # Assert - results should differ based on claim type
        banking_sources = {r.source for r in banking_result.results}
        crypto_sources = {r.source for r in crypto_result.results}
        
        # At least some sources should be different
        assert banking_sources != crypto_sources or len(banking_sources) == 0
