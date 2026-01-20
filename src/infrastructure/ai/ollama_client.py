"""Ollama API client for LLM categorization."""

import logging
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Exception raised for Ollama API errors."""

    pass


class OllamaClient:
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

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate(self, prompt: str, is_batch: bool = False, **options) -> str:
        """
        Generate response from Ollama.

        Args:
            prompt: Input prompt.
            is_batch: Whether this is a batch request (adjusts parameters).
            **options: Additional options for generation (temperature, num_ctx, etc.).

        Returns:
            Generated response text.

        Raises:
            OllamaError: If generation fails or Ollama is not available.
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

            logger.debug(f"Sending request to Ollama: {self.base_url}/api/generate")
            logger.debug(f"Batch mode: {is_batch}, Payload options: {generation_options}")

            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )

            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.debug(f"Received response ({len(generated_text)} chars)")

            return generated_text

        except httpx.ConnectError as e:
            logger.error(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running on supermicro."
            )
            raise OllamaError(
                f"Ollama server not available at {self.base_url}. "
                "Check connection to supermicro."
            ) from e

        except httpx.TimeoutException as e:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise OllamaError(
                f"Ollama request timed out. Model might be slow."
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            raise OllamaError(f"Ollama API error: {e.response.text}") from e

        except Exception as e:
            logger.error(f"Unexpected Ollama error: {e}")
            raise OllamaError(f"Failed to generate response: {e}") from e

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
