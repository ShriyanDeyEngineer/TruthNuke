"""Unit tests for API error handling.

Tests cover error scenarios for the POST /analyze endpoint (Task 13.3).

Requirements: 8.3, 8.4, 12.1, 12.3, 27.4
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router, configure_analyzer, get_analyzer
from app.models.schemas import (
    AnalysisResponse,
    Claim,
    ClaimAnalysis,
    ClassificationLabel,
    ClassificationResult,
    ContentModality,
    EvidenceSet,
    TrustScoreBreakdown,
)
from app.services.analyzer import Analyzer, ValidationError
from app.services.claim_extractor import ClaimExtractor
from app.services.classifier import Classifier
from app.services.explanation_engine import ExplanationEngine
from app.services.llm_client import LLMUnavailableError
from app.services.mock_search_provider import MockSearchProvider
from app.services.rag_pipeline import RAGPipeline
from app.services.trust_score_engine import TrustScoreEngine


def create_test_app() -> FastAPI:
    """Create a test FastAPI app without the lifespan handler."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


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
    # Create mock claim extractor that returns a sample claim
    mock_claim_extractor = MagicMock(spec=ClaimExtractor)
    
    async def mock_extract_claims(text: str):
        """Return a mock claim for any non-empty text."""
        claim_id = str(uuid.uuid4())
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


def create_no_claims_analyzer() -> Analyzer:
    """Create an Analyzer that returns no claims (for testing no-claims scenario)."""
    # Create mock claim extractor that returns empty list
    mock_claim_extractor = MagicMock(spec=ClaimExtractor)
    mock_claim_extractor.extract_claims = AsyncMock(return_value=[])
    
    # Create mock classifier (won't be called if no claims)
    mock_classifier = MagicMock(spec=Classifier)
    
    # Create mock explanation engine (won't be called if no claims)
    mock_explanation_engine = MagicMock(spec=ExplanationEngine)
    
    # Use real MockSearchProvider and RAGPipeline
    search_provider = MockSearchProvider()
    rag_pipeline = RAGPipeline(search_provider=search_provider, top_k=5)
    
    # Use real TrustScoreEngine
    trust_score_engine = TrustScoreEngine()
    
    # Create the Analyzer
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
    test_app = create_test_app()
    mock_analyzer = create_mock_analyzer()
    configure_analyzer(mock_analyzer)
    client = TestClient(test_app)
    return client


@pytest.fixture
def no_claims_client():
    """Create a test client with analyzer that returns no claims."""
    test_app = create_test_app()
    mock_analyzer = create_no_claims_analyzer()
    configure_analyzer(mock_analyzer)
    client = TestClient(test_app)
    return client


# ============================================================================
# Test: Missing text field → 422 (Pydantic validation)
# ============================================================================

class TestMissingTextField:
    """Tests for missing text field in request body.
    
    Note: FastAPI/Pydantic returns 422 for missing required fields.
    Requirements: 8.3
    """
    
    def test_missing_text_field_returns_422(self, test_client):
        """Request without 'text' field should return 422 (Pydantic validation)."""
        response = test_client.post(
            "/analyze",
            json={},  # No text field
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_missing_text_field_with_other_fields_returns_422(self, test_client):
        """Request with other fields but no 'text' should return 422."""
        response = test_client.post(
            "/analyze",
            json={"content_type": "TEXT"},  # Has content_type but no text
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_null_text_field_returns_422(self, test_client):
        """Request with null 'text' field should return 422."""
        response = test_client.post(
            "/analyze",
            json={"text": None},
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


# ============================================================================
# Test: Empty text → 422 (Pydantic min_length validation)
# ============================================================================

class TestEmptyText:
    """Tests for empty text in request body.
    
    Note: Empty string fails Pydantic min_length=1 validation (422).
    Whitespace-only text passes Pydantic but fails Analyzer validation (400).
    Requirements: 8.3
    """
    
    def test_empty_string_returns_422(self, test_client):
        """Empty string text should return 422 (Pydantic min_length validation)."""
        response = test_client.post(
            "/analyze",
            json={"text": ""},
        )
        
        # Pydantic min_length=1 validation returns 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_whitespace_only_spaces_returns_400(self, test_client):
        """Whitespace-only text (spaces) should return 400 (Req 8.3)."""
        response = test_client.post(
            "/analyze",
            json={"text": "     "},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_whitespace_only_tabs_returns_400(self, test_client):
        """Whitespace-only text (tabs) should return 400 (Req 8.3)."""
        response = test_client.post(
            "/analyze",
            json={"text": "\t\t\t"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_whitespace_only_newlines_returns_400(self, test_client):
        """Whitespace-only text (newlines) should return 400 (Req 8.3)."""
        response = test_client.post(
            "/analyze",
            json={"text": "\n\n\n"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_whitespace_only_mixed_returns_400(self, test_client):
        """Whitespace-only text (mixed) should return 400 (Req 8.3)."""
        response = test_client.post(
            "/analyze",
            json={"text": "  \t\n  \r\n  "},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


# ============================================================================
# Test: Text > 50,000 chars → 422 (Pydantic max_length validation)
# ============================================================================

class TestTextExceedsMaxLength:
    """Tests for text exceeding maximum length.
    
    Note: Pydantic max_length=50000 validation returns 422.
    Requirements: 8.3
    """
    
    def test_text_exceeding_50000_chars_returns_422(self, test_client):
        """Text exceeding 50,000 characters should return 422 (Pydantic validation)."""
        long_text = "a" * 50001
        
        response = test_client.post(
            "/analyze",
            json={"text": long_text},
        )
        
        # Pydantic max_length validation returns 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_text_at_exactly_50000_chars_returns_200(self, test_client):
        """Text at exactly 50,000 characters should return 200."""
        max_text = "a" * 50000
        
        response = test_client.post(
            "/analyze",
            json={"text": max_text},
        )
        
        assert response.status_code == 200
    
    def test_very_long_text_returns_422(self, test_client):
        """Very long text (100,000 chars) should return 422 (Pydantic validation)."""
        very_long_text = "x" * 100000
        
        response = test_client.post(
            "/analyze",
            json={"text": very_long_text},
        )
        
        # Pydantic max_length validation returns 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


# ============================================================================
# Test: Invalid content_type → 400
# ============================================================================

class TestInvalidContentType:
    """Tests for invalid content_type in request body.
    
    Requirements: 27.4
    """
    
    def test_unsupported_content_type_video_returns_400(self, test_client):
        """Unsupported content_type VIDEO should return 400 (Req 27.4)."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "VIDEO"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Should mention unsupported content type
        detail = data["detail"]
        assert "error" in detail
        assert detail["error"] == "validation_error"
        assert "Unsupported content type" in detail["detail"]
    
    def test_unsupported_content_type_article_returns_400(self, test_client):
        """Unsupported content_type ARTICLE should return 400 (Req 27.4)."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "ARTICLE"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "validation_error"
    
    def test_unsupported_content_type_social_post_returns_400(self, test_client):
        """Unsupported content_type SOCIAL_POST should return 400 (Req 27.4)."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "SOCIAL_POST"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "validation_error"
    
    def test_unsupported_content_type_image_returns_400(self, test_client):
        """Unsupported content_type IMAGE should return 400 (Req 27.4)."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "IMAGE"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "validation_error"
    
    def test_invalid_content_type_value_returns_422(self, test_client):
        """Invalid content_type value should return 422 (Pydantic validation)."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "INVALID_TYPE"},
        )
        
        # Pydantic returns 422 for invalid enum values
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_valid_content_type_text_returns_200(self, test_client):
        """Valid content_type TEXT should return 200."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content", "content_type": "TEXT"},
        )
        
        assert response.status_code == 200
    
    def test_default_content_type_returns_200(self, test_client):
        """Omitted content_type should default to TEXT and return 200."""
        response = test_client.post(
            "/analyze",
            json={"text": "Valid text content"},
        )
        
        assert response.status_code == 200


# ============================================================================
# Test: LLM unavailable → 503
# ============================================================================

class TestLLMUnavailable:
    """Tests for LLM service unavailability.
    
    Requirements: 12.3
    """
    
    def test_llm_unavailable_returns_503(self):
        """LLM unavailability should return 503 (Req 12.3)."""
        # Create a test app
        test_app = create_test_app()
        
        # Create an analyzer that raises LLMUnavailableError
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=LLMUnavailableError("LLM service unavailable")
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            detail = data["detail"]
            assert detail["error"] == "service_unavailable"
            # Should not expose internal error details
            assert "temporarily unavailable" in detail["detail"].lower()
    
    def test_llm_unavailable_error_message_is_user_friendly(self):
        """LLM unavailability error message should be user-friendly (Req 12.3)."""
        # Create a test app
        test_app = create_test_app()
        
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=LLMUnavailableError("Connection timeout after 3 retries")
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 503
            data = response.json()
            detail = data["detail"]
            # Should not expose internal details like "Connection timeout"
            assert "Connection timeout" not in detail["detail"]
            assert "retry" not in detail["detail"].lower() or "try again" in detail["detail"].lower()


# ============================================================================
# Test: Internal error → 500 with no internal details
# ============================================================================

class TestInternalError:
    """Tests for internal server errors.
    
    Requirements: 8.4
    """
    
    def test_internal_error_returns_500(self):
        """Internal error should return 500 (Req 8.4)."""
        # Create a test app
        test_app = create_test_app()
        
        # Create an analyzer that raises an unexpected exception
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=RuntimeError("Database connection failed: host=db.internal.com, port=5432")
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            detail = data["detail"]
            assert detail["error"] == "internal_error"
    
    def test_internal_error_does_not_expose_details(self):
        """Internal error should not expose internal system details (Req 8.4)."""
        # Create a test app
        test_app = create_test_app()
        
        # Create an analyzer that raises an exception with sensitive info
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=Exception(
                "Failed to connect to database at postgres://user:password@db.internal.com:5432/truthnuke"
            )
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 500
            data = response.json()
            detail = data["detail"]
            
            # Should not expose internal details
            assert "postgres" not in detail["detail"].lower()
            assert "password" not in detail["detail"].lower()
            assert "database" not in detail["detail"].lower()
            assert "db.internal.com" not in detail["detail"]
            assert "5432" not in detail["detail"]
            
            # Should have a generic error message
            assert "unexpected error" in detail["detail"].lower()
    
    def test_internal_error_with_stack_trace_does_not_expose_trace(self):
        """Internal error should not expose stack traces (Req 8.4)."""
        # Create a test app
        test_app = create_test_app()
        
        # Create an analyzer that raises an exception
        mock_analyzer = MagicMock(spec=Analyzer)
        
        def raise_with_traceback():
            raise ValueError("Internal processing error in module X at line 42")
        
        mock_analyzer.analyze = AsyncMock(side_effect=raise_with_traceback)
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 500
            data = response.json()
            detail = data["detail"]
            
            # Should not expose internal details
            assert "module X" not in detail["detail"]
            assert "line 42" not in detail["detail"]
            assert "ValueError" not in detail["detail"]
    
    def test_various_exception_types_return_500(self):
        """Various exception types should all return 500 (Req 8.4)."""
        exception_types = [
            RuntimeError("Runtime error"),
            ValueError("Value error"),
            TypeError("Type error"),
            KeyError("key_error"),
            AttributeError("Attribute error"),
        ]
        
        for exc in exception_types:
            # Create a test app for each iteration
            test_app = create_test_app()
            
            mock_analyzer = MagicMock(spec=Analyzer)
            mock_analyzer.analyze = AsyncMock(side_effect=exc)
            
            configure_analyzer(mock_analyzer)
            
            with TestClient(test_app) as client:
                response = client.post(
                    "/analyze",
                    json={"text": "Valid text content"},
                )
                
                assert response.status_code == 500, f"Expected 500 for {type(exc).__name__}"
                data = response.json()
                assert data["detail"]["error"] == "internal_error"


# ============================================================================
# Test: No claims found → valid response with null trust_score and empty claims
# ============================================================================

class TestNoClaimsFound:
    """Tests for when no financial claims are found in the text.
    
    Requirements: 12.1
    """
    
    def test_no_claims_returns_200(self, no_claims_client):
        """No claims found should return 200 with valid response (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
    
    def test_no_claims_returns_null_trust_score(self, no_claims_client):
        """No claims found should return null trust_score (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] is None
    
    def test_no_claims_returns_empty_claims_array(self, no_claims_client):
        """No claims found should return empty claims array (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["claims"] == []
    
    def test_no_claims_returns_null_overall_classification(self, no_claims_client):
        """No claims found should return null overall_classification (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall_classification"] is None
    
    def test_no_claims_returns_null_trust_score_breakdown(self, no_claims_client):
        """No claims found should return null trust_score_breakdown (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score_breakdown"] is None
    
    def test_no_claims_returns_explanation(self, no_claims_client):
        """No claims found should return an explanation (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["explanation"] is not None
        assert len(data["explanation"]) > 0
        # Should indicate no claims were detected
        assert "no financial claims" in data["explanation"].lower()
    
    def test_no_claims_returns_empty_sources(self, no_claims_client):
        """No claims found should return empty sources array (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sources"] == []
    
    def test_no_claims_returns_disclaimer(self, no_claims_client):
        """No claims found should still return disclaimer (Req 12.1)."""
        response = no_claims_client.post(
            "/analyze",
            json={"text": "The weather today is sunny with a high of 75 degrees."},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 0


# ============================================================================
# Test: Error response structure matches ErrorResponse model
# ============================================================================

class TestErrorResponseStructure:
    """Tests for error response structure conformance.
    
    Requirements: 8.3, 8.4
    """
    
    def test_422_error_response_structure(self, test_client):
        """422 error response should have detail field (Pydantic validation)."""
        response = test_client.post(
            "/analyze",
            json={"text": ""},  # Empty text triggers 422 (Pydantic min_length)
        )
        
        assert response.status_code == 422
        data = response.json()
        
        # FastAPI/Pydantic returns validation errors in {"detail": [...]} format
        assert "detail" in data
    
    def test_400_error_response_structure(self, test_client):
        """400 error response should match ErrorResponse model structure."""
        response = test_client.post(
            "/analyze",
            json={"text": "   "},  # Whitespace-only triggers 400 (Analyzer validation)
        )
        
        assert response.status_code == 400
        data = response.json()
        
        # Our custom error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "error" in detail
        assert "detail" in detail
        assert isinstance(detail["error"], str)
        assert isinstance(detail["detail"], str)
    
    def test_503_error_response_structure(self):
        """503 error response should match ErrorResponse model structure."""
        # Create a test app
        test_app = create_test_app()
        
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=LLMUnavailableError("Service unavailable")
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 503
            data = response.json()
            
            # Our custom error response structure
            assert "detail" in data
            detail = data["detail"]
            assert "error" in detail
            assert "detail" in detail
            assert isinstance(detail["error"], str)
            assert isinstance(detail["detail"], str)
    
    def test_500_error_response_structure(self):
        """500 error response should match ErrorResponse model structure."""
        # Create a test app
        test_app = create_test_app()
        
        mock_analyzer = MagicMock(spec=Analyzer)
        mock_analyzer.analyze = AsyncMock(
            side_effect=RuntimeError("Internal error")
        )
        
        configure_analyzer(mock_analyzer)
        
        with TestClient(test_app) as client:
            response = client.post(
                "/analyze",
                json={"text": "Valid text content"},
            )
            
            assert response.status_code == 500
            data = response.json()
            
            # Our custom error response structure
            assert "detail" in data
            detail = data["detail"]
            assert "error" in detail
            assert "detail" in detail
            assert isinstance(detail["error"], str)
            assert isinstance(detail["detail"], str)


# ============================================================================
# Test: Health endpoint
# ============================================================================

class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_endpoint_returns_200(self, test_client):
        """Health endpoint should return 200."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
    
    def test_health_endpoint_returns_status_ok(self, test_client):
        """Health endpoint should return status ok."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_health_endpoint_returns_version(self, test_client):
        """Health endpoint should return version."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)
