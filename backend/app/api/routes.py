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
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@router.post("/chat")
async def chat_with_feed(
    request: dict,
    analyzer: Annotated[Analyzer, Depends(get_analyzer)],
) -> dict:
    """Chat endpoint that answers questions about the user's analyzed feed.

    The extension sends the user's question along with their stored feed
    data. The LLM answers using that context.
    """
    question = request.get("question", "").strip()
    feed_items = request.get("feed", [])

    if not question:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "detail": "Question is required."})

    # Build context from feed items
    context_parts = []
    for i, item in enumerate(feed_items[:50], 1):
        ts = item.get("timestamp")
        date_str = ""
        day_of_week = ""
        if ts:
            from datetime import datetime
            try:
                dt = datetime.fromtimestamp(ts / 1000)
                date_str = dt.strftime("%A, %B %d, %Y at %I:%M %p")
                day_of_week = dt.strftime("%A")
            except Exception:
                date_str = str(ts)
        platform = item.get("platform", "unknown")
        author = item.get("author", "unknown")
        author_name = item.get("author_name", author)
        text = item.get("text", "")
        score = item.get("trust_score", "N/A")
        explanation = item.get("explanation", "")
        claims_list = item.get("claims", [])
        claims_text = "; ".join(c.get("claim", "")[:100] for c in claims_list) if claims_list else "none extracted"
        context_parts.append(
            f"[{i}] Platform: {platform} | Author: @{author} ({author_name}) | "
            f"Day: {day_of_week} | Date: {date_str} | Trust Score: {score}\n"
            f"Content: {text}\n"
            f"Claims: {claims_text}\n"
            f"Summary: {explanation[:200] if explanation else 'N/A'}"
        )

    feed_context = "\n\n".join(context_parts) if context_parts else "No articles in the feed yet."

    system_prompt = (
        "You are TruthNuke's research assistant. The user has a feed of analyzed "
        "financial articles/posts. Answer their question using ONLY the feed data "
        "provided below.\n\n"
        "RULES:\n"
        "- When listing articles, ALWAYS include: Author, Platform, Date, Trust Score, "
        "and a one-sentence description of the content.\n"
        "- Format each article as a numbered item.\n"
        "- If the user asks about a specific day (e.g. Saturday), filter by the Day field.\n"
        "- If the user asks about a specific platform, filter by Platform.\n"
        "- If the user asks about a specific stock or topic, search the Content and Claims fields.\n"
        "- Be concise and helpful. If no matching data exists, say so clearly.\n\n"
        f"=== USER'S ANALYZED FEED ({len(feed_items)} items) ===\n{feed_context}"
    )

    if not analyzer.claim_extractor or not hasattr(analyzer.claim_extractor, 'llm_client'):
        return {"answer": "Chat is unavailable — LLM service not configured."}

    llm = analyzer.claim_extractor.llm_client
    try:
        answer = await llm.complete(prompt=question, system_prompt=system_prompt)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {"answer": "Sorry, I couldn't process that question right now. Please try again."}
