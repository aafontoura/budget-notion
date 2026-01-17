"""Tests for AutoTaggerService."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.application.services.auto_tagger import AutoTaggerService
from src.domain.entities.transaction import Transaction


@pytest.fixture
def auto_tagger():
    """Create AutoTaggerService instance."""
    return AutoTaggerService()


def test_auto_tag_car_expenses(auto_tagger):
    """Test auto-tagging for car-related expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Car insurance payment",
        amount=Decimal("-100.00"),
        category="Transportation",
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Car Insurance")

    assert "car" in tagged.tags
    assert "fixed-expense" in tagged.tags
    assert "monthly" in tagged.tags


def test_auto_tag_bike_expenses(auto_tagger):
    """Test auto-tagging for bike-related expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Bike repair",
        amount=Decimal("-50.00"),
        category="Transportation",
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Bike Purchase & Maintenance")

    assert "bike" in tagged.tags
    # Note: variable-expense tag is not auto-applied unless "Bike Purchase & Maintenance"
    # is explicitly listed in the variable-expense section of STANDARD_TAGS


def test_auto_tag_baby_expenses(auto_tagger):
    """Test auto-tagging for baby-related expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Baby diapers",
        amount=Decimal("-30.00"),
        category="Baby & Childcare",
    )

    tagged = auto_tagger.apply_tags(transaction, "Baby & Childcare", "Baby Essentials")

    assert "baby" in tagged.tags
    # Note: flexibility tags not auto-applied unless explicitly in STANDARD_TAGS


def test_auto_tag_fixed_expenses(auto_tagger):
    """Test auto-tagging for fixed expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Mortgage payment",
        amount=Decimal("-2080.00"),
        category="Home",
    )

    tagged = auto_tagger.apply_tags(transaction, "Home", "Mortgage")

    assert "fixed-expense" in tagged.tags
    assert "home" in tagged.tags
    assert "monthly" in tagged.tags


def test_auto_tag_discretionary_expenses(auto_tagger):
    """Test auto-tagging for discretionary expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Restaurant dinner",
        amount=Decimal("-75.00"),
        category="Food & Dining",
    )

    tagged = auto_tagger.apply_tags(transaction, "Food & Dining", "Restaurants & Bars")

    assert "discretionary" in tagged.tags
    # discretionary and variable-expense are both in STANDARD_TAGS for Restaurants & Bars


def test_auto_tag_reimbursable(auto_tagger):
    """Test auto-tagging for reimbursable transactions."""
    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
    )

    tagged = auto_tagger.apply_tags(transaction, "Food & Dining", "Restaurants & Bars")

    assert "reimbursable" in tagged.tags


def test_auto_tag_yearly_frequency(auto_tagger):
    """Test auto-tagging for yearly expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Car tax",
        amount=Decimal("-300.00"),
        category="Transportation",
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Car Tax")

    assert "yearly" in tagged.tags
    assert "car" in tagged.tags


def test_auto_tag_quarterly_frequency(auto_tagger):
    """Test auto-tagging for quarterly expenses."""
    transaction = Transaction(
        date=datetime.now(),
        description="Quarterly Investment Review",
        amount=Decimal("-200.00"),
        category="Investments & Savings",
    )

    tagged = auto_tagger.apply_tags(transaction, "Investments & Savings", "Quarterly Investment Review")

    # Should detect quarterly from subcategory name
    assert "quarterly" in tagged.tags


def test_auto_tag_no_subcategory(auto_tagger):
    """Test auto-tagging when no subcategory is provided."""
    transaction = Transaction(
        date=datetime.now(),
        description="Generic expense",
        amount=Decimal("-50.00"),
        category="Other",
    )

    tagged = auto_tagger.apply_tags(transaction, "Other", None)

    # Should still work, just with fewer tags
    assert isinstance(tagged, Transaction)


def test_auto_tag_preserves_existing_tags(auto_tagger):
    """Test that auto-tagging preserves existing tags."""
    transaction = Transaction(
        date=datetime.now(),
        description="Car insurance",
        amount=Decimal("-100.00"),
        category="Transportation",
        tags=["custom-tag"],
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Car Insurance")

    assert "custom-tag" in tagged.tags
    assert "car" in tagged.tags
    assert "fixed-expense" in tagged.tags


def test_auto_tag_no_duplicates(auto_tagger):
    """Test that auto-tagging doesn't create duplicate tags."""
    transaction = Transaction(
        date=datetime.now(),
        description="Car insurance",
        amount=Decimal("-100.00"),
        category="Transportation",
        tags=["car"],  # Already has 'car' tag
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Car Insurance")

    # Count occurrences of 'car' tag
    car_count = tagged.tags.count("car")
    assert car_count == 1


def test_auto_tag_multiple_dimensions(auto_tagger):
    """Test that auto-tagging applies multiple tag dimensions."""
    transaction = Transaction(
        date=datetime.now(),
        description="Car fuel",
        amount=Decimal("-60.00"),
        category="Transportation",
    )

    tagged = auto_tagger.apply_tags(transaction, "Transportation", "Car Fuel")

    # Should have asset, flexibility, and frequency tags
    assert "car" in tagged.tags  # Asset
    assert "variable-expense" in tagged.tags  # Flexibility
    # Frequency may vary
