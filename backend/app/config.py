"""TruthNuke Configuration Module.

This module provides centralized configuration management using Pydantic Settings.
Configuration values are read from environment variables with support for .env files.

Requirements: 13.1, 13.2, 13.3
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.schemas import TrustScoreWeights


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All external API keys and configurable parameters are managed through
    environment variables. Required variables will cause the application
    to fail at startup if not set.
    
    Attributes:
        llm_api_key: API key for the LLM service (required).
        llm_model: LLM model to use for inference.
        llm_timeout: Timeout in seconds for LLM API calls.
        llm_max_retries: Maximum number of retries for LLM API calls.
        top_k: Number of top results to retrieve from search providers.
        max_input_length: Maximum allowed input text length in characters.
        trust_score_weights_str: Comma-separated weights for trust score components.
        cors_origin: Allowed origin for frontend CORS requests.
    
    Requirements: 13.1, 13.2, 13.3
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Required configuration - app fails to start if missing
    llm_api_key: str = Field(
        ...,
        description="API key for the LLM service (OpenAI, Anthropic, etc.)",
    )
    
    # LLM configuration with defaults
    llm_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for the LLM API (for OpenAI-compatible providers)",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for inference",
    )
    llm_timeout: float = Field(
        default=30.0,
        description="Timeout in seconds for LLM API calls",
        gt=0,
    )
    llm_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for LLM API calls",
        ge=0,
    )
    
    # RAG pipeline configuration
    top_k: int = Field(
        default=5,
        description="Number of top results to retrieve from search providers",
        ge=1,
    )
    
    # Input validation configuration
    max_input_length: int = Field(
        default=50000,
        description="Maximum allowed input text length in characters",
        ge=1,
    )
    
    # Trust score configuration - stored as string, parsed to TrustScoreWeights
    trust_score_weights_str: str = Field(
        default="0.3,0.3,0.2,0.2",
        alias="TRUST_SCORE_WEIGHTS",
        description="Comma-separated weights: Source_Credibility,Evidence_Strength,Language_Neutrality,Cross_Source_Agreement",
    )
    
    # CORS configuration
    cors_origin: str = Field(
        default="http://localhost:3000",
        description="Allowed origin for frontend CORS requests",
    )
    
    # Parsed trust score weights (computed from trust_score_weights_str)
    _trust_score_weights: Optional[TrustScoreWeights] = None
    
    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, v: str) -> str:
        """Validate that LLM_API_KEY is set and not empty.
        
        Raises:
            ValueError: If LLM_API_KEY is empty or whitespace-only.
        """
        if not v or not v.strip():
            raise ValueError(
                "LLM_API_KEY environment variable is required but not set. "
                "Please set LLM_API_KEY to your LLM service API key."
            )
        return v.strip()
    
    @field_validator("trust_score_weights_str")
    @classmethod
    def validate_trust_score_weights_str(cls, v: str) -> str:
        """Validate the trust score weights string format.
        
        Raises:
            ValueError: If the string is not in the expected format.
        """
        if not v or not v.strip():
            return "0.3,0.3,0.2,0.2"
        
        parts = v.strip().split(",")
        if len(parts) != 4:
            raise ValueError(
                f"TRUST_SCORE_WEIGHTS must contain exactly 4 comma-separated values, "
                f"got {len(parts)}: '{v}'"
            )
        
        try:
            weights = [float(p.strip()) for p in parts]
        except ValueError as e:
            raise ValueError(
                f"TRUST_SCORE_WEIGHTS must contain valid float values: '{v}'. Error: {e}"
            )
        
        # Validate weights sum to approximately 1.0
        total = sum(weights)
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"TRUST_SCORE_WEIGHTS must sum to 1.0, got {total}: '{v}'"
            )
        
        # Validate all weights are non-negative
        if any(w < 0 for w in weights):
            raise ValueError(
                f"TRUST_SCORE_WEIGHTS must all be non-negative: '{v}'"
            )
        
        return v.strip()
    
    @property
    def trust_score_weights(self) -> TrustScoreWeights:
        """Parse and return trust score weights as a TrustScoreWeights object.
        
        Returns:
            TrustScoreWeights object with the configured weights.
        """
        if self._trust_score_weights is None:
            parts = self.trust_score_weights_str.split(",")
            weights = [float(p.strip()) for p in parts]
            self._trust_score_weights = TrustScoreWeights(
                source_credibility=weights[0],
                evidence_strength=weights[1],
                language_neutrality=weights[2],
                cross_source_agreement=weights[3],
            )
        return self._trust_score_weights


class ConfigurationError(Exception):
    """Raised when there is a configuration error at startup."""
    pass


@lru_cache
def get_settings() -> Settings:
    """Get the application settings singleton.
    
    This function is cached to ensure only one Settings instance is created.
    The settings are loaded from environment variables and .env file.
    
    Returns:
        Settings: The application settings instance.
    
    Raises:
        ConfigurationError: If required configuration is missing or invalid.
    
    Example:
        >>> from app.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.llm_model)
        'gpt-4o-mini'
        >>> print(settings.trust_score_weights)
        TrustScoreWeights(source_credibility=0.3, ...)
    """
    try:
        return Settings()
    except Exception as e:
        raise ConfigurationError(
            f"Failed to load application configuration: {e}"
        ) from e
