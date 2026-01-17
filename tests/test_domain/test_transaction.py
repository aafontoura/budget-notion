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


# Tag Tests
def test_transaction_with_tags():
    """Test creating transaction with tags."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car", "fixed-expense"],
    )

    assert len(transaction.tags) == 2
    assert "car" in transaction.tags
    assert "fixed-expense" in transaction.tags


def test_transaction_tags_normalized_to_lowercase():
    """Test that tags are normalized to lowercase."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["CAR", "Fixed-Expense", "  Baby  "],
    )

    assert "car" in transaction.tags
    assert "fixed-expense" in transaction.tags
    assert "baby" in transaction.tags
    assert "CAR" not in transaction.tags


def test_transaction_has_tag():
    """Test has_tag method."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car", "fixed-expense"],
    )

    assert transaction.has_tag("car") is True
    assert transaction.has_tag("CAR") is True  # Case-insensitive
    assert transaction.has_tag("bike") is False


def test_transaction_add_tag():
    """Test adding a tag to transaction."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car"],
    )

    updated = transaction.add_tag("fixed-expense")

    assert "fixed-expense" in updated.tags
    assert "car" in updated.tags
    assert "car" in transaction.tags  # Original unchanged
    assert "fixed-expense" not in transaction.tags


def test_transaction_add_duplicate_tag():
    """Test adding a duplicate tag (should be no-op)."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car"],
    )

    updated = transaction.add_tag("car")

    assert len(updated.tags) == 1
    assert updated.tags == transaction.tags


def test_transaction_remove_tag():
    """Test removing a tag from transaction."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car", "fixed-expense"],
    )

    updated = transaction.remove_tag("car")

    assert "car" not in updated.tags
    assert "fixed-expense" in updated.tags
    assert "car" in transaction.tags  # Original unchanged


def test_transaction_remove_nonexistent_tag():
    """Test removing a tag that doesn't exist (should be no-op)."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-10.00"),
        category="Test",
        tags=["car"],
    )

    updated = transaction.remove_tag("bike")

    assert updated.tags == transaction.tags


# Reimbursement Tests
def test_transaction_reimbursable():
    """Test creating reimbursable transaction."""
    from src.domain.entities.transaction import ReimbursementStatus

    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
    )

    assert transaction.reimbursable is True
    assert transaction.expected_reimbursement == Decimal("50.00")
    assert transaction.actual_reimbursement == Decimal("0")
    assert transaction.reimbursement_status == ReimbursementStatus.PENDING


def test_transaction_reimbursement_validation():
    """Test reimbursement amount validation."""
    with pytest.raises(ValueError, match="Expected reimbursement cannot be negative"):
        Transaction(
            date=datetime.now(),
            description="Test",
            amount=Decimal("-100.00"),
            category="Test",
            expected_reimbursement=Decimal("-10.00"),
        )


def test_transaction_reimbursement_exceeds_amount():
    """Test that actual reimbursement cannot exceed transaction amount."""
    with pytest.raises(ValueError, match="Actual reimbursement cannot exceed transaction amount"):
        Transaction(
            date=datetime.now(),
            description="Test",
            amount=Decimal("-100.00"),
            category="Test",
            actual_reimbursement=Decimal("150.00"),
        )


def test_transaction_update_reimbursement():
    """Test updating reimbursement amount."""
    from src.domain.entities.transaction import ReimbursementStatus

    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
    )

    updated = transaction.update_reimbursement(Decimal("50.00"))

    assert updated.actual_reimbursement == Decimal("50.00")
    assert updated.reimbursement_status == ReimbursementStatus.COMPLETE
    assert transaction.actual_reimbursement == Decimal("0")  # Original unchanged


def test_transaction_partial_reimbursement():
    """Test partial reimbursement status."""
    from src.domain.entities.transaction import ReimbursementStatus

    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
    )

    updated = transaction.update_reimbursement(Decimal("25.00"))

    assert updated.actual_reimbursement == Decimal("25.00")
    assert updated.reimbursement_status == ReimbursementStatus.PARTIAL


def test_transaction_net_amount():
    """Test net amount calculation with reimbursement."""
    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
        actual_reimbursement=Decimal("30.00"),
    )

    # Net = -100 + 30 = -70
    assert transaction.net_amount == Decimal("-70.00")


def test_transaction_is_fully_reimbursed():
    """Test is_fully_reimbursed property."""
    from src.domain.entities.transaction import ReimbursementStatus

    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
        actual_reimbursement=Decimal("50.00"),
        reimbursement_status=ReimbursementStatus.COMPLETE,
    )

    assert transaction.is_fully_reimbursed is True


def test_transaction_pending_reimbursement():
    """Test pending reimbursement calculation."""
    transaction = Transaction(
        date=datetime.now(),
        description="Group dinner",
        amount=Decimal("-100.00"),
        category="Food & Dining",
        reimbursable=True,
        expected_reimbursement=Decimal("50.00"),
        actual_reimbursement=Decimal("20.00"),
    )

    assert transaction.pending_reimbursement == Decimal("30.00")


def test_transaction_auto_reimbursement_status_none():
    """Test auto-calculation of reimbursement status when not reimbursable."""
    from src.domain.entities.transaction import ReimbursementStatus

    transaction = Transaction(
        date=datetime.now(),
        description="Grocery shopping",
        amount=Decimal("-50.00"),
        category="Food & Dining",
        reimbursable=False,
    )

    assert transaction.reimbursement_status == ReimbursementStatus.NONE
