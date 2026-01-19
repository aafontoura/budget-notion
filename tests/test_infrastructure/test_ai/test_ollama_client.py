"""Unit tests for Ollama client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx

from src.infrastructure.ai.ollama_client import OllamaClient, OllamaError


class TestOllamaClient:
    """Test suite for OllamaClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create mock httpx client."""
        with patch("src.infrastructure.ai.ollama_client.httpx.Client") as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def client(self, mock_httpx_client):
        """Create OllamaClient instance with mocked httpx."""
        return OllamaClient(
            base_url="http://test:11434",
            model="test-model",
            timeout=30
        )

    def test_init_default_values(self):
        """Test initialization with default values."""
        with patch("src.infrastructure.ai.ollama_client.httpx.Client"):
            client = OllamaClient()

            assert client.base_url == "http://supermicro:11434"
            assert client.model == "llama3.1:8b"
            assert client.timeout == 60

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        with patch("src.infrastructure.ai.ollama_client.httpx.Client"):
            client = OllamaClient(
                base_url="http://custom:8080",
                model="custom-model",
                timeout=120
            )

            assert client.base_url == "http://custom:8080"
            assert client.model == "custom-model"
            assert client.timeout == 120

    def test_init_strips_trailing_slash(self):
        """Test that base URL trailing slash is stripped."""
        with patch("src.infrastructure.ai.ollama_client.httpx.Client"):
            client = OllamaClient(base_url="http://test:11434/")
            assert client.base_url == "http://test:11434"

    def test_generate_success(self, client, mock_httpx_client):
        """Test successful generation."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"response": "Generated text"}
        mock_httpx_client.post.return_value = mock_response

        result = client.generate("Test prompt")

        assert result == "Generated text"
        mock_httpx_client.post.assert_called_once()

        # Verify request payload
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "http://test:11434/api/generate"
        payload = call_args[1]["json"]
        assert payload["model"] == "test-model"
        assert payload["prompt"] == "Test prompt"
        assert payload["stream"] is False
        assert "temperature" in payload["options"]

    def test_generate_with_custom_options(self, client, mock_httpx_client):
        """Test generation with custom options."""
        mock_response = Mock()
        mock_response.json.return_value = {"response": "Generated text"}
        mock_httpx_client.post.return_value = mock_response

        client.generate("Test prompt", temperature=0.5, num_ctx=4096)

        # Verify custom options are passed
        call_args = mock_httpx_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["options"]["temperature"] == 0.5
        assert payload["options"]["num_ctx"] == 4096

    def test_generate_default_options(self, client, mock_httpx_client):
        """Test that default options are applied."""
        mock_response = Mock()
        mock_response.json.return_value = {"response": "Generated text"}
        mock_httpx_client.post.return_value = mock_response

        client.generate("Test prompt")

        call_args = mock_httpx_client.post.call_args
        options = call_args[1]["json"]["options"]

        assert options["temperature"] == 0.1  # Deterministic
        assert options["num_ctx"] == 2048  # Small context
        assert options["num_predict"] == 200  # Limit output
        assert options["num_thread"] == 6  # CPU cores

    def test_generate_connection_error(self, client, mock_httpx_client):
        """Test generation with connection error."""
        mock_httpx_client.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(OllamaError, match="Ollama server not available"):
            client.generate("Test prompt")

    def test_generate_timeout_error(self, client, mock_httpx_client):
        """Test generation with timeout error."""
        mock_httpx_client.post.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(OllamaError, match="timed out"):
            client.generate("Test prompt")

    def test_generate_http_error(self, client, mock_httpx_client):
        """Test generation with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_httpx_client.post.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Error", request=Mock(), response=mock_response
        )

        with pytest.raises(OllamaError, match="Ollama API error"):
            client.generate("Test prompt")

    def test_generate_unexpected_error(self, client, mock_httpx_client):
        """Test generation with unexpected error."""
        mock_httpx_client.post.side_effect = ValueError("Unexpected error")

        with pytest.raises(OllamaError, match="Failed to generate response"):
            client.generate("Test prompt")

    def test_test_connection_success(self, client, mock_httpx_client):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        result = client.test_connection()

        assert result is True
        mock_httpx_client.get.assert_called_once_with("http://test:11434/api/tags")

    def test_test_connection_failure(self, client, mock_httpx_client):
        """Test failed connection test."""
        mock_httpx_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = client.test_connection()

        assert result is False

    def test_list_models_success(self, client, mock_httpx_client):
        """Test successful model listing."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
            ]
        }
        mock_httpx_client.get.return_value = mock_response

        models = client.list_models()

        assert len(models) == 2
        assert "llama3.1:8b" in models
        assert "mistral:7b" in models

    def test_list_models_failure(self, client, mock_httpx_client):
        """Test model listing failure."""
        mock_httpx_client.get.side_effect = httpx.ConnectError("Connection refused")

        models = client.list_models()

        assert models == []

    @patch("src.infrastructure.ai.ollama_client.httpx.Client")
    def test_cleanup_on_delete(self, mock_client_class):
        """Test that HTTP client is closed on deletion."""
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance

        client = OllamaClient()
        del client

        mock_client_instance.close.assert_called_once()


class TestOllamaClientRetry:
    """Test retry logic for OllamaClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create mock httpx client."""
        with patch("src.infrastructure.ai.ollama_client.httpx.Client") as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def client(self, mock_httpx_client):
        """Create OllamaClient instance."""
        return OllamaClient(base_url="http://test:11434")

    def test_retry_on_timeout(self, client, mock_httpx_client):
        """Test that requests are retried on timeout."""
        # First two calls timeout, third succeeds
        mock_response = Mock()
        mock_response.json.return_value = {"response": "Success"}

        mock_httpx_client.post.side_effect = [
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"),
            mock_response,
        ]

        result = client.generate("Test prompt")

        assert result == "Success"
        assert mock_httpx_client.post.call_count == 3

    def test_retry_exhausted(self, client, mock_httpx_client):
        """Test that retry gives up after max attempts."""
        mock_httpx_client.post.side_effect = httpx.TimeoutException("Persistent timeout")

        with pytest.raises(OllamaError):
            client.generate("Test prompt")

        # Should retry 3 times total (initial + 2 retries)
        assert mock_httpx_client.post.call_count == 3
