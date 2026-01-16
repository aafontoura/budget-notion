"""Use case for creating a transaction."""

import logging
from datetime import datetime
from typing import Optional

from src.application.dtos import CreateTransactionDTO
from src.domain.entities import Transaction
from src.domain.repositories import TransactionRepository

logger = logging.getLogger(__name__)


class CreateTransactionUseCase:
    """
    Use case for creating a new transaction.

    This encapsulates the business logic for transaction creation,
    keeping it independent of the UI layer (CLI, API, etc.).
    """

    def __init__(self, repository: TransactionRepository):
        """
        Initialize use case.

        Args:
            repository: Transaction repository (can be Notion, SQLite, etc.).
        """
        self.repository = repository

    def execute(
        self,
        dto: CreateTransactionDTO,
        ai_confidence: Optional[float] = None,
    ) -> Transaction:
        """
        Create a new transaction.

        Args:
            dto: Transaction creation data.
            ai_confidence: Optional AI categorization confidence (0.0-1.0).

        Returns:
            Created transaction entity.

        Raises:
            ValueError: If transaction data is invalid.
            RepositoryError: If transaction cannot be saved.
        """
        # Create transaction entity
        transaction = Transaction(
            date=dto.date,
            description=dto.description,
            amount=dto.amount,
            category=dto.category,
            account=dto.account,
            notes=dto.notes,
            ai_confidence=ai_confidence,
            reviewed=ai_confidence is None or ai_confidence >= 0.9,
        )

        # Save transaction
        saved_transaction = self.repository.add(transaction)

        logger.info(
            f"Created transaction: {saved_transaction.id} | "
            f"{saved_transaction.description} | ${saved_transaction.amount}"
        )

        return saved_transaction
