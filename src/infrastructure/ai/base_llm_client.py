"""Abstract base class for LLM clients.

This module defines the interface that all LLM clients must implement,
enabling the application to work with different LLM providers (Ollama,
OpenAI, Anthropic, Google, etc.) through a unified interface.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Exception raised for LLM API errors."""

    pass


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.

    All LLM client implementations (Ollama, OpenAI, Anthropic, etc.)
    must inherit from this class and implement the required methods.

    This abstraction allows the CategorizationService to work with any
    LLM provider without modification.
    """

    @abstractmethod
    def generate(self, prompt: str, is_batch: bool = False, **options) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The input prompt to send to the LLM.
            is_batch: Whether this is a batch request (may affect token limits).
            **options: Provider-specific options (temperature, max_tokens, etc.).

        Returns:
            The generated response text from the LLM.

        Raises:
            LLMError: If the generation fails or the API is unavailable.

        Example:
            >>> client = SomeLLMClient()
            >>> response = client.generate("Categorize this transaction: groceries $45")
            >>> print(response)
            '{"category": "Food & Groceries", "confidence": 0.95}'
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the LLM provider.

        This method should perform a minimal request to verify that the
        LLM service is available and the configuration is correct.

        Returns:
            True if the connection is successful, False otherwise.

        Example:
            >>> client = SomeLLMClient()
            >>> if client.test_connection():
            ...     print("LLM is ready!")
            ... else:
            ...     print("LLM connection failed")
        """
        pass
