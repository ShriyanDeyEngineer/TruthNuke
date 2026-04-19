"""Search Provider Protocol.

This module defines the SearchProvider protocol that abstracts external data sources
for evidence retrieval in the RAG pipeline.

Requirements: 3.1, 4.1
"""

from typing import Protocol, runtime_checkable

from app.models.schemas import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for search providers that retrieve evidence for claim verification.
    
    This protocol defines the interface that all search providers must implement,
    enabling the RAG pipeline to work with different data sources (mock, live APIs,
    benchmark datasets) through a common interface.
    
    The protocol is async-compatible to support non-blocking I/O operations
    when querying external APIs.
    """

    async def search(self, query: str, claim_type: str) -> list[SearchResult]:
        """Search for evidence related to a query and claim type.
        
        Args:
            query: The search query text, typically the claim text to verify.
            claim_type: The category of the claim (banking, market, investment,
                       crypto, economic) to enable type-aware search.
        
        Returns:
            A list of SearchResult objects containing relevant evidence.
            Each result includes title, source, summary, timestamp, and
            relevance_score (0.0-1.0).
            
            Returns an empty list if no relevant results are found.
        """
        ...
