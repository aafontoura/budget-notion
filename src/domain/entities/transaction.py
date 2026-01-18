"""Transaction domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ReimbursementStatus(str, Enum):
    """Reimbursement status for group payments/Tikkie."""

    NONE = "none"
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"


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
    subcategory: Optional[str] = None
    account: Optional[str] = None
    notes: Optional[str] = None
    reviewed: bool = False
    ai_confidence: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    reimbursable: bool = False
    expected_reimbursement: Decimal = field(default_factory=lambda: Decimal("0"))
    actual_reimbursement: Decimal = field(default_factory=lambda: Decimal("0"))
    reimbursement_status: ReimbursementStatus = ReimbursementStatus.NONE
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

        # Validate reimbursement fields
        if self.expected_reimbursement < 0:
            raise ValueError("Expected reimbursement cannot be negative")

        if self.actual_reimbursement < 0:
            raise ValueError("Actual reimbursement cannot be negative")

        if self.actual_reimbursement > abs(self.amount):
            raise ValueError("Actual reimbursement cannot exceed transaction amount")

        # Normalize tags to lowercase
        self.tags = [tag.lower().strip() for tag in self.tags if tag.strip()]

        # Auto-update reimbursement status based on amounts
        if not self.reimbursable:
            self.reimbursement_status = ReimbursementStatus.NONE
        elif self.actual_reimbursement == 0:
            self.reimbursement_status = ReimbursementStatus.PENDING
        elif self.actual_reimbursement >= self.expected_reimbursement and self.expected_reimbursement > 0:
            self.reimbursement_status = ReimbursementStatus.COMPLETE
        elif self.actual_reimbursement > 0:
            self.reimbursement_status = ReimbursementStatus.PARTIAL

    def mark_as_reviewed(self) -> "Transaction":
        """
        Mark transaction as reviewed by user.

        Returns a new Transaction instance (immutable pattern).
        """
        return self._copy_with(reviewed=True)

    def update_category(self, new_category: str, new_subcategory: str = "", confidence: Optional[float] = None) -> "Transaction":
        """
        Update transaction category.

        Returns a new Transaction instance (immutable pattern).
        """
        if not new_category or not new_category.strip():
            raise ValueError("Category cannot be empty")

        return self._copy_with(category=new_category, subcategory=new_subcategory, ai_confidence=confidence)

    def anonymize(self) -> "Transaction":
        """
        Create anonymized version for logging/debugging.

        Removes potentially sensitive information (description, notes).
        """
        return self._copy_with(
            description="[REDACTED]",
            notes=None,
            updated_at=self.updated_at  # Don't update timestamp for anonymization
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

    @property
    def net_amount(self) -> Decimal:
        """
        Calculate net amount after reimbursements.

        Returns:
            Amount minus actual reimbursement.
        """
        return self.amount + self.actual_reimbursement if self.amount < 0 else self.amount - self.actual_reimbursement

    @property
    def is_fully_reimbursed(self) -> bool:
        """Check if transaction is fully reimbursed."""
        return self.reimbursement_status == ReimbursementStatus.COMPLETE

    @property
    def pending_reimbursement(self) -> Decimal:
        """Calculate remaining reimbursement amount."""
        if not self.reimbursable:
            return Decimal("0")
        return max(Decimal("0"), self.expected_reimbursement - self.actual_reimbursement)

    def has_tag(self, tag: str) -> bool:
        """
        Check if transaction has a specific tag.

        Args:
            tag: Tag to check (case-insensitive).

        Returns:
            True if tag exists.
        """
        return tag.lower() in self.tags

    def add_tag(self, tag: str) -> "Transaction":
        """
        Add a tag to the transaction.

        Returns a new Transaction instance (immutable pattern).

        Args:
            tag: Tag to add.

        Returns:
            New Transaction with tag added.
        """
        tag = tag.lower().strip()
        if not tag or tag in self.tags:
            return self

        new_tags = self.tags + [tag]
        return self._copy_with(tags=new_tags)

    def remove_tag(self, tag: str) -> "Transaction":
        """
        Remove a tag from the transaction.

        Returns a new Transaction instance (immutable pattern).

        Args:
            tag: Tag to remove.

        Returns:
            New Transaction with tag removed.
        """
        tag = tag.lower().strip()
        if tag not in self.tags:
            return self

        new_tags = [t for t in self.tags if t != tag]
        return self._copy_with(tags=new_tags)

    def update_reimbursement(
        self,
        actual_amount: Decimal,
        status: Optional[ReimbursementStatus] = None
    ) -> "Transaction":
        """
        Update reimbursement amount and status.

        Returns a new Transaction instance (immutable pattern).

        Args:
            actual_amount: Actual reimbursement received.
            status: Override status (auto-calculated if None).

        Returns:
            New Transaction with updated reimbursement.
        """
        if actual_amount < 0:
            raise ValueError("Reimbursement amount cannot be negative")

        if actual_amount > abs(self.amount):
            raise ValueError("Reimbursement cannot exceed transaction amount")

        # Auto-calculate status if not provided
        if status is None:
            if actual_amount == 0:
                status = ReimbursementStatus.PENDING
            elif actual_amount >= self.expected_reimbursement and self.expected_reimbursement > 0:
                status = ReimbursementStatus.COMPLETE
            elif actual_amount > 0:
                status = ReimbursementStatus.PARTIAL
            else:
                status = ReimbursementStatus.NONE

        return self._copy_with(
            actual_reimbursement=actual_amount,
            reimbursement_status=status
        )

    def _copy_with(self, **kwargs) -> "Transaction":
        """
        Create a copy of transaction with specified fields updated.

        Args:
            **kwargs: Fields to update.

        Returns:
            New Transaction instance.
        """
        return Transaction(
            id=kwargs.get('id', self.id),
            date=kwargs.get('date', self.date),
            description=kwargs.get('description', self.description),
            amount=kwargs.get('amount', self.amount),
            category=kwargs.get('category', self.category),
            subcategory=kwargs.get('subcategory', self.subcategory),
            account=kwargs.get('account', self.account),
            notes=kwargs.get('notes', self.notes),
            reviewed=kwargs.get('reviewed', self.reviewed),
            ai_confidence=kwargs.get('ai_confidence', self.ai_confidence),
            tags=kwargs.get('tags', self.tags.copy()),
            reimbursable=kwargs.get('reimbursable', self.reimbursable),
            expected_reimbursement=kwargs.get('expected_reimbursement', self.expected_reimbursement),
            actual_reimbursement=kwargs.get('actual_reimbursement', self.actual_reimbursement),
            reimbursement_status=kwargs.get('reimbursement_status', self.reimbursement_status),
            created_at=kwargs.get('created_at', self.created_at),
            updated_at=kwargs.get('updated_at', datetime.now())
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"{self.date.strftime('%Y-%m-%d')} | {self.description[:30]} | "
            f"${self.amount:,.2f} | {self.category} | {self.subcategory or ''} | {self.ai_confidence or 'N/A'} | {self.account or ''}"
        )

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"Transaction(id={self.id}, date={self.date.date()}, "
            f"description='{self.description}', amount={self.amount}, "
            f"category='{self.category}')"
        )
