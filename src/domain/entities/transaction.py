"""Transaction domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Transaction:
    """
    Core transaction entity representing a financial transaction.

    This is a pure domain entity with no dependencies on infrastructure.
    Immutable after creation to ensure data integrity.
    """

    date: datetime
    description: str
    amount: Decimal
    category: str
    account: Optional[str] = None
    notes: Optional[str] = None
    reviewed: bool = False
    ai_confidence: Optional[float] = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate transaction data after initialization."""
        if not self.description or not self.description.strip():
            raise ValueError("Transaction description cannot be empty")

        if not self.category or not self.category.strip():
            raise ValueError("Transaction category cannot be empty")

        if self.ai_confidence is not None:
            if not 0.0 <= self.ai_confidence <= 1.0:
                raise ValueError("AI confidence must be between 0.0 and 1.0")

    def mark_as_reviewed(self) -> "Transaction":
        """
        Mark transaction as reviewed by user.

        Returns a new Transaction instance (immutable pattern).
        """
        return Transaction(
            id=self.id,
            date=self.date,
            description=self.description,
            amount=self.amount,
            category=self.category,
            account=self.account,
            notes=self.notes,
            reviewed=True,
            ai_confidence=self.ai_confidence,
            created_at=self.created_at,
            updated_at=datetime.now()
        )

    def update_category(self, new_category: str, confidence: Optional[float] = None) -> "Transaction":
        """
        Update transaction category.

        Returns a new Transaction instance (immutable pattern).
        """
        if not new_category or not new_category.strip():
            raise ValueError("Category cannot be empty")

        return Transaction(
            id=self.id,
            date=self.date,
            description=self.description,
            amount=self.amount,
            category=new_category,
            account=self.account,
            notes=self.notes,
            reviewed=self.reviewed,
            ai_confidence=confidence,
            created_at=self.created_at,
            updated_at=datetime.now()
        )

    def anonymize(self) -> "Transaction":
        """
        Create anonymized version for logging/debugging.

        Removes potentially sensitive information (description, notes).
        """
        return Transaction(
            id=self.id,
            date=self.date,
            description="[REDACTED]",
            amount=self.amount,
            category=self.category,
            account=self.account,
            notes=None,
            reviewed=self.reviewed,
            ai_confidence=self.ai_confidence,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @property
    def is_expense(self) -> bool:
        """Check if transaction is an expense (negative amount)."""
        return self.amount < 0

    @property
    def is_income(self) -> bool:
        """Check if transaction is income (positive amount)."""
        return self.amount > 0

    @property
    def needs_review(self) -> bool:
        """
        Check if transaction needs manual review.

        Returns True if:
        - Not reviewed yet
        - AI confidence is low (< 0.7)
        """
        if not self.reviewed:
            if self.ai_confidence is None or self.ai_confidence < 0.7:
                return True
        return False

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"{self.date.strftime('%Y-%m-%d')} | {self.description[:30]} | "
            f"${self.amount:,.2f} | {self.category}"
        )

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"Transaction(id={self.id}, date={self.date.date()}, "
            f"description='{self.description}', amount={self.amount}, "
            f"category='{self.category}')"
        )
