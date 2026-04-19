"""TruthNuke FastAPI Application Entry Point.

This module initializes and configures the FastAPI application for the
TruthNuke financial misinformation detector backend.

Requirements: 8.5, 13.1, 13.2, 13.3
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import configure_analyzer, router
from app.config import get_settings, ConfigurationError
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
    
    Requirements: 13.1, 13.2, 13.3
    """
    try:
        settings = get_settings()
    except ConfigurationError:
        logger.warning(
            "Configuration error. Running in limited mode without LLM services."
        )
        return Analyzer(
            claim_extractor=None,
            rag_pipeline=RAGPipeline(
                search_provider=MockSearchProvider(),
                top_k=5,
            ),
            classifier=None,
            trust_score_engine=TrustScoreEngine(),
            explanation_engine=None,
        )
    
    # Create LLM client with settings
    llm_client = LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        base_url=settings.llm_base_url,
    )
    
    # Create search provider (use MockSearchProvider for Phase 1)
    search_provider = MockSearchProvider()
    logger.info("Using MockSearchProvider for evidence retrieval")
    
    # Create RAG pipeline
    rag_pipeline = RAGPipeline(
        search_provider=search_provider,
        top_k=settings.top_k,
    )
    
    # Create services
    claim_extractor = ClaimExtractor(llm_client)
    classifier = Classifier(llm_client)
    trust_score_engine = TrustScoreEngine()
    explanation_engine = ExplanationEngine(llm_client)
    
    # Create and return the Analyzer
    analyzer = Analyzer(
        claim_extractor=claim_extractor,
        rag_pipeline=rag_pipeline,
        classifier=classifier,
        trust_score_engine=trust_score_engine,
        explanation_engine=explanation_engine,
        max_input_length=settings.max_input_length,
    )
    
    logger.info(
        f"Analyzer configured with LLM model={settings.llm_model}, "
        f"base_url={settings.llm_base_url}, "
        f"top_k={settings.top_k}, max_input_length={settings.max_input_length}"
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
try:
    _settings = get_settings()
    cors_origin = _settings.cors_origin
except ConfigurationError:
    cors_origin = "http://localhost:3000"
logger.info(f"Configuring CORS with allowed origin: {cors_origin}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (needed for Chrome extension)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router at both / and /api (extension calls /api/analyze)
app.include_router(router)
app.include_router(router, prefix="/api")


def main() -> None:
    """Run the application using uvicorn."""
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
