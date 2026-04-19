"""
Common pytest fixtures for TruthNuke backend tests.

This module provides shared fixtures used across unit, integration,
and property-based tests.
"""

import pytest
from hypothesis import settings, Verbosity

# Configure Hypothesis settings for property-based tests
# Minimum 100 iterations as per design requirements
settings.register_profile(
    "default",
    max_examples=100,
    verbosity=Verbosity.normal,
)
settings.register_profile(
    "ci",
    max_examples=200,
    verbosity=Verbosity.normal,
)
settings.register_profile(
    "debug",
    max_examples=10,
    verbosity=Verbosity.verbose,
)
settings.load_profile("default")


@pytest.fixture
def sample_text() -> str:
    """Provide sample text containing financial claims for testing."""
    return (
        "Apple's stock price increased by 15% last quarter. "
        "Bitcoin reached an all-time high of $100,000. "
        "The Federal Reserve announced a 0.25% interest rate hike."
    )


@pytest.fixture
def sample_text_no_claims() -> str:
    """Provide sample text with no financial claims."""
    return "The weather today is sunny with a high of 75 degrees."


@pytest.fixture
def sample_whitespace_text() -> str:
    """Provide text with excessive whitespace for normalization testing."""
    return "   Apple's   stock   price   increased   by   15%   "


@pytest.fixture
def sample_empty_text() -> str:
    """Provide empty text for validation testing."""
    return ""


@pytest.fixture
def sample_whitespace_only_text() -> str:
    """Provide whitespace-only text for validation testing."""
    return "   \t\n   "


@pytest.fixture
def sample_long_text() -> str:
    """Provide text exceeding the 50,000 character limit."""
    return "A" * 50001


@pytest.fixture
def max_length_text() -> str:
    """Provide text at exactly the 50,000 character limit."""
    return "A" * 50000
