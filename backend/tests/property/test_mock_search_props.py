"""
Property-based tests for MockSearchProvider.

This module tests:
- Property 5: Mock provider returns type-varying evidence
- Property 6: SearchResult schema conformance

**Validates: Requirements 3.2, 4.2, 4.3**
"""

import asyncio
from hypothesis import given, strategies as st, settings

from app.models.schemas import Claim
from app.services.mock_search_provider import MockSearchProvider


# Define valid claim types as per the design document
VALID_CLAIM_TYPES = ["banking", "market", "investment", "crypto", "economic"]


# Strategy for generating valid claim types
claim_type_strategy = st.sampled_from(VALID_CLAIM_TYPES)


# Strategy for generating pairs of different claim types
@st.composite
def different_claim_types_strategy(draw):
    """
    Hypothesis composite strategy for generating pairs of different claim types.
    
    Returns a tuple of (type1, type2) where type1 != type2.
    """
    type1 = draw(claim_type_strategy)
    # Filter to get a different type
    type2 = draw(claim_type_strategy.filter(lambda t: t != type1))
    return (type1, type2)


# Strategy for generating query strings
query_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


@given(
    claim_types=different_claim_types_strategy(),
    query=query_strategy,
)
@settings(max_examples=100)
def test_mock_provider_returns_type_varying_evidence(claim_types, query):
    """
    Property 5: Mock provider returns type-varying evidence.
    
    For any two Claims with different `type` values submitted to the Mock Search
    Provider, the returned evidence sets should differ in content (not be identical),
    reflecting type-specific simulated data.
    
    **Validates: Requirements 4.2**
    
    This property ensures:
    1. Different claim types produce different evidence sets
    2. The mock provider generates type-aware synthetic data
    """
    type1, type2 = claim_types
    
    # Use a fixed seed for reproducibility within each test run
    # but the same seed for both calls to ensure the only difference is the type
    provider = MockSearchProvider(seed=42)
    
    # Run async search for both claim types
    async def run_searches():
        results1 = await provider.search(query, type1)
        results2 = await provider.search(query, type2)
        return results1, results2
    
    results1, results2 = asyncio.run(run_searches())
    
    # Extract source names from both result sets
    sources1 = {result.source for result in results1}
    sources2 = {result.source for result in results2}
    
    # The evidence sets should differ in their sources
    # Different claim types should produce different source names
    assert sources1 != sources2, (
        f"Evidence sets for different claim types should have different sources. "
        f"Type '{type1}' sources: {sources1}, Type '{type2}' sources: {sources2}"
    )


@given(
    claim_types=different_claim_types_strategy(),
    query=query_strategy,
)
@settings(max_examples=100)
def test_mock_provider_type_specific_sources(claim_types, query):
    """
    Property 5 (variant): Mock provider returns type-specific sources.
    
    Verifies that the sources returned for each claim type are from the
    type-specific source list defined in the MockSearchProvider.
    
    **Validates: Requirements 4.2**
    """
    type1, type2 = claim_types
    
    # Expected sources for each claim type (from MockSearchProvider._SOURCE_DATA)
    expected_sources = {
        "banking": {
            "Federal Reserve", "FDIC", "Reuters Finance", "Bloomberg Banking",
            "Wall Street Journal", "Financial Times", "American Banker",
        },
        "market": {
            "Bloomberg Markets", "CNBC", "MarketWatch", "Yahoo Finance",
            "Reuters Markets", "The Motley Fool", "Seeking Alpha",
        },
        "investment": {
            "Morningstar", "Vanguard Research", "Fidelity Insights",
            "BlackRock Investment Institute", "J.P. Morgan Asset Management",
            "Goldman Sachs Research", "Barron's",
        },
        "crypto": {
            "CoinDesk", "Cointelegraph", "The Block", "Decrypt",
            "CryptoSlate", "Bitcoin Magazine", "Messari",
        },
        "economic": {
            "Bureau of Economic Analysis", "Bureau of Labor Statistics", "IMF",
            "World Bank", "The Economist", "OECD", "Congressional Budget Office",
        },
    }
    
    provider = MockSearchProvider(seed=42)
    
    async def run_searches():
        results1 = await provider.search(query, type1)
        results2 = await provider.search(query, type2)
        return results1, results2
    
    results1, results2 = asyncio.run(run_searches())
    
    # Verify that sources for type1 are from the expected type1 sources
    sources1 = {result.source for result in results1}
    assert sources1.issubset(expected_sources[type1]), (
        f"Sources for type '{type1}' should be from expected sources. "
        f"Got: {sources1}, Expected subset of: {expected_sources[type1]}"
    )
    
    # Verify that sources for type2 are from the expected type2 sources
    sources2 = {result.source for result in results2}
    assert sources2.issubset(expected_sources[type2]), (
        f"Sources for type '{type2}' should be from expected sources. "
        f"Got: {sources2}, Expected subset of: {expected_sources[type2]}"
    )


@given(
    claim_types=different_claim_types_strategy(),
)
@settings(max_examples=100)
def test_mock_provider_consistent_type_differentiation(claim_types):
    """
    Property 5 (variant): Mock provider consistently differentiates by type.
    
    For the same query, different claim types should consistently produce
    different evidence sets across multiple calls with the same seed.
    
    **Validates: Requirements 4.2**
    """
    type1, type2 = claim_types
    query = "test financial claim about market conditions"
    
    # Use the same seed for reproducibility
    provider = MockSearchProvider(seed=123)
    
    async def run_searches():
        results1 = await provider.search(query, type1)
        results2 = await provider.search(query, type2)
        return results1, results2
    
    results1, results2 = asyncio.run(run_searches())
    
    # Extract all content from both result sets for comparison
    content1 = {(r.source, r.title) for r in results1}
    content2 = {(r.source, r.title) for r in results2}
    
    # The content should differ between different claim types
    # At minimum, the sources should be different
    sources1 = {r.source for r in results1}
    sources2 = {r.source for r in results2}
    
    assert sources1 != sources2, (
        f"Different claim types should produce different sources. "
        f"Type '{type1}': {sources1}, Type '{type2}': {sources2}"
    )


# =============================================================================
# Property 6: SearchResult schema conformance
# =============================================================================


@given(
    claim_type=claim_type_strategy,
    query=query_strategy,
)
@settings(max_examples=100)
def test_search_result_schema_conformance(claim_type, query):
    """
    Property 6: SearchResult schema conformance.
    
    For any SearchResult returned by any Search Provider (mock or live), the result
    must contain non-empty `title`, `source`, `summary`, and `timestamp` fields,
    and a `relevance_score` in the range [0.0, 1.0].
    
    **Validates: Requirements 3.2, 4.3**
    
    This property ensures:
    1. All required fields are present and non-empty
    2. relevance_score is within valid bounds
    3. timestamp is a valid ISO 8601 format string
    """
    provider = MockSearchProvider()
    
    async def run_search():
        return await provider.search(query, claim_type)
    
    results = asyncio.run(run_search())
    
    # Ensure we got at least one result to test
    assert len(results) > 0, (
        f"MockSearchProvider should return at least one result for claim_type='{claim_type}'"
    )
    
    for i, result in enumerate(results):
        # Assert title is non-empty string
        assert isinstance(result.title, str), (
            f"Result {i}: title must be a string, got {type(result.title)}"
        )
        assert len(result.title.strip()) > 0, (
            f"Result {i}: title must be non-empty, got '{result.title}'"
        )
        
        # Assert source is non-empty string
        assert isinstance(result.source, str), (
            f"Result {i}: source must be a string, got {type(result.source)}"
        )
        assert len(result.source.strip()) > 0, (
            f"Result {i}: source must be non-empty, got '{result.source}'"
        )
        
        # Assert summary is non-empty string
        assert isinstance(result.summary, str), (
            f"Result {i}: summary must be a string, got {type(result.summary)}"
        )
        assert len(result.summary.strip()) > 0, (
            f"Result {i}: summary must be non-empty, got '{result.summary}'"
        )
        
        # Assert timestamp is non-empty string
        assert isinstance(result.timestamp, str), (
            f"Result {i}: timestamp must be a string, got {type(result.timestamp)}"
        )
        assert len(result.timestamp.strip()) > 0, (
            f"Result {i}: timestamp must be non-empty, got '{result.timestamp}'"
        )
        
        # Assert relevance_score is in valid range [0.0, 1.0]
        assert isinstance(result.relevance_score, (int, float)), (
            f"Result {i}: relevance_score must be numeric, got {type(result.relevance_score)}"
        )
        assert 0.0 <= result.relevance_score <= 1.0, (
            f"Result {i}: relevance_score must be in [0.0, 1.0], got {result.relevance_score}"
        )


@given(
    claim_type=claim_type_strategy,
    query=query_strategy,
)
@settings(max_examples=100)
def test_search_result_timestamp_is_iso8601(claim_type, query):
    """
    Property 6 (variant): SearchResult timestamp is valid ISO 8601 format.
    
    Verifies that the timestamp field in each SearchResult can be parsed as
    a valid ISO 8601 datetime string.
    
    **Validates: Requirements 3.2, 4.3**
    """
    from datetime import datetime
    
    provider = MockSearchProvider()
    
    async def run_search():
        return await provider.search(query, claim_type)
    
    results = asyncio.run(run_search())
    
    for i, result in enumerate(results):
        # Try to parse the timestamp as ISO 8601
        try:
            # Python's fromisoformat handles ISO 8601 format
            parsed_timestamp = datetime.fromisoformat(result.timestamp.replace('Z', '+00:00'))
            assert parsed_timestamp is not None, (
                f"Result {i}: timestamp should parse to a valid datetime"
            )
        except ValueError as e:
            raise AssertionError(
                f"Result {i}: timestamp '{result.timestamp}' is not valid ISO 8601 format: {e}"
            )


@given(
    claim_type=claim_type_strategy,
)
@settings(max_examples=100)
def test_search_result_relevance_score_bounds(claim_type):
    """
    Property 6 (variant): SearchResult relevance_score is strictly bounded.
    
    Verifies that relevance_score is always within [0.0, 1.0] inclusive,
    regardless of the query or claim type.
    
    **Validates: Requirements 3.2, 4.3**
    """
    # Use a variety of query types to stress test the relevance score generation
    test_queries = [
        "simple query",
        "a" * 200,  # Long query
        "123 456 789",  # Numeric query
        "!@#$%^&*()",  # Special characters
        "mixed Query 123 !@#",  # Mixed content
    ]
    
    provider = MockSearchProvider()
    
    async def run_searches():
        all_results = []
        for query in test_queries:
            results = await provider.search(query, claim_type)
            all_results.extend(results)
        return all_results
    
    all_results = asyncio.run(run_searches())
    
    for i, result in enumerate(all_results):
        assert 0.0 <= result.relevance_score <= 1.0, (
            f"Result {i}: relevance_score {result.relevance_score} is outside [0.0, 1.0]"
        )


@given(
    claim_type=claim_type_strategy,
    query=query_strategy,
    seed=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100)
def test_search_result_schema_with_random_seeds(claim_type, query, seed):
    """
    Property 6 (variant): SearchResult schema conformance with random seeds.
    
    Verifies that schema conformance holds regardless of the random seed
    used to initialize the MockSearchProvider.
    
    **Validates: Requirements 3.2, 4.3**
    """
    provider = MockSearchProvider(seed=seed)
    
    async def run_search():
        return await provider.search(query, claim_type)
    
    results = asyncio.run(run_search())
    
    # Ensure we got results
    assert len(results) > 0, (
        f"MockSearchProvider(seed={seed}) should return results"
    )
    
    for i, result in enumerate(results):
        # All required fields must be non-empty
        assert result.title and result.title.strip(), (
            f"Result {i} (seed={seed}): title must be non-empty"
        )
        assert result.source and result.source.strip(), (
            f"Result {i} (seed={seed}): source must be non-empty"
        )
        assert result.summary and result.summary.strip(), (
            f"Result {i} (seed={seed}): summary must be non-empty"
        )
        assert result.timestamp and result.timestamp.strip(), (
            f"Result {i} (seed={seed}): timestamp must be non-empty"
        )
        
        # relevance_score must be in valid range
        assert 0.0 <= result.relevance_score <= 1.0, (
            f"Result {i} (seed={seed}): relevance_score {result.relevance_score} out of bounds"
        )
