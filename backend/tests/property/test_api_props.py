"""
Property-based tests for API response structure.

This module tests:
- Property 12: API response structure completeness
- Property 13: DeductionReference integrity

**Validates: Requirements 8.2, 28.1, 28.2, 28.3**
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings

from app.main import app
from app.api.routes import configure_analyzer
from app.models.schemas import (
    AnalysisResponse,
    Claim,
    ClaimAnalysis,
    ClassificationLabel,
    ClassificationResult,
    DeductionReference,
    EvidenceSet,
    NoCorroborationDeduction,
    SearchResult,
    TrustScoreBreakdown,
)
from app.services.analyzer import Analyzer
from app.services.claim_extractor import ClaimExtractor
from app.services.classifier import Classifier
from app.services.explanation_engine import ExplanationEngine
from app.services.mock_search_provider import MockSearchProvider
from app.services.rag_pipeline import RAGPipeline
from app.services.trust_score_engine import TrustScoreEngine


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for generating valid text strings for analysis
# - Non-empty (at least 1 character after stripping)
# - Within length limits (max 50,000 characters)
# - Contains at least some non-whitespace content
valid_text_strategy = st.text(
    min_size=1,
    max_size=1000,  # Keep reasonable for testing performance
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),  # Letters, numbers, punctuation, symbols, separators
        blacklist_characters="\x00",  # Exclude null characters
    ),
).filter(lambda s: s.strip())  # Ensure non-whitespace content exists


# Strategy for generating financial-like text that might contain claims
financial_text_strategy = st.one_of(
    # Simple financial statements
    st.builds(
        lambda company, percent, direction: f"{company} stock {direction} by {percent}% today.",
        company=st.sampled_from(["Apple", "Google", "Microsoft", "Tesla", "Amazon"]),
        percent=st.integers(min_value=1, max_value=50),
        direction=st.sampled_from(["rose", "fell", "increased", "decreased"]),
    ),
    # Crypto statements
    st.builds(
        lambda crypto, price: f"{crypto} reached ${price} this week.",
        crypto=st.sampled_from(["Bitcoin", "Ethereum", "Dogecoin"]),
        price=st.integers(min_value=100, max_value=100000),
    ),
    # General financial text
    st.builds(
        lambda text: f"Financial news: {text}",
        text=valid_text_strategy,
    ),
)


# ============================================================================
# Test Fixtures
# ============================================================================

def create_mock_analyzer() -> Analyzer:
    """Create a mock Analyzer with mocked LLM-dependent services.
    
    This creates an Analyzer where:
    - ClaimExtractor returns mock claims
    - Classifier returns mock classifications
    - ExplanationEngine returns mock explanations
    - RAGPipeline uses MockSearchProvider (real implementation)
    - TrustScoreEngine uses real implementation
    """
    # Create mock LLM client
    mock_llm_client = MagicMock()
    
    # Create mock claim extractor that returns a sample claim
    mock_claim_extractor = MagicMock(spec=ClaimExtractor)
    
    async def mock_extract_claims(text: str):
        """Return a mock claim for any non-empty text."""
        claim_id = str(uuid.uuid4())
        # Create a simple claim from the first 50 chars of text
        claim_text = text[:min(50, len(text))]
        return [
            Claim(
                id=claim_id,
                text=claim_text,
                start_index=0,
                end_index=min(50, len(text)),
                type="market",
                entities=["test_entity"],
            )
        ]
    
    mock_claim_extractor.extract_claims = AsyncMock(side_effect=mock_extract_claims)
    
    # Create mock classifier
    mock_classifier = MagicMock(spec=Classifier)
    
    async def mock_classify(claim: Claim, evidence: EvidenceSet):
        """Return a mock classification for any claim."""
        return ClassificationResult(
            claim_id=claim.id,
            label=ClassificationLabel.VERIFIED,
            reasoning="Mock classification for testing purposes.",
        )
    
    mock_classifier.classify = AsyncMock(side_effect=mock_classify)
    
    # Create mock explanation engine
    mock_explanation_engine = MagicMock(spec=ExplanationEngine)
    
    async def mock_generate_explanation(claim, classification, trust_score, trust_score_breakdown, evidence):
        """Return a mock explanation."""
        return (
            "This is a mock explanation for testing purposes. "
            "The analysis indicates the content appears to be generally reliable."
        )
    
    mock_explanation_engine.generate_explanation = AsyncMock(side_effect=mock_generate_explanation)
    
    # Use real MockSearchProvider and RAGPipeline
    search_provider = MockSearchProvider()
    rag_pipeline = RAGPipeline(search_provider=search_provider, top_k=5)
    
    # Use real TrustScoreEngine
    trust_score_engine = TrustScoreEngine()
    
    # Create the Analyzer with mocked LLM services
    analyzer = Analyzer(
        claim_extractor=mock_claim_extractor,
        rag_pipeline=rag_pipeline,
        classifier=mock_classifier,
        trust_score_engine=trust_score_engine,
        explanation_engine=mock_explanation_engine,
    )
    
    return analyzer


@pytest.fixture
def test_client():
    """Create a test client with mocked analyzer."""
    # Configure the analyzer with mocks
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    client = TestClient(app)
    return client


# ============================================================================
# Property 12: API response structure completeness
# ============================================================================

@given(text=valid_text_strategy)
@settings(deadline=None, max_examples=100)
def test_api_response_structure_completeness(text: str):
    """
    Property 12: API response structure completeness.
    
    For any valid text input submitted to POST /analyze, the JSON response
    must contain the fields: `claims` (array), `overall_classification`,
    `trust_score`, `explanation` (string), `sources` (array), and
    `disclaimer` (string).
    
    **Validates: Requirements 8.2**
    
    This property ensures:
    1. The API always returns a complete response structure
    2. All required fields are present regardless of input content
    3. Field types are correct (arrays, strings, integers/null)
    """
    # Configure the analyzer with mocks for each test iteration
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        # Should return 200 OK for valid text
        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        # Parse response JSON
        data = response.json()
        
        # Assert all required fields are present
        assert "claims" in data, "Response must contain 'claims' field"
        assert "overall_classification" in data, "Response must contain 'overall_classification' field"
        assert "trust_score" in data, "Response must contain 'trust_score' field"
        assert "explanation" in data, "Response must contain 'explanation' field"
        assert "sources" in data, "Response must contain 'sources' field"
        assert "disclaimer" in data, "Response must contain 'disclaimer' field"
        
        # Assert field types
        assert isinstance(data["claims"], list), "'claims' must be a list"
        assert isinstance(data["sources"], list), "'sources' must be a list"
        assert isinstance(data["explanation"], str), "'explanation' must be a string"
        assert isinstance(data["disclaimer"], str), "'disclaimer' must be a string"
        
        # trust_score can be int or None
        assert data["trust_score"] is None or isinstance(data["trust_score"], int), \
            "'trust_score' must be an integer or null"
        
        # overall_classification can be string or None
        assert data["overall_classification"] is None or isinstance(data["overall_classification"], str), \
            "'overall_classification' must be a string or null"
        
        # If trust_score is present, it should be in valid range
        if data["trust_score"] is not None:
            assert 0 <= data["trust_score"] <= 100, \
                f"'trust_score' must be between 0 and 100, got {data['trust_score']}"
        
        # If overall_classification is present, it should be a valid label
        valid_labels = {"VERIFIED", "MISLEADING", "LIKELY_FALSE", "HARMFUL"}
        if data["overall_classification"] is not None:
            assert data["overall_classification"] in valid_labels, \
                f"'overall_classification' must be one of {valid_labels}, got {data['overall_classification']}"
        
        # Disclaimer should be non-empty
        assert len(data["disclaimer"]) > 0, "'disclaimer' must be non-empty"


@given(text=financial_text_strategy)
@settings(deadline=None, max_examples=100)
def test_api_response_structure_with_financial_text(text: str):
    """
    Property 12 (variant): API response structure with financial-like text.
    
    Tests the same property with text that is more likely to contain
    financial claims, ensuring the response structure is complete
    even when claims are extracted.
    
    **Validates: Requirements 8.2**
    """
    # Configure the analyzer with mocks for each test iteration
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        # Should return 200 OK for valid text
        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        # Parse response JSON
        data = response.json()
        
        # Assert all required fields are present
        required_fields = [
            "claims",
            "overall_classification",
            "trust_score",
            "explanation",
            "sources",
            "disclaimer",
        ]
        
        for field in required_fields:
            assert field in data, f"Response must contain '{field}' field"
        
        # When claims are found, verify claim structure
        if data["claims"]:
            for claim_analysis in data["claims"]:
                assert "claim" in claim_analysis, "ClaimAnalysis must contain 'claim'"
                assert "classification" in claim_analysis, "ClaimAnalysis must contain 'classification'"
                assert "evidence" in claim_analysis, "ClaimAnalysis must contain 'evidence'"
                assert "deduction_references" in claim_analysis, "ClaimAnalysis must contain 'deduction_references'"
                
                # Verify claim structure
                claim = claim_analysis["claim"]
                assert "id" in claim, "Claim must contain 'id'"
                assert "text" in claim, "Claim must contain 'text'"
                assert "start_index" in claim, "Claim must contain 'start_index'"
                assert "end_index" in claim, "Claim must contain 'end_index'"
                assert "type" in claim, "Claim must contain 'type'"
                assert "entities" in claim, "Claim must contain 'entities'"
                
                # Verify classification structure
                classification = claim_analysis["classification"]
                assert "claim_id" in classification, "Classification must contain 'claim_id'"
                assert "label" in classification, "Classification must contain 'label'"
                assert "reasoning" in classification, "Classification must contain 'reasoning'"
                
                # Verify evidence structure
                evidence = claim_analysis["evidence"]
                assert "results" in evidence, "Evidence must contain 'results'"
                assert "insufficient_evidence" in evidence, "Evidence must contain 'insufficient_evidence'"


@given(text=valid_text_strategy)
@settings(deadline=None, max_examples=50)
def test_api_response_trust_score_breakdown_structure(text: str):
    """
    Property: API response trust_score_breakdown structure.
    
    When trust_score is present, trust_score_breakdown should also be present
    with all four sub-scores.
    
    **Validates: Requirements 6.7, 8.2**
    """
    # Configure the analyzer with mocks for each test iteration
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If trust_score is present, trust_score_breakdown should also be present
        if data["trust_score"] is not None:
            assert "trust_score_breakdown" in data, \
                "Response must contain 'trust_score_breakdown' when trust_score is present"
            
            breakdown = data["trust_score_breakdown"]
            assert breakdown is not None, \
                "'trust_score_breakdown' must not be null when trust_score is present"
            
            # Verify all four sub-scores are present
            required_subscores = [
                "source_credibility",
                "evidence_strength",
                "language_neutrality",
                "cross_source_agreement",
            ]
            
            for subscore in required_subscores:
                assert subscore in breakdown, \
                    f"'trust_score_breakdown' must contain '{subscore}'"
                assert isinstance(breakdown[subscore], int), \
                    f"'{subscore}' must be an integer"
                assert 0 <= breakdown[subscore] <= 100, \
                    f"'{subscore}' must be between 0 and 100"


@given(text=valid_text_strategy)
@settings(deadline=None, max_examples=50)
def test_api_response_sources_structure(text: str):
    """
    Property: API response sources structure.
    
    Each source in the sources array should have the required SearchResult fields.
    
    **Validates: Requirements 3.2, 8.2**
    """
    # Configure the analyzer with mocks for each test iteration
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify sources structure
        sources = data["sources"]
        assert isinstance(sources, list), "'sources' must be a list"
        
        for source in sources:
            # Verify required SearchResult fields
            assert "title" in source, "Source must contain 'title'"
            assert "source" in source, "Source must contain 'source'"
            assert "summary" in source, "Source must contain 'summary'"
            assert "timestamp" in source, "Source must contain 'timestamp'"
            assert "relevance_score" in source, "Source must contain 'relevance_score'"
            
            # Verify field types
            assert isinstance(source["title"], str), "'title' must be a string"
            assert isinstance(source["source"], str), "'source' must be a string"
            assert isinstance(source["summary"], str), "'summary' must be a string"
            assert isinstance(source["timestamp"], str), "'timestamp' must be a string"
            assert isinstance(source["relevance_score"], (int, float)), \
                "'relevance_score' must be a number"
            
            # Verify relevance_score range
            assert 0.0 <= source["relevance_score"] <= 1.0, \
                f"'relevance_score' must be between 0.0 and 1.0, got {source['relevance_score']}"


# ============================================================================
# Property 13: DeductionReference integrity
# ============================================================================

def create_mock_analyzer_with_deductions() -> Analyzer:
    """Create a mock Analyzer that produces claims with DeductionReferences.
    
    This creates an Analyzer where:
    - ClaimExtractor returns mock claims
    - Classifier returns MISLEADING/LIKELY_FALSE classifications (to trigger deductions)
    - ExplanationEngine returns mock explanations
    - RAGPipeline uses MockSearchProvider with contradicting evidence
    - TrustScoreEngine uses real implementation (produces DeductionReferences)
    """
    # Create mock LLM client
    mock_llm_client = MagicMock()
    
    # Create mock claim extractor that returns a sample claim
    mock_claim_extractor = MagicMock(spec=ClaimExtractor)
    
    async def mock_extract_claims(text: str):
        """Return a mock claim for any non-empty text."""
        claim_id = str(uuid.uuid4())
        # Create a simple claim from the first 50 chars of text
        claim_text = text[:min(50, len(text))]
        return [
            Claim(
                id=claim_id,
                text=claim_text,
                start_index=0,
                end_index=min(50, len(text)),
                type="market",
                entities=["test_entity"],
            )
        ]
    
    mock_claim_extractor.extract_claims = AsyncMock(side_effect=mock_extract_claims)
    
    # Create mock classifier that returns MISLEADING to trigger deductions
    mock_classifier = MagicMock(spec=Classifier)
    
    async def mock_classify(claim: Claim, evidence: EvidenceSet):
        """Return a MISLEADING classification to trigger deduction references."""
        return ClassificationResult(
            claim_id=claim.id,
            label=ClassificationLabel.MISLEADING,
            reasoning="Mock classification indicating misleading content for testing deductions.",
        )
    
    mock_classifier.classify = AsyncMock(side_effect=mock_classify)
    
    # Create mock explanation engine
    mock_explanation_engine = MagicMock(spec=ExplanationEngine)
    
    async def mock_generate_explanation(claim, classification, trust_score, trust_score_breakdown, evidence):
        """Return a mock explanation."""
        return (
            "This is a mock explanation for testing purposes. "
            "The analysis indicates the content may be misleading."
        )
    
    mock_explanation_engine.generate_explanation = AsyncMock(side_effect=mock_generate_explanation)
    
    # Use real MockSearchProvider and RAGPipeline
    # MockSearchProvider returns evidence with contradiction keywords
    search_provider = MockSearchProvider()
    rag_pipeline = RAGPipeline(search_provider=search_provider, top_k=5)
    
    # Use real TrustScoreEngine (this produces DeductionReferences)
    trust_score_engine = TrustScoreEngine()
    
    # Create the Analyzer with mocked LLM services
    analyzer = Analyzer(
        claim_extractor=mock_claim_extractor,
        rag_pipeline=rag_pipeline,
        classifier=mock_classifier,
        trust_score_engine=trust_score_engine,
        explanation_engine=mock_explanation_engine,
    )
    
    return analyzer


# Strategy for generating text that is likely to produce claims with deductions
# These texts contain financial claims that might be flagged as misleading
deduction_triggering_text_strategy = st.one_of(
    # Misleading financial statements
    st.builds(
        lambda company, percent: f"{company} stock is guaranteed to rise by {percent}% - this is a sure thing!",
        company=st.sampled_from(["Apple", "Google", "Microsoft", "Tesla", "Amazon"]),
        percent=st.integers(min_value=50, max_value=500),
    ),
    # Crypto hype statements
    st.builds(
        lambda crypto, multiplier: f"{crypto} will definitely 100x your money - don't miss out on this opportunity!",
        crypto=st.sampled_from(["Bitcoin", "Ethereum", "Dogecoin", "Solana"]),
        multiplier=st.integers(min_value=10, max_value=1000),
    ),
    # Market manipulation claims
    st.builds(
        lambda action, asset: f"URGENT: You must {action} {asset} immediately before it's too late!",
        action=st.sampled_from(["buy", "sell", "invest in"]),
        asset=st.sampled_from(["gold", "silver", "tech stocks", "crypto"]),
    ),
    # General financial text with emotional language
    st.builds(
        lambda text: f"Financial alert: {text} - act now or miss out forever!",
        text=valid_text_strategy,
    ),
)


@given(text=deduction_triggering_text_strategy)
@settings(deadline=None, max_examples=100)
def test_deduction_reference_integrity(text: str):
    """
    Property 13: DeductionReference integrity.
    
    For any DeductionReference in an AnalysisResponse, it must contain non-empty
    `source_name`, `url`, `summary`, and `contradiction_rationale` fields, and its
    `claim_id` must match the `id` of an existing Claim in the same response.
    
    **Validates: Requirements 28.1, 28.2, 28.3**
    
    This property ensures:
    1. All DeductionReference fields are non-empty strings
    2. Each DeductionReference's claim_id references a valid claim in the response
    3. The structure is consistent regardless of input content
    """
    # Configure the analyzer with mocks that produce deductions
    mock_analyzer = create_mock_analyzer_with_deductions()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        # Should return 200 OK for valid text
        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        # Parse response JSON
        data = response.json()
        
        # Collect all claim IDs from the response
        claim_ids = set()
        for claim_analysis in data.get("claims", []):
            claim = claim_analysis.get("claim", {})
            if "id" in claim:
                claim_ids.add(claim["id"])
        
        # Verify DeductionReference integrity for each claim
        for claim_analysis in data.get("claims", []):
            deduction_references = claim_analysis.get("deduction_references", [])
            
            for deduction in deduction_references:
                # Check if this is a DeductionReference (has source_name) or NoCorroborationDeduction (has rationale only)
                if "source_name" in deduction:
                    # This is a DeductionReference - verify all required fields
                    
                    # Requirement 28.1: source_name must be non-empty
                    assert "source_name" in deduction, \
                        "DeductionReference must contain 'source_name' field"
                    assert isinstance(deduction["source_name"], str), \
                        "'source_name' must be a string"
                    assert len(deduction["source_name"].strip()) > 0, \
                        "'source_name' must be non-empty (Req 28.1)"
                    
                    # Requirement 28.2: url must be non-empty
                    assert "url" in deduction, \
                        "DeductionReference must contain 'url' field"
                    assert isinstance(deduction["url"], str), \
                        "'url' must be a string"
                    assert len(deduction["url"].strip()) > 0, \
                        "'url' must be non-empty (Req 28.2)"
                    
                    # Requirement 28.3: summary must be non-empty
                    assert "summary" in deduction, \
                        "DeductionReference must contain 'summary' field"
                    assert isinstance(deduction["summary"], str), \
                        "'summary' must be a string"
                    assert len(deduction["summary"].strip()) > 0, \
                        "'summary' must be non-empty (Req 28.3)"
                    
                    # Requirement 28.3: contradiction_rationale must be non-empty
                    assert "contradiction_rationale" in deduction, \
                        "DeductionReference must contain 'contradiction_rationale' field"
                    assert isinstance(deduction["contradiction_rationale"], str), \
                        "'contradiction_rationale' must be a string"
                    assert len(deduction["contradiction_rationale"].strip()) > 0, \
                        "'contradiction_rationale' must be non-empty (Req 28.3)"
                    
                    # claim_id must match an existing Claim
                    assert "claim_id" in deduction, \
                        "DeductionReference must contain 'claim_id' field"
                    assert deduction["claim_id"] in claim_ids, (
                        f"DeductionReference claim_id '{deduction['claim_id']}' "
                        f"must match an existing Claim id. Valid claim_ids: {claim_ids}"
                    )
                
                elif "rationale" in deduction:
                    # This is a NoCorroborationDeduction - verify its structure
                    assert "claim_id" in deduction, \
                        "NoCorroborationDeduction must contain 'claim_id' field"
                    assert deduction["claim_id"] in claim_ids, (
                        f"NoCorroborationDeduction claim_id '{deduction['claim_id']}' "
                        f"must match an existing Claim id. Valid claim_ids: {claim_ids}"
                    )
                    assert isinstance(deduction["rationale"], str), \
                        "'rationale' must be a string"
                    assert len(deduction["rationale"].strip()) > 0, \
                        "'rationale' must be non-empty"


@given(text=financial_text_strategy)
@settings(deadline=None, max_examples=100)
def test_deduction_reference_integrity_with_financial_text(text: str):
    """
    Property 13 (variant): DeductionReference integrity with financial text.
    
    Tests the same property with text that is more likely to contain
    financial claims, ensuring DeductionReference integrity holds
    for various types of financial content.
    
    **Validates: Requirements 28.1, 28.2, 28.3**
    """
    # Configure the analyzer with mocks that produce deductions
    mock_analyzer = create_mock_analyzer_with_deductions()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        # Should return 200 OK for valid text
        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.text}"
        )
        
        # Parse response JSON
        data = response.json()
        
        # Collect all claim IDs from the response
        claim_ids = set()
        for claim_analysis in data.get("claims", []):
            claim = claim_analysis.get("claim", {})
            if "id" in claim:
                claim_ids.add(claim["id"])
        
        # Verify DeductionReference integrity for each claim
        for claim_analysis in data.get("claims", []):
            deduction_references = claim_analysis.get("deduction_references", [])
            
            for deduction in deduction_references:
                # Check if this is a DeductionReference (has source_name)
                if "source_name" in deduction:
                    # Verify all required fields are present and non-empty
                    required_fields = ["source_name", "url", "summary", "contradiction_rationale", "claim_id"]
                    
                    for field in required_fields:
                        assert field in deduction, \
                            f"DeductionReference must contain '{field}' field"
                        
                        if field != "claim_id":
                            assert isinstance(deduction[field], str), \
                                f"'{field}' must be a string"
                            assert len(deduction[field].strip()) > 0, \
                                f"'{field}' must be non-empty"
                    
                    # Verify claim_id references an existing claim
                    assert deduction["claim_id"] in claim_ids, (
                        f"DeductionReference claim_id '{deduction['claim_id']}' "
                        f"must match an existing Claim id"
                    )
                
                elif "rationale" in deduction:
                    # NoCorroborationDeduction - verify claim_id reference
                    assert "claim_id" in deduction, \
                        "NoCorroborationDeduction must contain 'claim_id' field"
                    assert deduction["claim_id"] in claim_ids, (
                        f"NoCorroborationDeduction claim_id '{deduction['claim_id']}' "
                        f"must match an existing Claim id"
                    )


@given(text=valid_text_strategy)
@settings(deadline=None, max_examples=50)
def test_deduction_reference_claim_id_consistency(text: str):
    """
    Property 13 (claim_id consistency): Every deduction's claim_id must reference
    a claim that exists in the same response.
    
    This test specifically focuses on the claim_id referential integrity aspect
    of Property 13.
    
    **Validates: Requirements 28.1, 28.2, 28.3**
    """
    # Configure the analyzer with mocks
    mock_analyzer = create_mock_analyzer_with_deductions()
    configure_analyzer(mock_analyzer)
    
    # Create test client
    with TestClient(app) as client:
        # Submit the text for analysis
        response = client.post(
            "/analyze",
            json={"text": text},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Build a set of all valid claim IDs
        valid_claim_ids = set()
        for claim_analysis in data.get("claims", []):
            claim = claim_analysis.get("claim", {})
            if "id" in claim:
                valid_claim_ids.add(claim["id"])
        
        # Verify every deduction references a valid claim
        for claim_analysis in data.get("claims", []):
            for deduction in claim_analysis.get("deduction_references", []):
                if "claim_id" in deduction:
                    assert deduction["claim_id"] in valid_claim_ids, (
                        f"Deduction claim_id '{deduction['claim_id']}' is not in the set of "
                        f"valid claim IDs: {valid_claim_ids}. This violates referential integrity."
                    )
