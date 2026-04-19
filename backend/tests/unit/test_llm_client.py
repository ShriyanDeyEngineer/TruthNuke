"""Unit tests for the LLM Client.

Tests cover:
- Basic completion functionality
- JSON parsing and error handling
- Exponential backoff retry logic
- Error handling for various failure modes

Requirements: 12.3, 14.3
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openai import APITimeoutError, RateLimitError, APIStatusError, APIConnectionError

from app.services.llm_client import (
    LLMClient,
    LLMUnavailableError,
    LLMParsingError,
)


class TestLLMClientInit:
    """Tests for LLMClient initialization."""
    
    def test_init_with_valid_api_key(self):
        """Test that client initializes with valid API key."""
        client = LLMClient(api_key="sk-test-key")
        assert client.api_key == "sk-test-key"
        assert client.model == "gpt-4o-mini"
        assert client.timeout == 30.0
        assert client.max_retries == 3
    
    def test_init_with_custom_parameters(self):
        """Test that client accepts custom parameters."""
        client = LLMClient(
            api_key="sk-test-key",
            model="gpt-4",
            timeout=60.0,
            max_retries=5,
        )
        assert client.model == "gpt-4"
        assert client.timeout == 60.0
        assert client.max_retries == 5
    
    def test_init_strips_whitespace_from_api_key(self):
        """Test that whitespace is stripped from API key."""
        client = LLMClient(api_key="  sk-test-key  ")
        assert client.api_key == "sk-test-key"
    
    def test_init_raises_on_empty_api_key(self):
        """Test that empty API key raises ValueError."""
        with pytest.raises(ValueError, match="api_key is required"):
            LLMClient(api_key="")
    
    def test_init_raises_on_whitespace_only_api_key(self):
        """Test that whitespace-only API key raises ValueError."""
        with pytest.raises(ValueError, match="api_key is required"):
            LLMClient(api_key="   ")
    
    def test_init_raises_on_none_api_key(self):
        """Test that None API key raises ValueError."""
        with pytest.raises(ValueError, match="api_key is required"):
            LLMClient(api_key=None)


class TestLLMClientComplete:
    """Tests for LLMClient.complete() method."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return LLMClient(api_key="sk-test-key", max_retries=2)
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock OpenAI response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Test response"
        return response
    
    @pytest.mark.asyncio
    async def test_complete_returns_response_text(self, client, mock_response):
        """Test that complete() returns the response text."""
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.complete("Test prompt")
            assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, client, mock_response):
        """Test that complete() includes system prompt in messages."""
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await client.complete("User prompt", system_prompt="System prompt")
            
            # Verify messages include both system and user prompts
            call_args = mock_create.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "System prompt"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "User prompt"
    
    @pytest.mark.asyncio
    async def test_complete_without_system_prompt(self, client, mock_response):
        """Test that complete() works without system prompt."""
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await client.complete("User prompt")
            
            # Verify only user message is included
            call_args = mock_create.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_complete_strips_response_whitespace(self, client):
        """Test that complete() strips whitespace from response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "  Response with whitespace  \n"
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete("Test prompt")
            assert result == "Response with whitespace"
    
    @pytest.mark.asyncio
    async def test_complete_handles_empty_response(self, client):
        """Test that complete() handles empty response gracefully."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete("Test prompt")
            assert result == ""


class TestLLMClientCompleteJSON:
    """Tests for LLMClient.complete_json() method."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return LLMClient(api_key="sk-test-key", max_retries=0)
    
    @pytest.mark.asyncio
    async def test_complete_json_parses_valid_json(self, client):
        """Test that complete_json() parses valid JSON response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '{"key": "value", "number": 42}'
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete_json("Test prompt")
            assert result == {"key": "value", "number": 42}
    
    @pytest.mark.asyncio
    async def test_complete_json_parses_json_array(self, client):
        """Test that complete_json() parses JSON array response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '[{"id": 1}, {"id": 2}]'
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete_json("Test prompt")
            assert result == [{"id": 1}, {"id": 2}]
    
    @pytest.mark.asyncio
    async def test_complete_json_extracts_from_markdown_code_block(self, client):
        """Test that complete_json() extracts JSON from markdown code blocks."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '''Here is the JSON:
```json
{"extracted": true}
```
'''
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete_json("Test prompt")
            assert result == {"extracted": True}
    
    @pytest.mark.asyncio
    async def test_complete_json_extracts_from_plain_code_block(self, client):
        """Test that complete_json() extracts JSON from plain code blocks."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '''```
{"plain": "block"}
```'''
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await client.complete_json("Test prompt")
            assert result == {"plain": "block"}
    
    @pytest.mark.asyncio
    async def test_complete_json_raises_on_invalid_json(self, client):
        """Test that complete_json() raises LLMParsingError on invalid JSON."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "This is not JSON at all"
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            with pytest.raises(LLMParsingError, match="not valid JSON"):
                await client.complete_json("Test prompt")
    
    @pytest.mark.asyncio
    async def test_complete_json_raises_on_malformed_json(self, client):
        """Test that complete_json() raises LLMParsingError on malformed JSON."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '{"key": "value", missing_quotes: true}'
        
        with patch.object(
            client._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            with pytest.raises(LLMParsingError):
                await client.complete_json("Test prompt")


class TestLLMClientRetryLogic:
    """Tests for LLMClient retry logic with exponential backoff."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with 2 retries."""
        return LLMClient(api_key="sk-test-key", max_retries=2)
    
    @pytest.fixture
    def mock_success_response(self):
        """Create a mock successful response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Success"
        return response
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client, mock_success_response):
        """Test that client retries on timeout error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APITimeoutError(request=MagicMock())
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
                assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_429(self, client, mock_success_response):
        """Test that client retries on 429 rate limit error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
                assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, client, mock_success_response):
        """Test that client retries on 500 server error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIStatusError(
                    message="Internal server error",
                    response=MagicMock(status_code=500),
                    body=None,
                )
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
                assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_502_error(self, client, mock_success_response):
        """Test that client retries on 502 bad gateway error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIStatusError(
                    message="Bad gateway",
                    response=MagicMock(status_code=502),
                    body=None,
                )
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
    
    @pytest.mark.asyncio
    async def test_retry_on_503_error(self, client, mock_success_response):
        """Test that client retries on 503 service unavailable error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIStatusError(
                    message="Service unavailable",
                    response=MagicMock(status_code=503),
                    body=None,
                )
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
    
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, client, mock_success_response):
        """Test that client retries on connection error."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIConnectionError(request=MagicMock())
            return mock_success_response
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete("Test")
                assert result == "Success"
                assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_raises_after_max_retries_exhausted(self, client):
        """Test that client raises LLMUnavailableError after max retries."""
        async def mock_create(*args, **kwargs):
            raise APITimeoutError(request=MagicMock())
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(LLMUnavailableError, match="unavailable after 3 attempts"):
                    await client.complete("Test")
    
    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self, client):
        """Test that client does not retry on 400 bad request error."""
        async def mock_create(*args, **kwargs):
            raise APIStatusError(
                message="Bad request",
                response=MagicMock(status_code=400),
                body=None,
            )
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with pytest.raises(LLMUnavailableError, match="non-retryable error"):
                await client.complete("Test")
    
    @pytest.mark.asyncio
    async def test_no_retry_on_401_error(self, client):
        """Test that client does not retry on 401 unauthorized error."""
        async def mock_create(*args, **kwargs):
            raise APIStatusError(
                message="Unauthorized",
                response=MagicMock(status_code=401),
                body=None,
            )
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with pytest.raises(LLMUnavailableError, match="non-retryable error"):
                await client.complete("Test")
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, client, mock_success_response):
        """Test that retry delays follow exponential backoff pattern."""
        call_count = 0
        sleep_delays = []
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APITimeoutError(request=MagicMock())
            return mock_success_response
        
        async def mock_sleep(delay):
            sleep_delays.append(delay)
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                await client.complete("Test")
        
        # First retry: 1s * 2^0 = 1s
        # Second retry: 1s * 2^1 = 2s
        assert len(sleep_delays) == 2
        assert sleep_delays[0] == 1.0
        assert sleep_delays[1] == 2.0
    
    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that retry delay is capped at max delay."""
        # Create client with many retries to test max delay cap
        client = LLMClient(api_key="sk-test-key", max_retries=5)
        
        call_count = 0
        sleep_delays = []
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success"
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 6:
                raise APITimeoutError(request=MagicMock())
            return mock_response
        
        async def mock_sleep(delay):
            sleep_delays.append(delay)
        
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=mock_create,
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                await client.complete("Test")
        
        # Delays: 1, 2, 4, 8, 10 (capped at max 10s)
        assert sleep_delays == [1.0, 2.0, 4.0, 8.0, 10.0]


class TestLLMClientExceptions:
    """Tests for LLM client exception classes."""
    
    def test_llm_unavailable_error_message(self):
        """Test LLMUnavailableError has correct message."""
        error = LLMUnavailableError("Service down")
        assert str(error) == "Service down"
    
    def test_llm_parsing_error_message(self):
        """Test LLMParsingError has correct message."""
        error = LLMParsingError("Invalid JSON")
        assert str(error) == "Invalid JSON"
    
    def test_llm_unavailable_error_is_exception(self):
        """Test LLMUnavailableError is an Exception."""
        assert issubclass(LLMUnavailableError, Exception)
    
    def test_llm_parsing_error_is_exception(self):
        """Test LLMParsingError is an Exception."""
        assert issubclass(LLMParsingError, Exception)
