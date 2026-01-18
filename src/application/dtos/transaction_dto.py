"""Data Transfer Objects for transactions."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CreateTransactionDTO(BaseModel):
    """DTO for creating a new transaction."""

    date: datetime
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    account: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)
    tags: list[str] = Field(default_factory=list)
    reimbursable: bool = False
    expected_reimbursement: Decimal = Field(default=Decimal("0"))

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Validate description is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v: str) -> str:
        """Validate category is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Category cannot be empty")
        return v.strip()

    @field_validator("expected_reimbursement")
    @classmethod
    def validate_reimbursement(cls, v: Decimal) -> Decimal:
        """Validate reimbursement amount is non-negative."""
        if v < 0:
            raise ValueError("Expected reimbursement cannot be negative")
        return v


class UpdateTransactionDTO(BaseModel):
    """DTO for updating an existing transaction."""

    date: Optional[datetime] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount: Optional[Decimal] = None
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    account: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)
    reviewed: Optional[bool] = None


class TransactionFilterDTO(BaseModel):
    """DTO for filtering transactions."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = None
    account: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class ImportCSVDTO(BaseModel):
    """DTO for CSV import configuration."""

    file_path: str
    default_category: str = "Uncategorized"
    account_name: Optional[str] = None
    bank_config: Optional[str] = None  # e.g., "ing", "rabobank", "generic_us"
