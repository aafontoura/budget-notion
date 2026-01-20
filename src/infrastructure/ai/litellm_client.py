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
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base_llm_client import BaseLLMClient, LLMError

logger = logging.getLogger(__name__)


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

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate(self, prompt: str, is_batch: bool = False, **options) -> str:
        """
        Generate a response using LiteLLM.

        This method automatically handles provider-specific API differences
        and provides retry logic with exponential backoff for transient failures.

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
            LLMError: If the generation fails after all retries.

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
            logger.error(f"LiteLLM generation error: {e}")
            raise LLMError(f"Failed to generate response from {self.model}: {e}") from e

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
