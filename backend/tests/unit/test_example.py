"""
Example unit test to verify testing infrastructure is working.

This file can be removed once actual tests are implemented.
"""

import pytest


def test_example_passes():
    """Simple test to verify pytest is configured correctly."""
    assert True


def test_sample_text_fixture(sample_text: str):
    """Test that the sample_text fixture is available."""
    assert "Apple" in sample_text
    assert "stock" in sample_text


def test_sample_whitespace_only_fixture(sample_whitespace_only_text: str):
    """Test that the whitespace-only fixture is available."""
    assert sample_whitespace_only_text.strip() == ""
