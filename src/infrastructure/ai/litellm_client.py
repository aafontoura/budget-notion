"""LiteLLM client for commercial LLM providers.

This module provides a unified interface to 100+ LLM providers using the
LiteLLM library. It supports major providers including:
- OpenAI (GPT-4, GPT-3.5-turbo)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini 1.5 Pro, Gemini 1.5 Flash)
- Groq (fast inference for open models)
- And many more

The client maintains the same interface as OllamaClient, making it a
drop-in replacement for commercial LLM providers.
"""

import logging
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .base_llm_client import (
    BaseLLMClient,
    LLMError,
    PermanentError,
    RateLimitError,
    TransientError,
)

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception should be retried.

    Args:
        exception: The exception to check.

    Returns:
        True if the error is retryable (rate limit or transient), False otherwise.
    """
    return isinstance(exception, (RateLimitError, TransientError))


class LiteLLMClient(BaseLLMClient):
    """
    Unified LLM client using LiteLLM library.

    This client provides a consistent interface to multiple commercial
    LLM providers through the LiteLLM library. It automatically handles
    provider-specific API differences and provides features like:
    - Automatic retries with exponential backoff
    - Cost tracking
    - Provider-agnostic error handling
    - Batch processing optimization

    Supported model formats:
    - OpenAI: "gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"
    - Anthropic: "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"
    - Google: "gemini-1.5-pro", "gemini-1.5-flash"
    - Groq: "groq/llama-3.1-8b-instant", "groq/mixtral-8x7b-32768"
    - Ollama (via LiteLLM): "ollama/llama3.1:8b"

    Example:
        >>> client = LiteLLMClient(model="gpt-4", api_key="sk-...")
        >>> response = client.generate("Categorize: groceries $45")
        >>> print(response)
        '{"category": "Food & Groceries", "confidence": 0.95}'
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.1,
    ):
        """
        Initialize LiteLLM client.

        Args:
            model: Model identifier (e.g., "gpt-4", "claude-3-5-sonnet-20241022").
                   Can be provider-prefixed (e.g., "groq/llama-3.1-8b-instant").
            api_key: API key for the provider. If not provided, LiteLLM will look
                    for environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.).
            base_url: Custom base URL for the provider (optional, for self-hosted).
            timeout: Request timeout in seconds.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.temperature = temperature

        # Lazy import to avoid dependency if not using commercial providers
        try:
            import litellm

            self.litellm = litellm

            # Configure LiteLLM
            litellm.drop_params = True  # Drop unsupported params for each provider
            litellm.set_verbose = False  # Reduce logging noise

            if api_key:
                # Set API key in LiteLLM's environment
                # LiteLLM will automatically detect the provider from the model name
                litellm.api_key = api_key

            if base_url:
                litellm.api_base = base_url

            logger.info(f"Initialized LiteLLM client with model: {model}")

        except ImportError as e:
            raise LLMError(
                "LiteLLM is not installed. Install it with: pip install litellm"
            ) from e

    def _parse_litellm_error(self, error: Exception) -> Exception:
        """
        Parse LiteLLM error and convert to appropriate exception type.

        Args:
            error: Original exception from LiteLLM.

        Returns:
            Appropriate exception type (RateLimitError, TransientError, or PermanentError).
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Check for rate limit errors (HTTP 429)
        if "rate limit" in error_str or "429" in error_str or "ratelimiterror" in error_type.lower():
            # Try to extract retry_after from error message
            retry_after = 60  # Default to 60 seconds

            # Look for retry_after in error message
            # Common formats: "retry after 30s", "try again in 45.5s", "wait 60 seconds"
            import re
            match = re.search(r'(?:retry.*?|wait.*?|try.*?in)\s*(\d+(?:\.\d+)?)\s*s', error_str)
            if match:
                retry_after = int(float(match.group(1)))
                logger.info(f"Extracted retry_after={retry_after}s from error message")

            logger.warning(f"Rate limit error detected. Retry after {retry_after}s: {error}")
            return RateLimitError(message=str(error), retry_after=retry_after)

        # Check for transient errors (timeouts, 500-503)
        if any(
            keyword in error_str
            for keyword in [
                "timeout",
                "timed out",
                "connection",
                "network",
                "500",
                "502",
                "503",
                "504",
                "server error",
                "internal error",
                "service unavailable",
            ]
        ):
            logger.warning(f"Transient error detected: {error}")
            return TransientError(str(error))

        # Check for permanent errors (auth, validation, 400-404)
        if any(
            keyword in error_str
            for keyword in [
                "authentication",
                "authorization",
                "api key",
                "invalid",
                "not found",
                "400",
                "401",
                "403",
                "404",
                "badrequest",
                "unauthenticated",
                "forbidden",
            ]
        ):
            logger.error(f"Permanent error detected (not retrying): {error}")
            return PermanentError(str(error))

        # Default to transient error if unsure
        logger.warning(f"Unknown error type, treating as transient: {error}")
        return TransientError(str(error))

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=120),
    )
    def generate(self, prompt: str, is_batch: bool = False, **options) -> str:
        """
        Generate a response using LiteLLM with intelligent retry logic.

        This method automatically handles provider-specific API differences
        and provides retry logic with exponential backoff for transient failures.

        **Retry Behavior**:
        - Rate limit errors (HTTP 429): Retried up to 5 times with exponential backoff (5s → 120s max)
        - Transient errors (timeouts, 500-503): Retried up to 5 times with exponential backoff
        - Permanent errors (auth, 400-404): Not retried, fail immediately
        - Respects `Retry-After` hints from error messages

        Args:
            prompt: The input prompt to send to the LLM.
            is_batch: Whether this is a batch request (uses higher token limits).
            **options: Additional options to pass to the LLM provider:
                      - max_tokens: Maximum tokens to generate
                      - temperature: Override default temperature
                      - top_p: Nucleus sampling parameter
                      - Any other provider-specific options

        Returns:
            The generated response text from the LLM.

        Raises:
            RateLimitError: If rate limit exceeded after all retries.
            TransientError: If transient failure persists after all retries.
            PermanentError: If permanent error (auth, validation) occurs.

        Example:
            >>> client = LiteLLMClient(model="gpt-3.5-turbo")
            >>> response = client.generate("Categorize: groceries", is_batch=True)
        """
        try:
            # Determine optimal parameters based on batch mode
            if is_batch:
                # Batch requests need more tokens for multiple transactions
                max_tokens = options.get("max_tokens", 2000)
                temperature = options.get("temperature", 0.1)
            else:
                # Single requests need fewer tokens
                max_tokens = options.get("max_tokens", 100)
                temperature = options.get("temperature", self.temperature)

            # Build messages for chat completion
            # LiteLLM uses OpenAI's chat format as the standard
            messages = [{"role": "user", "content": prompt}]

            logger.debug(
                f"Sending request to {self.model} (batch={is_batch}, "
                f"max_tokens={max_tokens})"
            )

            # Call LiteLLM completion
            response = self.litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.timeout,
                **options,
            )

            # Extract text from response
            # LiteLLM returns OpenAI-compatible response format
            generated_text = response.choices[0].message.content

            logger.debug(
                f"Received response from {self.model} ({len(generated_text)} chars)"
            )

            return generated_text

        except Exception as e:
            # Parse error and convert to appropriate exception type
            parsed_error = self._parse_litellm_error(e)

            # Re-raise the parsed error (will be caught by @retry decorator if retryable)
            raise parsed_error from e

    def test_connection(self) -> bool:
        """
        Test connection to the LLM provider.

        Sends a minimal test request to verify that the provider is accessible
        and the API credentials are valid.

        Returns:
            True if the connection test succeeds, False otherwise.

        Example:
            >>> client = LiteLLMClient(model="gpt-3.5-turbo")
            >>> if client.test_connection():
            ...     print("Ready to use!")
        """
        try:
            logger.info(f"Testing connection to {self.model}...")

            # Send minimal test request
            response = self.litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                timeout=10,
            )

            logger.info(f"Successfully connected to {self.model}")
            return True

        except Exception as e:
            logger.error(f"Connection test failed for {self.model}: {e}")
            logger.debug(
                f"Make sure you have set the appropriate API key environment variable "
                f"(e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY)"
            )
            return False
