"""Unit tests for response parser."""

import json
import pytest

from src.infrastructure.ai.response_parser import (
    CategorizationResponseParser,
    CategorizationResult,
    ResponseParserError,
)


class TestCategorizationResponseParser:
    """Test suite for CategorizationResponseParser."""

    @pytest.fixture
    def parser(self):
        """Create ResponseParser instance."""
        return CategorizationResponseParser()

    def test_init_loads_categories(self, parser):
        """Test that initialization loads valid categories."""
        assert len(parser.valid_categories) > 0
        assert "FOOD & GROCERIES" in parser.valid_categories
        assert "TRANSPORTATION" in parser.valid_categories

    def test_parse_category_response_valid(self, parser):
        """Test parsing valid category response."""
        response = '{"category": "FOOD & GROCERIES", "confidence": 0.95}'

        result = parser.parse_category_response(response)

        assert result.category == "FOOD & GROCERIES"
        assert result.subcategory is None
        assert result.confidence == 0.95
        assert result.raw_response == response

    def test_parse_category_response_with_extra_text(self, parser):
        """Test parsing response with extra text around JSON."""
        response = 'Here is the categorization: {"category": "TRANSPORTATION", "confidence": 0.88}'

        result = parser.parse_category_response(response)

        assert result.category == "TRANSPORTATION"
        assert result.confidence == 0.88

    def test_parse_category_response_case_insensitive(self, parser):
        """Test parsing with different case."""
        response = '{"category": "food & groceries", "confidence": 0.90}'

        result = parser.parse_category_response(response)

        assert result.category == "FOOD & GROCERIES"  # Corrected to proper case

    def test_parse_category_response_invalid_json(self, parser):
        """Test parsing invalid JSON."""
        response = "This is not valid JSON"

        result = parser.parse_category_response(response)

        # Should fallback to Miscellaneous
        assert result.category == "Miscellaneous"
        assert result.confidence == 0.0

    def test_parse_category_response_missing_confidence(self, parser):
        """Test parsing response without confidence."""
        response = '{"category": "FOOD & GROCERIES"}'

        result = parser.parse_category_response(response)

        assert result.category == "FOOD & GROCERIES"
        assert result.confidence == 0.5  # Default

    def test_parse_category_response_confidence_clamping(self, parser):
        """Test that confidence is clamped to [0, 1]."""
        # Test upper bound
        response1 = '{"category": "FOOD & GROCERIES", "confidence": 1.5}'
        result1 = parser.parse_category_response(response1)
        assert result1.confidence == 1.0

        # Test lower bound
        response2 = '{"category": "FOOD & GROCERIES", "confidence": -0.5}'
        result2 = parser.parse_category_response(response2)
        assert result2.confidence == 0.0

    def test_parse_subcategory_response_valid(self, parser):
        """Test parsing valid subcategory response."""
        response = '{"subcategory": "Groceries", "confidence": 0.92}'
        category = "FOOD & GROCERIES"

        result = parser.parse_subcategory_response(response, category)

        assert result.category == category
        assert result.subcategory == "Groceries"
        assert result.confidence == 0.92

    def test_parse_subcategory_response_invalid_subcategory(self, parser):
        """Test parsing with invalid subcategory."""
        response = '{"subcategory": "InvalidSubcategory", "confidence": 0.90}'
        category = "FOOD & GROCERIES"

        result = parser.parse_subcategory_response(response, category)

        # Should fallback to first subcategory of category
        assert result.category == category
        assert result.subcategory is not None
        assert result.confidence == 0.3  # Low confidence due to fallback

    def test_parse_full_response_valid(self, parser):
        """Test parsing full categorization response."""
        response = '{"category": "FOOD & GROCERIES", "subcategory": "Groceries", "confidence": 0.93}'

        result = parser.parse_full_response(response)

        assert result.category == "FOOD & GROCERIES"
        assert result.subcategory == "Groceries"
        assert result.confidence == 0.93

    def test_parse_full_response_invalid(self, parser):
        """Test parsing invalid full response."""
        response = "Invalid response"

        result = parser.parse_full_response(response)

        # Should fallback completely
        assert result.category == "Miscellaneous"
        assert result.subcategory == "Uncategorized"
        assert result.confidence == 0.0

    def test_parse_batch_response_valid(self, parser):
        """Test parsing valid batch response."""
        response = '''[
            {"id": 1, "category": "FOOD & GROCERIES", "confidence": 0.95},
            {"id": 2, "category": "TRANSPORTATION", "confidence": 0.88}
        ]'''

        results = parser.parse_batch_response(response, transaction_count=2)

        assert len(results) == 2
        assert results[0].category == "FOOD & GROCERIES"
        assert results[0].confidence == 0.95
        assert results[1].category == "TRANSPORTATION"
        assert results[1].confidence == 0.88

    def test_parse_batch_response_not_array(self, parser):
        """Test parsing batch response that's not an array."""
        response = '{"category": "FOOD & GROCERIES", "confidence": 0.95}'

        results = parser.parse_batch_response(response, transaction_count=3)

        # Should fallback to generic results
        assert len(results) == 3
        assert all(r.category == "Miscellaneous" for r in results)
        assert all(r.confidence == 0.0 for r in results)

    def test_parse_batch_response_invalid_json(self, parser):
        """Test parsing invalid batch JSON."""
        response = "Not valid JSON"

        results = parser.parse_batch_response(response, transaction_count=2)

        # Should fallback to generic results
        assert len(results) == 2
        assert all(r.category == "Miscellaneous" for r in results)

    def test_validate_category_exact_match(self, parser):
        """Test category validation with exact match."""
        result = parser._validate_category("FOOD & GROCERIES")
        assert result == "FOOD & GROCERIES"

    def test_validate_category_case_insensitive_match(self, parser):
        """Test category validation with case-insensitive match."""
        result = parser._validate_category("food & groceries")
        assert result == "FOOD & GROCERIES"

    def test_validate_category_partial_match(self, parser):
        """Test category validation with partial match."""
        result = parser._validate_category("FOOD")
        assert result == "FOOD & GROCERIES"

    def test_validate_category_invalid(self, parser):
        """Test category validation with invalid category."""
        result = parser._validate_category("INVALID_CATEGORY")
        assert result == "Miscellaneous"

    def test_validate_subcategory_exact_match(self, parser):
        """Test subcategory validation with exact match."""
        result = parser._validate_subcategory("FOOD & GROCERIES", "Groceries")
        assert result == "Groceries"

    def test_validate_subcategory_case_insensitive_match(self, parser):
        """Test subcategory validation with case-insensitive match."""
        result = parser._validate_subcategory("FOOD & GROCERIES", "groceries")
        assert result == "Groceries"

    def test_validate_subcategory_partial_match(self, parser):
        """Test subcategory validation with partial match."""
        # This depends on actual subcategories available
        result = parser._validate_subcategory("FOOD & GROCERIES", "Groc")
        # Should match to "Groceries" if it exists
        assert result is not None

    def test_validate_subcategory_invalid(self, parser):
        """Test subcategory validation with invalid subcategory."""
        result = parser._validate_subcategory("FOOD & GROCERIES", "InvalidSubcat")
        # Should return fallback subcategory
        assert result is not None

    def test_validate_subcategory_empty(self, parser):
        """Test subcategory validation with empty string."""
        result = parser._validate_subcategory("FOOD & GROCERIES", "")
        assert result is None

    def test_extract_json_direct_parse(self, parser):
        """Test JSON extraction with direct parsing."""
        response = '{"category": "FOOD & GROCERIES", "confidence": 0.95}'

        result = parser._extract_json(response)

        assert result["category"] == "FOOD & GROCERIES"
        assert result["confidence"] == 0.95

    def test_extract_json_with_extra_text_before(self, parser):
        """Test JSON extraction with text before JSON."""
        response = 'Here is the result: {"category": "TRANSPORTATION", "confidence": 0.88}'

        result = parser._extract_json(response)

        assert result["category"] == "TRANSPORTATION"

    def test_extract_json_with_extra_text_after(self, parser):
        """Test JSON extraction with text after JSON."""
        response = '{"category": "FOOD & GROCERIES", "confidence": 0.95} This is the end.'

        result = parser._extract_json(response)

        assert result["category"] == "FOOD & GROCERIES"

    def test_extract_json_array(self, parser):
        """Test JSON extraction with array."""
        response = '[{"id": 1, "category": "FOOD & GROCERIES"}]'

        result = parser._extract_json(response)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_extract_json_invalid(self, parser):
        """Test JSON extraction with invalid JSON."""
        response = "This is not JSON at all"

        with pytest.raises(json.JSONDecodeError):
            parser._extract_json(response)

    def test_get_fallback_subcategory(self, parser):
        """Test getting fallback subcategory."""
        fallback = parser._get_fallback_subcategory("FOOD & GROCERIES")

        assert fallback is not None
        assert isinstance(fallback, str)

    def test_get_fallback_subcategory_invalid_category(self, parser):
        """Test getting fallback subcategory for invalid category."""
        fallback = parser._get_fallback_subcategory("INVALID_CATEGORY")

        assert fallback is None


class TestCategorizationResult:
    """Test suite for CategorizationResult dataclass."""

    def test_create_result(self):
        """Test creating CategorizationResult."""
        result = CategorizationResult(
            category="FOOD & GROCERIES",
            subcategory="Groceries",
            confidence=0.95,
            raw_response='{"test": "data"}'
        )

        assert result.category == "FOOD & GROCERIES"
        assert result.subcategory == "Groceries"
        assert result.confidence == 0.95
        assert result.raw_response == '{"test": "data"}'

    def test_create_result_without_subcategory(self):
        """Test creating result without subcategory."""
        result = CategorizationResult(
            category="FOOD & GROCERIES",
            subcategory=None,
            confidence=0.90,
            raw_response="{}"
        )

        assert result.subcategory is None
