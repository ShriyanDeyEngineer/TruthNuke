"""TruthNuke FastAPI Application Entry Point.

This module initializes and configures the FastAPI application for the
TruthNuke financial misinformation detector backend.

Requirements: 8.5, 13.1, 13.2, 13.3
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import configure_analyzer, router
from app.services.analyzer import Analyzer
from app.services.claim_extractor import ClaimExtractor
from app.services.classifier import Classifier
from app.services.explanation_engine import ExplanationEngine
from app.services.llm_client import LLMClient
from app.services.mock_search_provider import MockSearchProvider
from app.services.rag_pipeline import RAGPipeline
from app.services.trust_score_engine import TrustScoreEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_analyzer() -> Analyzer:
    """Create and configure the Analyzer with all service dependencies.
    
    This function creates the Analyzer instance with all required services
    based on the current configuration. It uses MockSearchProvider when
    no external API keys are configured.
    
    Returns:
        Configured Analyzer instance.
    
    Raises:
        ValueError: If required configuration (LLM_API_KEY) is missing.
    
    Requirements: 13.1, 13.2, 13.3
    """
    # Get LLM API key from environment (required)
    llm_api_key = os.environ.get("LLM_API_KEY", "").strip()
    
    if not llm_api_key:
        logger.warning(
            "LLM_API_KEY not set. Running in limited mode without LLM services."
        )
        # Return analyzer without LLM-dependent services
        return Analyzer(
            claim_extractor=None,
            rag_pipeline=RAGPipeline(
                search_provider=MockSearchProvider(),
                top_k=int(os.environ.get("TOP_K", "5")),
            ),
            classifier=None,
            trust_score_engine=TrustScoreEngine(),
            explanation_engine=None,
            max_input_length=int(os.environ.get("MAX_INPUT_LENGTH", "50000")),
        )
    
    # Get LLM configuration from environment
    llm_model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    llm_timeout = float(os.environ.get("LLM_TIMEOUT", "30.0"))
    llm_max_retries = int(os.environ.get("LLM_MAX_RETRIES", "3"))
    
    # Create LLM client
    llm_client = LLMClient(
        api_key=llm_api_key,
        model=llm_model,
        timeout=llm_timeout,
        max_retries=llm_max_retries,
    )
    
    # Get RAG configuration
    top_k = int(os.environ.get("TOP_K", "5"))
    
    # Create search provider (use MockSearchProvider for Phase 1)
    # In Phase 2, this will check for news/financial API keys and use live providers
    search_provider = MockSearchProvider()
    logger.info("Using MockSearchProvider for evidence retrieval")
    
    # Create RAG pipeline
    rag_pipeline = RAGPipeline(
        search_provider=search_provider,
        top_k=top_k,
    )
    
    # Create services
    claim_extractor = ClaimExtractor(llm_client)
    classifier = Classifier(llm_client)
    trust_score_engine = TrustScoreEngine()
    explanation_engine = ExplanationEngine(llm_client)
    
    # Get max input length from environment
    max_input_length = int(os.environ.get("MAX_INPUT_LENGTH", "50000"))
    
    # Create and return the Analyzer
    analyzer = Analyzer(
        claim_extractor=claim_extractor,
        rag_pipeline=rag_pipeline,
        classifier=classifier,
        trust_score_engine=trust_score_engine,
        explanation_engine=explanation_engine,
        max_input_length=max_input_length,
    )
    
    logger.info(
        f"Analyzer configured with LLM model={llm_model}, "
        f"top_k={top_k}, max_input_length={max_input_length}"
    )
    
    return analyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.
    
    Handles startup and shutdown events for the FastAPI application.
    Creates and configures the Analyzer during startup.
    """
    # Startup
    logger.info("Starting TruthNuke API server...")
    
    try:
        analyzer = create_analyzer()
        configure_analyzer(analyzer)
        logger.info("Analyzer configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure Analyzer: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down TruthNuke API server...")


# Create the FastAPI application
app = FastAPI(
    title="TruthNuke API",
    description="AI-powered financial misinformation detector",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware with allowed origin from environment (Req 8.5)
cors_origin = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
logger.info(f"Configuring CORS with allowed origin: {cors_origin}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(router)


def main() -> None:
    """Run the application using uvicorn."""
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
