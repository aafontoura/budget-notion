"""Budget domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class BudgetPeriod(str, Enum):
    """Budget period types."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class Budget:
    """
    Budget entity for tracking spending limits by category.

    Supports different time periods (monthly, yearly, etc.).
    """

    category_id: UUID
    amount: Decimal
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rollover: bool = False
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate budget data after initialization."""
        if self.amount <= 0:
            raise ValueError("Budget amount must be positive")

        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValueError("End date must be after start date")

    def is_active(self, date: Optional[datetime] = None) -> bool:
        """
        Check if budget is active on the given date.

        Args:
            date: Date to check. Defaults to current date.

        Returns:
            True if budget is active, False otherwise.
        """
        check_date = date or datetime.now()

        if self.start_date and check_date < self.start_date:
            return False

        if self.end_date and check_date > self.end_date:
            return False

        return True

    def calculate_remaining(self, spent: Decimal) -> Decimal:
        """
        Calculate remaining budget amount.

        Args:
            spent: Total amount spent in this budget period.

        Returns:
            Remaining budget (positive) or overspent amount (negative).
        """
        return self.amount - abs(spent)

    def is_overspent(self, spent: Decimal) -> bool:
        """
        Check if budget has been exceeded.

        Args:
            spent: Total amount spent in this budget period.

        Returns:
            True if budget is overspent, False otherwise.
        """
        return abs(spent) > self.amount

    def get_utilization_percentage(self, spent: Decimal) -> float:
        """
        Calculate budget utilization as a percentage.

        Args:
            spent: Total amount spent in this budget period.

        Returns:
            Percentage of budget used (0-100+).
        """
        if self.amount == 0:
            return 0.0

        return (abs(spent) / self.amount) * 100

    def __str__(self) -> str:
        """Human-readable string representation."""
        period_str = self.period.value.capitalize()
        return f"{period_str} budget: ${self.amount:,.2f}"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"Budget(id={self.id}, category_id={self.category_id}, "
            f"amount={self.amount}, period={self.period.value})"
        )
