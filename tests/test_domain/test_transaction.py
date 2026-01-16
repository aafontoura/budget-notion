"""Tests for Transaction domain entity."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.entities import Transaction


def test_transaction_creation():
    """Test creating a valid transaction."""
    transaction = Transaction(
        date=datetime(2026, 1, 15),
        description="Test transaction",
        amount=Decimal("-50.00"),
        category="Food & Dining",
    )

    assert transaction.description == "Test transaction"
    assert transaction.amount == Decimal("-50.00")
    assert transaction.category == "Food & Dining"
    assert transaction.is_expense is True
    assert transaction.is_income is False


def test_transaction_with_invalid_description():
    """Test that empty description raises ValueError."""
    with pytest.raises(ValueError, match="description cannot be empty"):
        Transaction(
            date=datetime.now(),
            description="",
            amount=Decimal("-10.00"),
            category="Test",
        )


def test_transaction_with_invalid_category():
    """Test that empty category raises ValueError."""
    with pytest.raises(ValueError, match="category cannot be empty"):
        Transaction(
            date=datetime.now(),
            description="Test",
            amount=Decimal("-10.00"),
            category="",
        )


def test_transaction_is_income():
    """Test income transaction detection."""
    transaction = Transaction(
        date=datetime.now(),
        description="Salary",
        amount=Decimal("3000.00"),
        category="Income",
    )

    assert transaction.is_income is True
    assert transaction.is_expense is False


def test_transaction_needs_review():
    """Test needs_review property."""
    # Low confidence, not reviewed
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        ai_confidence=0.5,
        reviewed=False,
    )
    assert transaction.needs_review is True

    # High confidence, not reviewed
    transaction2 = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        ai_confidence=0.9,
        reviewed=False,
    )
    assert transaction2.needs_review is False


def test_transaction_mark_as_reviewed():
    """Test marking transaction as reviewed."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        reviewed=False,
    )

    reviewed_transaction = transaction.mark_as_reviewed()

    assert reviewed_transaction.reviewed is True
    assert transaction.reviewed is False  # Original unchanged (immutable)


def test_transaction_update_category():
    """Test updating transaction category."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Old Category",
    )

    updated_transaction = transaction.update_category("New Category", confidence=0.95)

    assert updated_transaction.category == "New Category"
    assert updated_transaction.ai_confidence == 0.95
    assert transaction.category == "Old Category"  # Original unchanged


def test_transaction_anonymize():
    """Test transaction anonymization for logging."""
    transaction = Transaction(
        date=datetime.now(),
        description="Sensitive merchant name",
        amount=Decimal("-50.00"),
        category="Shopping",
        notes="Secret note",
    )

    anonymized = transaction.anonymize()

    assert anonymized.description == "[REDACTED]"
    assert anonymized.notes is None
    assert anonymized.amount == transaction.amount  # Amount preserved
    assert anonymized.category == transaction.category  # Category preserved
