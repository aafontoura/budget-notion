"""Unit tests for prompt builder."""

import pytest

from src.infrastructure.ai.prompt_builder import CategorizationPromptBuilder


class TestCategorizationPromptBuilder:
    """Test suite for CategorizationPromptBuilder."""

    @pytest.fixture
    def builder(self):
        """Create PromptBuilder instance."""
        return CategorizationPromptBuilder()

    def test_init_loads_categories(self, builder):
        """Test that initialization loads categories."""
        assert len(builder.categories) > 0
        assert "FOOD & GROCERIES" in builder.categories
        assert "TRANSPORTATION" in builder.categories

    def test_init_loads_subcategories(self, builder):
        """Test that initialization loads subcategories."""
        assert len(builder.category_subcategories) > 0
        assert "FOOD & GROCERIES" in builder.category_subcategories
        assert len(builder.category_subcategories["FOOD & GROCERIES"]) > 0

    def test_build_category_prompt_basic(self, builder):
        """Test building basic category prompt."""
        transaction = {
            "date": "2025-01-19",
            "description": "Albert Heijn Supermarket",
            "amount": "-50.00"
        }

        prompt = builder.build_category_prompt(transaction)

        # Check that prompt contains key elements
        assert "Albert Heijn Supermarket" in prompt
        assert "-50.00" in prompt or "50.00" in prompt
        assert "2025-01-19" in prompt
        assert "FOOD & GROCERIES" in prompt
        assert "JSON" in prompt
        assert "category" in prompt
        assert "confidence" in prompt

    def test_build_category_prompt_includes_all_categories(self, builder):
        """Test that category prompt includes all categories."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "100.00"
        }

        prompt = builder.build_category_prompt(transaction)

        # Verify all main categories are included
        for category in builder.categories:
            assert category in prompt

    def test_build_subcategory_prompt_basic(self, builder):
        """Test building basic subcategory prompt."""
        transaction = {
            "date": "2025-01-19",
            "description": "Albert Heijn Supermarket",
            "amount": "-50.00"
        }
        category = "FOOD & GROCERIES"

        prompt = builder.build_subcategory_prompt(transaction, category)

        # Check that prompt contains key elements
        assert "Albert Heijn Supermarket" in prompt
        assert category in prompt
        assert "subcategory" in prompt
        assert "JSON" in prompt

    def test_build_subcategory_prompt_includes_relevant_subcategories(self, builder):
        """Test that subcategory prompt includes relevant subcategories."""
        transaction = {
            "date": "2025-01-19",
            "description": "Grocery shopping",
            "amount": "-50.00"
        }
        category = "FOOD & GROCERIES"

        prompt = builder.build_subcategory_prompt(transaction, category)

        # Verify relevant subcategories are included
        subcats = builder.category_subcategories[category]
        # At least some subcategories should be present (first 15)
        included_count = sum(1 for subcat in subcats[:15] if subcat in prompt)
        assert included_count > 0

    def test_build_subcategory_prompt_limits_subcategories(self, builder):
        """Test that subcategory prompt limits number of subcategories."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "100.00"
        }

        # Use a category with many subcategories
        category = "FOOD & GROCERIES"
        prompt = builder.build_subcategory_prompt(transaction, category)

        # Prompt should not be excessively long (rough check)
        # With 15 subcategories limit, prompt should be reasonable
        assert len(prompt) < 1000  # Reasonable limit

    def test_build_batch_category_prompt_single_transaction(self, builder):
        """Test building batch prompt with single transaction."""
        transactions = [
            {
                "date": "2025-01-19",
                "description": "Albert Heijn",
                "amount": "-50.00"
            }
        ]

        prompt = builder.build_batch_category_prompt(transactions)

        assert "Albert Heijn" in prompt
        assert "1." in prompt  # Transaction numbering
        assert "JSON array" in prompt

    def test_build_batch_category_prompt_multiple_transactions(self, builder):
        """Test building batch prompt with multiple transactions."""
        transactions = [
            {"date": "2025-01-19", "description": "Grocery Store", "amount": "-50.00"},
            {"date": "2025-01-18", "description": "Gas Station", "amount": "-60.00"},
            {"date": "2025-01-17", "description": "Restaurant", "amount": "-35.00"},
        ]

        prompt = builder.build_batch_category_prompt(transactions)

        # Check all transactions are included
        assert "Grocery Store" in prompt
        assert "Gas Station" in prompt
        assert "Restaurant" in prompt

        # Check numbering
        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt

    def test_build_full_categorization_prompt_basic(self, builder):
        """Test building full categorization prompt."""
        transaction = {
            "date": "2025-01-19",
            "description": "Albert Heijn Supermarket",
            "amount": "-50.00"
        }

        prompt = builder.build_full_categorization_prompt(transaction)

        # Check that prompt contains key elements
        assert "Albert Heijn Supermarket" in prompt
        assert "category" in prompt
        assert "subcategory" in prompt
        assert "JSON" in prompt

    def test_build_full_categorization_prompt_includes_mapping(self, builder):
        """Test that full prompt includes category-subcategory mapping."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "100.00"
        }

        prompt = builder.build_full_categorization_prompt(transaction)

        # Should include some categories with their subcategories
        # Limited to first 12 categories
        included_categories = sum(
            1 for cat in builder.categories[:12] if cat in prompt
        )
        assert included_categories > 0

    def test_get_category_subcategories(self, builder):
        """Test getting subcategories for a category."""
        subcats = builder.get_category_subcategories("FOOD & GROCERIES")

        assert len(subcats) > 0
        assert isinstance(subcats, list)

    def test_get_category_subcategories_invalid_category(self, builder):
        """Test getting subcategories for invalid category."""
        subcats = builder.get_category_subcategories("INVALID_CATEGORY")

        assert subcats == []

    def test_prompts_use_euro_symbol(self, builder):
        """Test that prompts use Euro symbol for amounts."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "50.00"
        }

        category_prompt = builder.build_category_prompt(transaction)
        subcategory_prompt = builder.build_subcategory_prompt(transaction, "FOOD & GROCERIES")
        full_prompt = builder.build_full_categorization_prompt(transaction)

        # All prompts should use € for amounts
        assert "€" in category_prompt
        assert "€" in subcategory_prompt
        assert "€" in full_prompt

    def test_prompts_include_examples(self, builder):
        """Test that prompts include example outputs."""
        transaction = {
            "date": "2025-01-19",
            "description": "Test",
            "amount": "50.00"
        }

        category_prompt = builder.build_category_prompt(transaction)
        subcategory_prompt = builder.build_subcategory_prompt(transaction, "FOOD & GROCERIES")

        # Prompts should include example JSON
        assert "Example:" in category_prompt
        assert "Example:" in subcategory_prompt
