"""Unit tests for categorization service."""

import pytest
from unittest.mock import Mock, MagicMock

from src.application.services.categorization_service import CategorizationService
from src.infrastructure.ai.response_parser import CategorizationResult
from src.infrastructure.ai.ollama_client import OllamaError


class TestCategorizationService:
    """Test suite for CategorizationService."""

    @pytest.fixture
    def mock_ollama_client(self):
        """Create mock Ollama client."""
        return Mock()

    @pytest.fixture
    def mock_prompt_builder(self):
        """Create mock prompt builder."""
        return Mock()

    @pytest.fixture
    def mock_response_parser(self):
        """Create mock response parser."""
        return Mock()

    @pytest.fixture
    def service(self, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Create CategorizationService instance."""
        return CategorizationService(
            ollama_client=mock_ollama_client,
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            batch_size=5,
            confidence_threshold=0.9
        )

    def test_init(self, service):
        """Test service initialization."""
        assert service.batch_size == 5
        assert service.confidence_threshold == 0.9

    def test_categorize_single_success(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test successful single transaction categorization."""
        transaction = {
            "date": "2025-01-19",
            "description": "Albert Heijn",
            "amount": "-50.00"
        }

        # Mock category step
        mock_prompt_builder.build_category_prompt.return_value = "category prompt"
        mock_ollama_client.generate.return_value = '{"category": "FOOD & GROCERIES", "confidence": 0.95}'
        category_result = CategorizationResult(
            category="FOOD & GROCERIES",
            subcategory=None,
            confidence=0.95,
            raw_response='{"category": "FOOD & GROCERIES", "confidence": 0.95}'
        )
        mock_response_parser.parse_category_response.return_value = category_result

        # Mock subcategory step
        mock_prompt_builder.build_subcategory_prompt.return_value = "subcategory prompt"
        mock_ollama_client.generate.return_value = '{"subcategory": "Groceries", "confidence": 0.92}'
        final_result = CategorizationResult(
            category="FOOD & GROCERIES",
            subcategory="Groceries",
            confidence=0.92,
            raw_response='{"subcategory": "Groceries", "confidence": 0.92}'
        )
        mock_response_parser.parse_subcategory_response.return_value = final_result

        result = service.categorize_single(transaction)

        assert result.category == "FOOD & GROCERIES"
        assert result.subcategory == "Groceries"
        assert result.confidence == 0.92

        # Verify calls
        mock_prompt_builder.build_category_prompt.assert_called_once_with(transaction)
        mock_prompt_builder.build_subcategory_prompt.assert_called_once_with(transaction, "FOOD & GROCERIES")

    def test_categorize_single_ollama_error(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test single categorization with Ollama error."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "100.00"
        }

        mock_prompt_builder.build_category_prompt.return_value = "prompt"
        mock_ollama_client.generate.side_effect = OllamaError("Connection failed")

        result = service.categorize_single(transaction)

        # Should fallback to Miscellaneous
        assert result.category == "Miscellaneous"
        assert result.subcategory == "Uncategorized"
        assert result.confidence == 0.0

    def test_categorize_batch_success(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test successful batch categorization."""
        transactions = [
            {"date": "2025-01-19", "description": "Store 1", "amount": "-50.00"},
            {"date": "2025-01-18", "description": "Store 2", "amount": "-60.00"},
        ]

        # Mock batch category step
        mock_prompt_builder.build_batch_category_prompt.return_value = "batch prompt"
        mock_ollama_client.generate.return_value = '[{"id": 1, "category": "FOOD & GROCERIES"}]'
        batch_results = [
            CategorizationResult("FOOD & GROCERIES", None, 0.95, "{}"),
            CategorizationResult("TRANSPORTATION", None, 0.88, "{}"),
        ]
        mock_response_parser.parse_batch_response.return_value = batch_results

        # Mock subcategory steps
        mock_prompt_builder.build_subcategory_prompt.return_value = "subcat prompt"
        subcategory_results = [
            CategorizationResult("FOOD & GROCERIES", "Groceries", 0.92, "{}"),
            CategorizationResult("TRANSPORTATION", "Car Fuel", 0.85, "{}"),
        ]
        mock_response_parser.parse_subcategory_response.side_effect = subcategory_results

        results = service.categorize_batch(transactions)

        assert len(results) == 2
        assert results[0].category == "FOOD & GROCERIES"
        assert results[0].subcategory == "Groceries"
        assert results[1].category == "TRANSPORTATION"
        assert results[1].subcategory == "Car Fuel"

    def test_categorize_batch_empty(self, service):
        """Test batch categorization with empty list."""
        results = service.categorize_batch([])
        assert results == []

    def test_categorize_batch_with_batching(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test that batch categorization splits into chunks."""
        # Create 8 transactions (should be split into 2 batches of 5 and 3)
        transactions = [
            {"date": "2025-01-19", "description": f"Store {i}", "amount": "-50.00"}
            for i in range(8)
        ]

        # Mock batch responses
        mock_prompt_builder.build_batch_category_prompt.return_value = "batch prompt"
        batch_results = [
            CategorizationResult("FOOD & GROCERIES", None, 0.95, "{}") for _ in range(8)
        ]
        mock_response_parser.parse_batch_response.side_effect = [
            batch_results[:5],  # First batch
            batch_results[5:],  # Second batch
        ]

        # Mock subcategory responses
        mock_prompt_builder.build_subcategory_prompt.return_value = "subcat prompt"
        subcategory_results = [
            CategorizationResult("FOOD & GROCERIES", "Groceries", 0.92, "{}")
            for _ in range(8)
        ]
        mock_response_parser.parse_subcategory_response.side_effect = subcategory_results

        results = service.categorize_batch(transactions)

        assert len(results) == 8
        # Should have called batch categorization twice (2 batches)
        assert mock_prompt_builder.build_batch_category_prompt.call_count == 2

    def test_categorize_batch_ollama_error_fallback(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test batch categorization fallback on error."""
        transactions = [
            {"date": "2025-01-19", "description": "Store 1", "amount": "-50.00"},
        ]

        # Batch categorization fails
        mock_prompt_builder.build_batch_category_prompt.return_value = "batch prompt"
        mock_ollama_client.generate.side_effect = OllamaError("Connection failed")

        # Mock fallback to single categorization
        mock_prompt_builder.build_category_prompt.return_value = "category prompt"
        category_result = CategorizationResult("FOOD & GROCERIES", None, 0.95, "{}")
        mock_response_parser.parse_category_response.return_value = category_result

        mock_prompt_builder.build_subcategory_prompt.return_value = "subcat prompt"
        subcategory_result = CategorizationResult("FOOD & GROCERIES", "Groceries", 0.92, "{}")
        mock_response_parser.parse_subcategory_response.return_value = subcategory_result

        results = service.categorize_batch(transactions)

        # Should fallback and still return results
        assert len(results) == 1
        assert results[0].category == "FOOD & GROCERIES"

    def test_categorize_full_success(self, service, mock_ollama_client, mock_prompt_builder, mock_response_parser):
        """Test successful full categorization."""
        transaction = {
            "date": "2025-01-19",
            "description": "Albert Heijn",
            "amount": "-50.00"
        }

        mock_prompt_builder.build_full_categorization_prompt.return_value = "full prompt"
        mock_ollama_client.generate.return_value = '{"category": "FOOD & GROCERIES", "subcategory": "Groceries"}'
        full_result = CategorizationResult(
            category="FOOD & GROCERIES",
            subcategory="Groceries",
            confidence=0.93,
            raw_response="{}"
        )
        mock_response_parser.parse_full_response.return_value = full_result

        result = service.categorize_full(transaction)

        assert result.category == "FOOD & GROCERIES"
        assert result.subcategory == "Groceries"
        assert result.confidence == 0.93

    def test_categorize_full_ollama_error(self, service, mock_ollama_client, mock_prompt_builder):
        """Test full categorization with Ollama error."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "100.00"
        }

        mock_prompt_builder.build_full_categorization_prompt.return_value = "prompt"
        mock_ollama_client.generate.side_effect = OllamaError("Connection failed")

        result = service.categorize_full(transaction)

        assert result.category == "Miscellaneous"
        assert result.subcategory == "Uncategorized"
        assert result.confidence == 0.0

    def test_test_connection_success(self, service, mock_ollama_client):
        """Test successful connection test."""
        mock_ollama_client.test_connection.return_value = True

        result = service.test_connection()

        assert result is True
        mock_ollama_client.test_connection.assert_called_once()

    def test_test_connection_failure(self, service, mock_ollama_client):
        """Test failed connection test."""
        mock_ollama_client.test_connection.return_value = False

        result = service.test_connection()

        assert result is False
