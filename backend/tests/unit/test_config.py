"""Unit tests for the configuration module.

Tests the Settings class and get_settings function to ensure:
- Required LLM_API_KEY validation works
- Default values are applied correctly
- Trust score weights parsing works
- Configuration errors are raised appropriately

Requirements: 13.1, 13.2, 13.3
"""

import os
from unittest.mock import patch

import pytest

from app.config import ConfigurationError, Settings, get_settings
from app.models.schemas import TrustScoreWeights


class TestSettings:
    """Tests for the Settings class."""

    def test_settings_with_valid_api_key(self):
        """Test that settings load correctly with a valid API key."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-api-key"}, clear=False):
            settings = Settings()
            assert settings.llm_api_key == "test-api-key"

    def test_settings_missing_api_key_raises_error(self):
        """Test that missing LLM_API_KEY raises a validation error."""
        # Create a clean environment without LLM_API_KEY
        env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception) as exc_info:
                Settings()
            # The error should mention LLM_API_KEY
            assert "LLM_API_KEY" in str(exc_info.value) or "llm_api_key" in str(exc_info.value)

    def test_settings_empty_api_key_raises_error(self):
        """Test that empty LLM_API_KEY raises a validation error."""
        with patch.dict(os.environ, {"LLM_API_KEY": ""}, clear=False):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "LLM_API_KEY" in str(exc_info.value) or "required" in str(exc_info.value).lower()

    def test_settings_whitespace_api_key_raises_error(self):
        """Test that whitespace-only LLM_API_KEY raises a validation error."""
        with patch.dict(os.environ, {"LLM_API_KEY": "   "}, clear=False):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "LLM_API_KEY" in str(exc_info.value) or "required" in str(exc_info.value).lower()

    def test_default_llm_model(self):
        """Test that LLM_MODEL defaults to gpt-4o-mini."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.llm_model == "gpt-4o-mini"

    def test_custom_llm_model(self):
        """Test that LLM_MODEL can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "LLM_MODEL": "gpt-4"},
            clear=False,
        ):
            settings = Settings()
            assert settings.llm_model == "gpt-4"

    def test_default_llm_timeout(self):
        """Test that LLM_TIMEOUT defaults to 30.0."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.llm_timeout == 30.0

    def test_custom_llm_timeout(self):
        """Test that LLM_TIMEOUT can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "LLM_TIMEOUT": "60.0"},
            clear=False,
        ):
            settings = Settings()
            assert settings.llm_timeout == 60.0

    def test_default_llm_max_retries(self):
        """Test that LLM_MAX_RETRIES defaults to 3."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.llm_max_retries == 3

    def test_custom_llm_max_retries(self):
        """Test that LLM_MAX_RETRIES can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "LLM_MAX_RETRIES": "5"},
            clear=False,
        ):
            settings = Settings()
            assert settings.llm_max_retries == 5

    def test_default_top_k(self):
        """Test that TOP_K defaults to 5."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.top_k == 5

    def test_custom_top_k(self):
        """Test that TOP_K can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TOP_K": "10"},
            clear=False,
        ):
            settings = Settings()
            assert settings.top_k == 10

    def test_default_max_input_length(self):
        """Test that MAX_INPUT_LENGTH defaults to 50000."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.max_input_length == 50000

    def test_custom_max_input_length(self):
        """Test that MAX_INPUT_LENGTH can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "MAX_INPUT_LENGTH": "100000"},
            clear=False,
        ):
            settings = Settings()
            assert settings.max_input_length == 100000

    def test_default_cors_origin(self):
        """Test that CORS_ORIGIN defaults to http://localhost:3000."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            assert settings.cors_origin == "http://localhost:3000"

    def test_custom_cors_origin(self):
        """Test that CORS_ORIGIN can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "CORS_ORIGIN": "https://example.com"},
            clear=False,
        ):
            settings = Settings()
            assert settings.cors_origin == "https://example.com"


class TestTrustScoreWeights:
    """Tests for trust score weights parsing."""

    def test_default_trust_score_weights(self):
        """Test that TRUST_SCORE_WEIGHTS defaults to 0.3,0.3,0.2,0.2."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            settings = Settings()
            weights = settings.trust_score_weights
            assert isinstance(weights, TrustScoreWeights)
            assert weights.source_credibility == 0.3
            assert weights.evidence_strength == 0.3
            assert weights.language_neutrality == 0.2
            assert weights.cross_source_agreement == 0.2

    def test_custom_trust_score_weights(self):
        """Test that TRUST_SCORE_WEIGHTS can be customized."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "0.25,0.25,0.25,0.25"},
            clear=False,
        ):
            settings = Settings()
            weights = settings.trust_score_weights
            assert weights.source_credibility == 0.25
            assert weights.evidence_strength == 0.25
            assert weights.language_neutrality == 0.25
            assert weights.cross_source_agreement == 0.25

    def test_trust_score_weights_with_spaces(self):
        """Test that TRUST_SCORE_WEIGHTS handles spaces correctly."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "0.3, 0.3, 0.2, 0.2"},
            clear=False,
        ):
            settings = Settings()
            weights = settings.trust_score_weights
            assert weights.source_credibility == 0.3
            assert weights.evidence_strength == 0.3

    def test_trust_score_weights_invalid_count(self):
        """Test that TRUST_SCORE_WEIGHTS with wrong count raises error."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "0.5,0.5"},
            clear=False,
        ):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "4" in str(exc_info.value) or "comma-separated" in str(exc_info.value)

    def test_trust_score_weights_invalid_values(self):
        """Test that TRUST_SCORE_WEIGHTS with non-numeric values raises error."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "a,b,c,d"},
            clear=False,
        ):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "float" in str(exc_info.value).lower() or "valid" in str(exc_info.value).lower()

    def test_trust_score_weights_not_summing_to_one(self):
        """Test that TRUST_SCORE_WEIGHTS not summing to 1.0 raises error."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "0.5,0.5,0.5,0.5"},
            clear=False,
        ):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "sum" in str(exc_info.value).lower() or "1.0" in str(exc_info.value)

    def test_trust_score_weights_negative_values(self):
        """Test that TRUST_SCORE_WEIGHTS with negative values raises error."""
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": "test-key", "TRUST_SCORE_WEIGHTS": "-0.1,0.4,0.4,0.3"},
            clear=False,
        ):
            with pytest.raises(Exception) as exc_info:
                Settings()
            assert "negative" in str(exc_info.value).lower() or "non-negative" in str(exc_info.value).lower()


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            # Clear the cache to ensure fresh settings
            get_settings.cache_clear()
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test that get_settings returns the same instance on repeated calls."""
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}, clear=False):
            get_settings.cache_clear()
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_get_settings_raises_configuration_error(self):
        """Test that get_settings raises ConfigurationError on invalid config."""
        env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            get_settings.cache_clear()
            with pytest.raises(ConfigurationError) as exc_info:
                get_settings()
            assert "configuration" in str(exc_info.value).lower()
