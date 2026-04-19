"""
Property-based tests for RAG Pipeline evidence ranking.

This module tests:
- Property 4: Evidence results are ranked by descending relevance score

**Validates: Requirements 3.3**
"""

import asyncio
from datetime import datetime, timezone
from hypothesis import given, strategies as st, settings, assume

from app.models.schemas import Claim, SearchResult, EvidenceSet
from app.services.rag_pipeline import RAGPipeline, SearchProvider


# =============================================================================
# Strategies for generating test data
# =============================================================================


# Strategy for generating valid relevance scores in [0.0, 1.0]
relevance_score_strategy = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)


# Strategy for generating non-empty strings for SearchResult fields
non_empty_string_strategy = st.text(min_size=1, max_size=100).filter(
    lambda s: s.strip()
)


# Strategy for generating valid ISO 8601 timestamps
timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2025, 12, 31),
).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat())


@st.composite
def search_result_strategy(draw):
    """
    Hypothesis composite strategy for generating valid SearchResult objects.
    
    Generates SearchResult with random but valid field values.
    """
    return SearchResult(
        title=draw(non_empty_string_strategy),
        source=draw(non_empty_string_strategy),
        summary=draw(non_empty_string_strategy),
        timestamp=draw(timestamp_strategy),
        relevance_score=draw(relevance_score_strategy),
        source_type="external",
    )


@st.composite
def search_result_list_strategy(draw, min_size=0, max_size=20):
    """
    Hypothesis composite strategy for generating lists of SearchResult objects.
    
    Args:
        min_size: Minimum number of results to generate
        max_size: Maximum number of results to generate
    
    Returns:
        A list of SearchResult objects with random relevance scores
    """
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    results = []
    for _ in range(size):
        results.append(draw(search_result_strategy()))
    return results


# Strategy for generating valid claim types
claim_type_strategy = st.sampled_from(
    ["banking", "market", "investment", "crypto", "economic"]
)


@st.composite
def claim_strategy(draw):
    """
    Hypothesis composite strategy for generating valid Claim objects.
    """
    text = draw(non_empty_string_strategy)
    return Claim(
        id=draw(st.uuids().map(str)),
        text=text,
        start_index=0,
        end_index=len(text),
        type=draw(claim_type_strategy),
        entities=[],
    )


# =============================================================================
# Mock Search Provider for testing
# =============================================================================


class MockSearchProviderForTest:
    """
    A mock search provider that returns pre-configured results.
    
    This allows us to test the RAG pipeline's sorting behavior
    with controlled input data.
    """
    
    def __init__(self, results: list[SearchResult]):
        """
        Initialize with a list of results to return.
        
        Args:
            results: The SearchResult list to return from search()
        """
        self._results = results
    
    async def search(self, query: str, claim_type: str) -> list[SearchResult]:
        """Return the pre-configured results."""
        return self._results


# =============================================================================
# Property 4: Evidence results are ranked by descending relevance score
# =============================================================================


@given(
    results=search_result_list_strategy(min_size=0, max_size=20),
    claim=claim_strategy(),
    top_k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_evidence_results_ranked_by_descending_relevance_score(results, claim, top_k):
    """
    Property 4: Evidence results are ranked by descending relevance score.
    
    For any list of SearchResults returned by the RAG Pipeline for a Claim,
    each result's `relevance_score` must be greater than or equal to the
    `relevance_score` of the result that follows it in the list.
    
    **Validates: Requirements 3.3**
    
    This property ensures:
    1. Results are sorted by relevance_score in descending order
    2. The sorting is stable and consistent
    3. The property holds for any list size (empty, single, multiple)
    """
    # Create a mock provider that returns our random results
    mock_provider = MockSearchProviderForTest(results)
    
    # Create the RAG pipeline with the mock provider
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=top_k)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    
    # Assert the output is an EvidenceSet
    assert isinstance(evidence_set, EvidenceSet)
    
    # Get the results from the evidence set
    output_results = evidence_set.results
    
    # Assert results are sorted by relevance_score descending
    for i in range(len(output_results) - 1):
        current_score = output_results[i].relevance_score
        next_score = output_results[i + 1].relevance_score
        assert current_score >= next_score, (
            f"Results not sorted descending at index {i}: "
            f"score {current_score} should be >= {next_score}. "
            f"Full scores: {[r.relevance_score for r in output_results]}"
        )


@given(
    results=search_result_list_strategy(min_size=0, max_size=20),
    claim=claim_strategy(),
    top_k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_top_k_limiting_preserves_sorted_order(results, claim, top_k):
    """
    Property 4 (variant): Top-k limiting works correctly with sorted results.
    
    When the RAG pipeline limits results to top_k, the returned results
    should still be sorted by descending relevance score, and should
    contain the k highest-scoring results.
    
    **Validates: Requirements 3.3**
    """
    # Create a mock provider that returns our random results
    mock_provider = MockSearchProviderForTest(results)
    
    # Create the RAG pipeline with the mock provider
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=top_k)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    output_results = evidence_set.results
    
    # The number of results should be min(len(results), top_k)
    expected_count = min(len(results), top_k)
    assert len(output_results) == expected_count, (
        f"Expected {expected_count} results, got {len(output_results)}"
    )
    
    # Results should be sorted descending
    output_scores = [r.relevance_score for r in output_results]
    assert output_scores == sorted(output_scores, reverse=True), (
        f"Results not sorted descending: {output_scores}"
    )
    
    # The returned results should be the top-k highest scoring from input
    if results:
        input_sorted = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        expected_top_k = input_sorted[:top_k]
        expected_scores = sorted([r.relevance_score for r in expected_top_k], reverse=True)
        
        assert output_scores == expected_scores, (
            f"Output scores {output_scores} don't match expected top-k scores {expected_scores}"
        )


@given(claim=claim_strategy())
@settings(max_examples=100)
def test_empty_results_handled_correctly(claim):
    """
    Property 4 (variant): Empty result lists are handled correctly.
    
    When the search provider returns no results, the RAG pipeline should
    return an EvidenceSet with an empty results list and insufficient_evidence=True.
    
    **Validates: Requirements 3.3, 3.4**
    """
    # Create a mock provider that returns empty results
    mock_provider = MockSearchProviderForTest([])
    
    # Create the RAG pipeline
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=5)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    
    # Assert empty results and insufficient_evidence flag
    assert isinstance(evidence_set, EvidenceSet)
    assert len(evidence_set.results) == 0
    assert evidence_set.insufficient_evidence is True


@given(
    result=search_result_strategy(),
    claim=claim_strategy(),
)
@settings(max_examples=100)
def test_single_result_handled_correctly(result, claim):
    """
    Property 4 (variant): Single result lists are handled correctly.
    
    When the search provider returns exactly one result, the RAG pipeline
    should return that result (trivially sorted).
    
    **Validates: Requirements 3.3**
    """
    # Create a mock provider that returns a single result
    mock_provider = MockSearchProviderForTest([result])
    
    # Create the RAG pipeline
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=5)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    
    # Assert single result is returned
    assert len(evidence_set.results) == 1
    assert evidence_set.results[0].relevance_score == result.relevance_score
    assert evidence_set.insufficient_evidence is False


@given(
    results=search_result_list_strategy(min_size=2, max_size=20),
    claim=claim_strategy(),
)
@settings(max_examples=100)
def test_multiple_results_sorted_correctly(results, claim):
    """
    Property 4 (variant): Multiple results are sorted correctly.
    
    When the search provider returns multiple results with varying
    relevance scores, the RAG pipeline should sort them in descending order.
    
    **Validates: Requirements 3.3**
    """
    # Ensure we have at least 2 results
    assume(len(results) >= 2)
    
    # Create a mock provider that returns our results
    mock_provider = MockSearchProviderForTest(results)
    
    # Create the RAG pipeline with high top_k to get all results
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=100)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    output_results = evidence_set.results
    
    # Verify descending order
    for i in range(len(output_results) - 1):
        assert output_results[i].relevance_score >= output_results[i + 1].relevance_score, (
            f"Results not sorted at index {i}: "
            f"{output_results[i].relevance_score} should be >= {output_results[i + 1].relevance_score}"
        )


@given(
    relevance_scores=st.lists(
        relevance_score_strategy,
        min_size=2,
        max_size=15,
    ),
    claim=claim_strategy(),
)
@settings(max_examples=100)
def test_relevance_scores_determine_order(relevance_scores, claim):
    """
    Property 4 (variant): Relevance scores alone determine the output order.
    
    Given a list of results with specific relevance scores, the output
    order should be determined solely by those scores (descending).
    
    **Validates: Requirements 3.3**
    """
    # Create results with the given relevance scores
    results = []
    for i, score in enumerate(relevance_scores):
        results.append(SearchResult(
            title=f"Article {i}",
            source=f"Source {i}",
            summary=f"Summary {i}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            relevance_score=score,
        ))
    
    # Create a mock provider
    mock_provider = MockSearchProviderForTest(results)
    
    # Create the RAG pipeline with high top_k
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=100)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    output_scores = [r.relevance_score for r in evidence_set.results]
    
    # The output scores should be the input scores sorted descending
    expected_scores = sorted(relevance_scores, reverse=True)
    assert output_scores == expected_scores, (
        f"Output scores {output_scores} don't match expected sorted scores {expected_scores}"
    )


@given(
    results=search_result_list_strategy(min_size=5, max_size=20),
    claim=claim_strategy(),
)
@settings(max_examples=100)
def test_top_k_returns_highest_scores(results, claim):
    """
    Property 4 (variant): Top-k returns the k highest relevance scores.
    
    When limiting to top_k results, the returned results should have
    the k highest relevance scores from the input.
    
    **Validates: Requirements 3.3**
    """
    # Ensure we have enough results
    assume(len(results) >= 5)
    
    top_k = 3
    
    # Create a mock provider
    mock_provider = MockSearchProviderForTest(results)
    
    # Create the RAG pipeline
    pipeline = RAGPipeline(search_provider=mock_provider, top_k=top_k)
    
    # Run the async retrieve_evidence method
    async def run_retrieve():
        return await pipeline.retrieve_evidence(claim)
    
    evidence_set = asyncio.run(run_retrieve())
    
    # Get the top-k scores from input
    input_scores = sorted([r.relevance_score for r in results], reverse=True)
    expected_top_k_scores = input_scores[:top_k]
    
    # Get output scores
    output_scores = [r.relevance_score for r in evidence_set.results]
    
    # Output should match expected top-k scores
    assert output_scores == expected_top_k_scores, (
        f"Output scores {output_scores} don't match expected top-k {expected_top_k_scores}"
    )
