"""RAG Pipeline.

This module provides the Retrieval-Augmented Generation pipeline that queries
external data sources to retrieve evidence for verifying extracted claims.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

import logging
from typing import Protocol, runtime_checkable

from app.models.schemas import Claim, EvidenceSet, SearchResult


logger = logging.getLogger(__name__)


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for search providers that retrieve evidence for claim verification."""

    async def search(self, query: str, claim_type: str) -> list[SearchResult]:
        """Search for evidence related to a query and claim type."""
        ...


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for evidence retrieval.
    
    This pipeline queries a configurable search provider to retrieve evidence
    for claim verification. It ranks results by relevance score and returns
    the top-k results as an EvidenceSet.
    
    The pipeline uses the strategy pattern to accept any SearchProvider
    implementation, enabling easy swapping between mock, live, and benchmark
    data sources.
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        top_k: int = 5,
    ) -> None:
        """Initialize the RAG pipeline.
        
        Args:
            search_provider: A SearchProvider instance for evidence retrieval.
                Can be MockSearchProvider, LiveSearchProvider, or any other
                implementation of the SearchProvider protocol.
            top_k: Maximum number of results to return (default 5).
        """
        self._search_provider = search_provider
        self._top_k = top_k

    async def retrieve_evidence(self, claim: Claim) -> EvidenceSet:
        """Retrieve evidence for a claim from the search provider.
        
        Queries the configured search provider with the claim text and type,
        ranks results by relevance_score in descending order, and returns
        the top-k results as an EvidenceSet.
        
        Args:
            claim: The Claim object to retrieve evidence for.
        
        Returns:
            An EvidenceSet containing the top-k search results ranked by
            relevance_score descending. If no results are found or an error
            occurs, returns an EvidenceSet with insufficient_evidence=True.
        
        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        try:
            # Query the search provider (Req 3.1)
            results = await self._search_provider.search(
                query=claim.text,
                claim_type=claim.type,
            )

            # Handle no results case (Req 3.4)
            if not results:
                logger.info(
                    f"No search results found for claim {claim.id}: {claim.text[:50]}..."
                )
                return EvidenceSet(
                    results=[],
                    insufficient_evidence=True,
                )

            # Rank results by relevance_score descending (Req 3.3)
            sorted_results = sorted(
                results,
                key=lambda r: r.relevance_score,
                reverse=True,
            )

            # Return top-k results (Req 3.2)
            top_results = sorted_results[: self._top_k]

            return EvidenceSet(
                results=top_results,
                insufficient_evidence=False,
            )

        except Exception as e:
            # Handle search provider errors: log and return empty EvidenceSet
            logger.error(
                f"Search provider error for claim {claim.id}: {e}",
                exc_info=True,
            )
            return EvidenceSet(
                results=[],
                insufficient_evidence=True,
            )
