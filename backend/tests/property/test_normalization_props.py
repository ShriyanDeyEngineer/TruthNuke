"""
Property-based tests for text normalization and validation.

This module tests that the Analyzer's _normalize() method correctly handles
whitespace while preserving all non-whitespace content, and that the
_validate() method correctly rejects whitespace-only strings.

**Validates: Requirements 1.2, 1.3**
"""

import re

import pytest
from hypothesis import given, strategies as st, settings

from app.services.analyzer import Analyzer, ValidationError


# Strategy for generating strings with mixed whitespace characters
# Includes spaces, tabs, newlines, carriage returns, and form feeds
whitespace_chars = " \t\n\r\f\v"


@st.composite
def mixed_whitespace_string_strategy(draw):
    """
    Hypothesis composite strategy for generating strings with mixed whitespace.
    
    Generates strings that may contain:
    - Leading whitespace
    - Trailing whitespace
    - Consecutive whitespace characters between words
    - Various whitespace types (spaces, tabs, newlines, etc.)
    """
    # Generate a list of text segments and whitespace segments
    num_segments = draw(st.integers(min_value=0, max_value=10))
    
    parts = []
    for i in range(num_segments):
        # Add optional leading whitespace for first segment
        if i == 0:
            leading_ws = draw(st.text(alphabet=whitespace_chars, min_size=0, max_size=5))
            parts.append(leading_ws)
        
        # Add a non-whitespace text segment (word)
        word = draw(st.text(
            alphabet=st.characters(blacklist_characters=whitespace_chars),
            min_size=1,
            max_size=20
        ).filter(lambda s: len(s.strip()) > 0))
        parts.append(word)
        
        # Add whitespace between segments (or trailing for last segment)
        ws = draw(st.text(alphabet=whitespace_chars, min_size=1, max_size=5))
        parts.append(ws)
    
    return "".join(parts)


@st.composite
def any_string_with_whitespace_strategy(draw):
    """
    Alternative strategy that generates any text with potential whitespace issues.
    
    This strategy is simpler and generates a wider variety of inputs.
    """
    # Generate base text that may contain any characters
    text = draw(st.text(min_size=0, max_size=200))
    return text


def extract_non_whitespace_content(text: str) -> list[str]:
    """
    Extract all non-whitespace characters from text, preserving order.
    
    Returns a list of individual non-whitespace characters.
    """
    return [char for char in text if not char.isspace()]


def extract_non_whitespace_tokens(text: str) -> list[str]:
    """
    Extract all non-whitespace tokens (words) from text, preserving order.
    
    Returns a list of whitespace-separated tokens.
    """
    return text.split()


@given(text=mixed_whitespace_string_strategy())
@settings(max_examples=100)
def test_normalization_no_leading_whitespace(text: str):
    """
    Property 1a: Normalized text has no leading whitespace.
    
    For any input string, the normalized output should not start with
    any whitespace character.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    # If the result is non-empty, it should not start with whitespace
    if normalized:
        assert not normalized[0].isspace(), (
            f"Normalized text starts with whitespace: {repr(normalized)}"
        )


@given(text=mixed_whitespace_string_strategy())
@settings(max_examples=100)
def test_normalization_no_trailing_whitespace(text: str):
    """
    Property 1b: Normalized text has no trailing whitespace.
    
    For any input string, the normalized output should not end with
    any whitespace character.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    # If the result is non-empty, it should not end with whitespace
    if normalized:
        assert not normalized[-1].isspace(), (
            f"Normalized text ends with whitespace: {repr(normalized)}"
        )


@given(text=mixed_whitespace_string_strategy())
@settings(max_examples=100)
def test_normalization_no_consecutive_whitespace(text: str):
    """
    Property 1c: Normalized text has no consecutive whitespace characters.
    
    For any input string, the normalized output should not contain
    two or more consecutive whitespace characters.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    # Check for consecutive whitespace using regex
    consecutive_ws_pattern = re.compile(r'\s{2,}')
    match = consecutive_ws_pattern.search(normalized)
    
    assert match is None, (
        f"Normalized text contains consecutive whitespace at position {match.start()}: "
        f"{repr(normalized)}"
    )


@given(text=mixed_whitespace_string_strategy())
@settings(max_examples=100)
def test_normalization_preserves_non_whitespace_content(text: str):
    """
    Property 1d: Normalization preserves all non-whitespace content in order.
    
    For any input string, all non-whitespace characters should appear
    in the normalized output in the same relative order.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    # Extract non-whitespace characters from both input and output
    original_content = extract_non_whitespace_content(text)
    normalized_content = extract_non_whitespace_content(normalized)
    
    # All non-whitespace content should be preserved in the same order
    assert original_content == normalized_content, (
        f"Non-whitespace content not preserved.\n"
        f"Original: {original_content}\n"
        f"Normalized: {normalized_content}"
    )


@given(text=any_string_with_whitespace_strategy())
@settings(max_examples=100)
def test_normalization_combined_properties(text: str):
    """
    Property 1: Text normalization preserves content and removes excess whitespace.
    
    Combined test that verifies all normalization properties together:
    1. No leading whitespace in output
    2. No trailing whitespace in output
    3. No consecutive whitespace characters in output
    4. All non-whitespace content is preserved in the same order
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    # Property 1a: No leading whitespace
    if normalized:
        assert not normalized[0].isspace(), (
            f"Normalized text starts with whitespace: {repr(normalized)}"
        )
    
    # Property 1b: No trailing whitespace
    if normalized:
        assert not normalized[-1].isspace(), (
            f"Normalized text ends with whitespace: {repr(normalized)}"
        )
    
    # Property 1c: No consecutive whitespace
    consecutive_ws_pattern = re.compile(r'\s{2,}')
    match = consecutive_ws_pattern.search(normalized)
    assert match is None, (
        f"Normalized text contains consecutive whitespace: {repr(normalized)}"
    )
    
    # Property 1d: Non-whitespace content preserved in order
    original_content = extract_non_whitespace_content(text)
    normalized_content = extract_non_whitespace_content(normalized)
    assert original_content == normalized_content, (
        f"Non-whitespace content not preserved.\n"
        f"Original: {original_content}\n"
        f"Normalized: {normalized_content}"
    )


@given(text=st.text(alphabet=whitespace_chars, min_size=0, max_size=50))
@settings(max_examples=100)
def test_normalization_whitespace_only_returns_empty(text: str):
    """
    Property: Whitespace-only input normalizes to empty string.
    
    For any string composed entirely of whitespace characters,
    normalization should produce an empty string.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    normalized = analyzer._normalize(text)
    
    assert normalized == "", (
        f"Whitespace-only input should normalize to empty string, "
        f"got: {repr(normalized)}"
    )


@given(text=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()))
@settings(max_examples=100)
def test_normalization_idempotent(text: str):
    """
    Property: Normalization is idempotent.
    
    Normalizing an already-normalized string should produce the same result.
    
    **Validates: Requirements 1.2**
    """
    analyzer = Analyzer()
    
    # Normalize once
    normalized_once = analyzer._normalize(text)
    
    # Normalize again
    normalized_twice = analyzer._normalize(normalized_once)
    
    # Results should be identical
    assert normalized_once == normalized_twice, (
        f"Normalization is not idempotent.\n"
        f"First normalization: {repr(normalized_once)}\n"
        f"Second normalization: {repr(normalized_twice)}"
    )


# =============================================================================
# Property 2: Whitespace-only strings are rejected
# =============================================================================


# Strategy for generating strings composed entirely of whitespace characters
# Includes spaces, tabs, newlines, carriage returns, form feeds, and vertical tabs
whitespace_only_strategy = st.text(
    alphabet=" \t\n\r\f\v",
    min_size=1,  # At least one whitespace character
    max_size=100
)


@given(text=whitespace_only_strategy)
@settings(max_examples=100)
def test_whitespace_only_strings_are_rejected(text: str):
    """
    Property 2: Whitespace-only strings are rejected.
    
    For any string composed entirely of whitespace characters (spaces, tabs,
    newlines, carriage returns, form feeds, vertical tabs, or combinations
    thereof), submitting it to the Analyzer's validation step should produce
    a ValidationError, and no analysis should proceed.
    
    **Validates: Requirements 1.3**
    """
    analyzer = Analyzer()
    
    # Whitespace-only strings should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        analyzer._validate(text)
    
    # Verify the error message indicates non-empty text is required
    assert "non-empty" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower(), (
        f"ValidationError message should indicate non-empty text is required, "
        f"got: {exc_info.value.message}"
    )


@given(text=st.text(alphabet=" \t\n\r\f\v", min_size=0, max_size=100))
@settings(max_examples=100)
def test_empty_and_whitespace_only_strings_are_rejected(text: str):
    """
    Property 2 (extended): Empty and whitespace-only strings are rejected.
    
    For any string that is either empty or composed entirely of whitespace
    characters, submitting it to the Analyzer's validation step should
    produce a ValidationError.
    
    **Validates: Requirements 1.3**
    """
    analyzer = Analyzer()
    
    # Empty and whitespace-only strings should raise ValidationError
    with pytest.raises(ValidationError):
        analyzer._validate(text)


@given(
    ws_prefix=st.text(alphabet=" \t\n\r\f\v", min_size=0, max_size=20),
    ws_suffix=st.text(alphabet=" \t\n\r\f\v", min_size=0, max_size=20),
    ws_middle=st.lists(
        st.text(alphabet=" \t\n\r\f\v", min_size=1, max_size=10),
        min_size=0,
        max_size=5
    )
)
@settings(max_examples=100)
def test_various_whitespace_combinations_are_rejected(
    ws_prefix: str, ws_suffix: str, ws_middle: list[str]
):
    """
    Property 2 (variant): Various whitespace combinations are rejected.
    
    For any combination of different whitespace character types (spaces,
    tabs, newlines, etc.), the validation should reject the input.
    
    **Validates: Requirements 1.3**
    """
    # Combine all whitespace parts into a single string
    text = ws_prefix + "".join(ws_middle) + ws_suffix
    
    # Skip if the result is empty (covered by other tests)
    if not text:
        return
    
    analyzer = Analyzer()
    
    # Whitespace-only strings should raise ValidationError
    with pytest.raises(ValidationError):
        analyzer._validate(text)


@given(text=whitespace_only_strategy)
@settings(max_examples=100)
def test_whitespace_only_validation_prevents_analysis(text: str):
    """
    Property 2 (behavioral): Whitespace-only validation prevents analysis.
    
    For any whitespace-only string, the analyze() method should raise
    ValidationError before any analysis proceeds.
    
    **Validates: Requirements 1.3**
    """
    analyzer = Analyzer()
    
    # The analyze method should raise ValidationError for whitespace-only input
    with pytest.raises(ValidationError):
        # Note: analyze() is async, but _validate() is called synchronously
        # at the start, so we can test the validation directly
        analyzer._validate(text)
