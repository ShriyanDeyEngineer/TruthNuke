"""TruthNuke API Routes.

This module defines the FastAPI routes for the TruthNuke API, including
the POST /analyze endpoint and GET /health endpoint.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.1, 12.3, 13.1, 27.3, 27.4
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    ContentModality,
    ErrorResponse,
)
from app.services.analyzer import Analyzer, ValidationError
from app.services.llm_client import LLMUnavailableError, LLMParsingError


logger = logging.getLogger(__name__)


# Create the API router
router = APIRouter()


# Dependency injection for the Analyzer
_analyzer_instance: Analyzer | None = None


def get_analyzer() -> Analyzer:
    """Get the Analyzer instance for dependency injection.
    
    This function returns the configured Analyzer instance. The instance
    is created and configured during application startup.
    
    Returns:
        The configured Analyzer instance.
    
    Raises:
        RuntimeError: If the Analyzer has not been initialized.
    """
    if _analyzer_instance is None:
        raise RuntimeError(
            "Analyzer not initialized. Call configure_analyzer() during startup."
        )
    return _analyzer_instance


def configure_analyzer(analyzer: Analyzer) -> None:
    """Configure the Analyzer instance for dependency injection.
    
    This function should be called during application startup to set up
    the Analyzer with all its dependencies.
    
    Args:
        analyzer: The configured Analyzer instance.
    """
    global _analyzer_instance
    _analyzer_instance = analyzer


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Analyze text for financial misinformation",
    description="Submit text containing financial claims for analysis. "
                "Returns classification, trust score, and explanation.",
)
async def analyze(
    request: AnalyzeRequest,
    analyzer: Annotated[Analyzer, Depends(get_analyzer)],
) -> AnalysisResponse:
    """Analyze text for financial misinformation.
    
    This endpoint accepts text containing financial claims and returns
    a comprehensive analysis including:
    - Extracted claims with classifications
    - Overall trust score (0-100)
    - Trust score breakdown by component
    - Natural language explanation
    - Retrieved sources
    
    Args:
        request: The analysis request containing text and optional content_type.
        analyzer: The Analyzer instance (injected).
    
    Returns:
        AnalysisResponse containing the complete analysis results.
    
    Raises:
        HTTPException: 400 for validation errors, 500 for internal errors,
                      503 for LLM unavailability.
    
    Requirements: 8.1, 8.2, 8.3, 8.4, 12.1, 12.3, 27.3, 27.4
    """
    # Validate content_type - only TEXT is supported in Phase 1 (Req 27.4)
    if request.content_type != ContentModality.TEXT:
        logger.warning(
            f"Unsupported content_type requested: {request.content_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "detail": f"Unsupported content type: {request.content_type.value}. "
                          f"Supported types: {ContentModality.TEXT.value}",
            },
        )
    
    try:
        # Run the analysis pipeline (Req 8.1, 8.2)
        response = await analyzer.analyze(request.text)
        return response
        
    except ValidationError as e:
        # Return 400 for validation errors (Req 8.3)
        logger.info(f"Validation error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "detail": e.message,
            },
        )
        
    except LLMUnavailableError as e:
        # Return 503 for LLM unavailability (Req 12.3)
        logger.error(f"LLM service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "service_unavailable",
                "detail": "Analysis service is temporarily unavailable. Please try again later.",
            },
        )
        
    except LLMParsingError as e:
        # Return 502 when LLM returns unparseable response
        logger.error(f"LLM returned invalid response: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "llm_response_error",
                "detail": "The AI model returned an invalid response. Please try again.",
            },
        )
        
    except Exception as e:
        # Return 500 for internal errors - no internal details exposed (Req 8.4)
        logger.exception(f"Internal error during analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "detail": "An unexpected error occurred.",
            },
        )


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Returns the health status and version of the API.",
)
async def health_check() -> dict:
    """Health check endpoint.
    
    Returns the current health status and version of the API.
    
    Returns:
        Dictionary with status and version information.
    """
    return {"status": "ok", "version": "0.1.0"}
