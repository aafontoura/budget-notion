"""Ollama API client for LLM categorization."""

import logging
from typing import Optional

import httpx
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


class OllamaError(LLMError):
    """Exception raised for Ollama API errors."""

    pass


def _is_retryable_ollama_error(exception: Exception) -> bool:
    """
    Determine if an Ollama exception should be retried.

    Args:
        exception: The exception to check.

    Returns:
        True if the error is retryable, False otherwise.
    """
    return isinstance(exception, (RateLimitError, TransientError))


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama API.

    Connects to local Ollama server for transaction categorization.
    Optimized for Llama 3.1 8B model running on CPU.
    """

    def __init__(
        self,
        base_url: str = "http://supermicro:11434",
        model: str = "llama3.1:8b",
        timeout: int = 60,
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL (default: http://supermicro:11434).
            model: Model name (default: llama3.1:8b).
            timeout: Request timeout in seconds (default: 60).
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

        logger.info(f"Initialized Ollama client: {base_url} ({model})")

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def _parse_ollama_error(self, error: Exception, response: Optional[httpx.Response] = None) -> Exception:
        """
        Parse Ollama error and convert to appropriate exception type.

        Args:
            error: Original exception.
            response: HTTP response if available.

        Returns:
            Appropriate exception type.
        """
        # Check for rate limit (HTTP 429)
        if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
            # Extract retry_after from header
            retry_after = 60  # Default
            if "retry-after" in error.response.headers:
                try:
                    retry_after = int(error.response.headers["retry-after"])
                except ValueError:
                    pass

            logger.warning(f"Rate limit error. Retry after {retry_after}s")
            return RateLimitError(message=str(error), retry_after=retry_after)

        # Connection errors and timeouts are transient
        if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
            logger.warning(f"Transient error: {error}")
            return TransientError(str(error))

        # HTTP 500-503 errors are transient
        if isinstance(error, httpx.HTTPStatusError) and 500 <= error.response.status_code < 504:
            logger.warning(f"Server error (transient): {error.response.status_code}")
            return TransientError(str(error))

        # HTTP 400-404 errors are permanent
        if isinstance(error, httpx.HTTPStatusError) and 400 <= error.response.status_code < 500:
            logger.error(f"Client error (permanent): {error.response.status_code}")
            return PermanentError(str(error))

        # Unknown errors default to transient
        logger.warning(f"Unknown error type, treating as transient: {error}")
        return TransientError(str(error))

    @retry(
        retry=retry_if_exception(_is_retryable_ollama_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=120),
    )
    def generate(self, prompt: str, is_batch: bool = False, **options) -> str:
        """
        Generate response from Ollama with intelligent retry logic.

        **Retry Behavior**:
        - Rate limit errors (HTTP 429): Retried up to 5 times with exponential backoff (5s → 120s max)
        - Transient errors (timeouts, 500-503): Retried up to 5 times with exponential backoff
        - Permanent errors (auth, 400-404): Not retried, fail immediately
        - Respects `Retry-After` headers from Ollama

        Args:
            prompt: Input prompt.
            is_batch: Whether this is a batch request (adjusts parameters).
            **options: Additional options for generation (temperature, num_ctx, etc.).

        Returns:
            Generated response text.

        Raises:
            RateLimitError: If rate limit exceeded after all retries.
            TransientError: If transient failure persists after all retries.
            PermanentError: If permanent error occurs.
        """
        try:
            # Default options optimized for transaction categorization
            if is_batch:
                # Batch mode: larger context, controlled output size
                default_options = {
                    "temperature": 0.1,  # Deterministic
                    "num_ctx": 1536,  # Enough for 30-40 transactions
                    "num_predict": 2000,  # ~50 chars per transaction × 40 transactions
                    "num_thread": 6,  # Use CPU cores
                }
            else:
                # Single transaction mode
                default_options = {
                    "temperature": 0.1,  # Deterministic
                    "num_ctx": 1024,  # Smaller context
                    "num_predict": 50,  # Small JSON response
                    "num_thread": 6,  # Use CPU cores
                }

            # Merge with provided options
            generation_options = {**default_options, **options}

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": generation_options,
                "keep_alive": "30m",  # Keep model loaded during batch jobs
            }

            logger.info(f"🤖 Sending request to Ollama: {self.base_url}/api/generate")
            logger.info(f"   Model: {self.model} | Batch mode: {is_batch}")
            logger.info(f"   Options: {generation_options}")
            logger.debug("─" * 80)
            logger.debug("📤 PROMPT:")
            logger.debug(prompt[:500] + ("..." if len(prompt) > 500 else ""))
            logger.debug("─" * 80)

            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )

            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.debug("─" * 80)
            logger.debug(f"📥 RESPONSE ({len(generated_text)} chars):")
            logger.debug(generated_text[:500] + ("..." if len(generated_text) > 500 else ""))
            logger.debug("─" * 80)
            logger.info(f"✅ Response received: {len(generated_text)} characters")

            return generated_text

        except Exception as e:
            # Parse error and convert to appropriate exception type
            parsed_error = self._parse_ollama_error(e)

            # Re-raise the parsed error (will be caught by @retry decorator if retryable)
            raise parsed_error from e

    def test_connection(self) -> bool:
        """
        Test connection to Ollama server.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            logger.info("Successfully connected to Ollama")
            return True
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False

    def list_models(self) -> list[str]:
        """
        List available models on Ollama server.

        Returns:
            List of model names.
        """
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            result = response.json()
            models = result.get("models", [])

            model_names = [model.get("name") for model in models]
            logger.info(f"Available models: {model_names}")

            return model_names

        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []
