"""LLM Client Wrapper for TruthNuke.

This module provides a wrapper around the OpenAI API with retry logic,
timeout handling, and error normalization.

Requirements: 12.3, 14.3
"""

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError, APIStatusError


logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM service is unavailable after all retries are exhausted.
    
    This error indicates that the LLM API could not be reached or returned
    persistent errors (timeout, rate limit, server errors) despite retry attempts.
    
    Requirements: 12.3
    """
    pass


class LLMParsingError(Exception):
    """Raised when the LLM returns a response that cannot be parsed as valid JSON.
    
    This error is raised by complete_json() when the LLM response is not
    valid JSON format.
    
    Requirements: 14.3
    """
    pass


class LLMClient:
    """Wrapper for LLM API calls with retry logic and error handling.
    
    This client wraps the OpenAI API and provides:
    - Async methods for non-blocking I/O
    - Exponential backoff retry logic for transient errors
    - Timeout handling
    - JSON response parsing with error handling
    
    Retry Strategy:
    - Max retries: configurable (default 3)
    - Base delay: 1 second
    - Backoff multiplier: 2x
    - Max delay: 10 seconds
    - Retryable errors: timeout, 429 (rate limit), 500, 502, 503
    
    Attributes:
        api_key: The API key for the LLM service.
        model: The model to use for completions.
        timeout: Timeout in seconds for API calls.
        max_retries: Maximum number of retry attempts.
    
    Example:
        >>> client = LLMClient(api_key="sk-...", model="gpt-4o-mini")
        >>> response = await client.complete("What is 2+2?")
        >>> print(response)
        "4"
        
        >>> data = await client.complete_json("Return JSON: {\"answer\": 4}")
        >>> print(data)
        {"answer": 4}
    
    Requirements: 12.3, 14.3
    """
    
    # Retry configuration constants
    BASE_DELAY_SECONDS = 0.5
    BACKOFF_MULTIPLIER = 2.0
    MAX_DELAY_SECONDS = 5.0
    
    # HTTP status codes that are retryable
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        max_retries: int = 3,
        base_url: str | None = None,
    ) -> None:
        """Initialize the LLM client.
        
        Args:
            api_key: API key for the LLM service (required).
            model: Model identifier to use for completions.
            timeout: Timeout in seconds for API calls.
            max_retries: Maximum number of retry attempts for transient errors.
            base_url: Optional base URL for OpenAI-compatible providers.
        
        Raises:
            ValueError: If api_key is empty or None.
        """
        if not api_key or not api_key.strip():
            raise ValueError("api_key is required and cannot be empty")
        
        self.api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Initialize the async OpenAI client
        # Disable the OpenAI SDK's own retry logic — we handle retries ourselves
        client_kwargs: dict = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": 0,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self._client = AsyncOpenAI(**client_kwargs)
    
    async def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Send a prompt to the LLM and return the response text.
        
        This method sends a chat completion request to the LLM with optional
        system prompt. It implements exponential backoff retry logic for
        transient errors.
        
        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt to set context.
        
        Returns:
            The text content of the LLM's response.
        
        Raises:
            LLMUnavailableError: If the LLM service is unavailable after
                all retry attempts are exhausted.
        
        Example:
            >>> response = await client.complete(
            ...     prompt="Extract claims from: The stock rose 10%",
            ...     system_prompt="You are a financial claim extractor."
            ... )
        
        Requirements: 12.3
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return await self._execute_with_retry(messages)
    
    async def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Send a prompt expecting a JSON response and parse it.
        
        This method sends a chat completion request to the LLM and parses
        the response as JSON. It implements exponential backoff retry logic
        for transient errors.
        
        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt to set context.
        
        Returns:
            The parsed JSON response as a dictionary.
        
        Raises:
            LLMUnavailableError: If the LLM service is unavailable after
                all retry attempts are exhausted.
            LLMParsingError: If the LLM response is not valid JSON.
        
        Example:
            >>> data = await client.complete_json(
            ...     prompt="Return the claims as JSON array",
            ...     system_prompt="You are a JSON-only responder."
            ... )
            >>> print(data)
            {"claims": [...]}
        
        Requirements: 12.3, 14.3
        """
        response_text = await self.complete(prompt, system_prompt)
        
        try:
            # Try to parse the response as JSON
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from markdown code blocks if present
            extracted = self._extract_json_from_response(response_text)
            if extracted is not None:
                return extracted
            
            logger.error(
                f"Failed to parse LLM response as JSON: {e}. "
                f"Response (first 500 chars): {response_text[:500]}"
            )
            raise LLMParsingError(
                f"LLM response is not valid JSON: {e}. "
                f"Response preview: {response_text[:200]}..."
            ) from e
    
    def _extract_json_from_response(self, response_text: str) -> dict[str, Any] | None:
        """Attempt to extract JSON from a response that may contain markdown.
        
        LLMs sometimes wrap JSON in markdown code blocks. This method attempts
        to extract and parse JSON from such responses.
        
        Args:
            response_text: The raw response text from the LLM.
        
        Returns:
            The parsed JSON dictionary if extraction succeeds, None otherwise.
        """
        # Try to find JSON in markdown code blocks
        import re
        
        # Pattern for ```json ... ``` or ``` ... ```
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        
        return None
    
    async def _execute_with_retry(self, messages: list[dict[str, str]]) -> str:
        """Execute an API call with exponential backoff retry logic.
        
        This method implements the retry strategy:
        - Base delay: 1 second
        - Backoff multiplier: 2x
        - Max delay: 10 seconds
        - Retryable errors: timeout, connection errors, 429, 500, 502, 503
        
        Args:
            messages: The list of chat messages to send.
        
        Returns:
            The text content of the LLM's response.
        
        Raises:
            LLMUnavailableError: If all retry attempts are exhausted.
        """
        last_exception: Exception | None = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                )
                
                # Extract the response content
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
                
                # Empty response - treat as an error
                logger.warning("LLM returned empty response")
                return ""
                
            except APITimeoutError as e:
                last_exception = e
                logger.warning(
                    f"LLM API timeout on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                )
                
            except APIConnectionError as e:
                last_exception = e
                logger.warning(
                    f"LLM API connection error on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                )
                
            except RateLimitError as e:
                last_exception = e
                logger.warning(
                    f"LLM API rate limit (429) on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                )
                
            except APIStatusError as e:
                last_exception = e
                
                # Check if this is a retryable status code
                if e.status_code in self.RETRYABLE_STATUS_CODES:
                    logger.warning(
                        f"LLM API error {e.status_code} on attempt "
                        f"{attempt + 1}/{self.max_retries + 1}: {e}"
                    )
                else:
                    # Non-retryable error - raise immediately
                    logger.error(f"LLM API non-retryable error {e.status_code}: {e}")
                    raise LLMUnavailableError(
                        f"LLM service returned non-retryable error: {e.status_code}"
                    ) from e
            
            except Exception as e:
                # Unexpected error - log and raise
                logger.error(f"Unexpected error calling LLM API: {e}")
                raise LLMUnavailableError(
                    f"Unexpected error communicating with LLM service: {e}"
                ) from e
            
            # If we have more retries, wait with exponential backoff
            if attempt < self.max_retries:
                delay = min(
                    self.BASE_DELAY_SECONDS * (self.BACKOFF_MULTIPLIER ** attempt),
                    self.MAX_DELAY_SECONDS
                )
                logger.info(f"Retrying LLM API call in {delay:.1f} seconds...")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(
            f"LLM API unavailable after {self.max_retries + 1} attempts. "
            f"Last error: {last_exception}"
        )
        raise LLMUnavailableError(
            f"LLM service unavailable after {self.max_retries + 1} attempts. "
            f"Last error: {last_exception}"
        ) from last_exception
