"""Use case for creating a transaction."""

import logging
from datetime import datetime
from typing import Optional

from src.application.dtos import CreateTransactionDTO
from src.application.services.auto_tagger import AutoTaggerService
from src.domain.entities import Transaction
from src.domain.repositories import TransactionRepository

logger = logging.getLogger(__name__)


class CreateTransactionUseCase:
    """
    Use case for creating a new transaction.

    This encapsulates the business logic for transaction creation,
    keeping it independent of the UI layer (CLI, API, etc.).
    """

    def __init__(
        self,
        repository: TransactionRepository,
        auto_tagger: Optional[AutoTaggerService] = None
    ):
        """
        Initialize use case.

        Args:
            repository: Transaction repository (can be Notion, SQLite, etc.).
            auto_tagger: Optional auto-tagger service (creates default if None).
        """
        self.repository = repository
        self.auto_tagger = auto_tagger or AutoTaggerService()

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
        # Create transaction entity with user-provided tags
        transaction = Transaction(
            date=dto.date,
            description=dto.description,
            amount=dto.amount,
            category=dto.category,
            subcategory=dto.subcategory,
            summary=dto.summary,
            account=dto.account,
            notes=dto.notes,
            tags=dto.tags.copy() if dto.tags else [],
            reimbursable=dto.reimbursable,
            expected_reimbursement=dto.expected_reimbursement,
            ai_confidence=ai_confidence,
            reviewed=ai_confidence is None or ai_confidence >= 0.9,
        )

        # Apply auto-tags based on category/subcategory
        transaction = self.auto_tagger.apply_tags(
            transaction,
            dto.category,
            dto.subcategory
        )

        # Save transaction
        saved_transaction = self.repository.add(transaction)

        logger.info(
            f"Created transaction: {saved_transaction.id} | "
            f"{saved_transaction.description} | ${saved_transaction.amount} | "
            f"Tags: {saved_transaction.tags} |" f"Category: {saved_transaction.category} | Subcategory: {saved_transaction.subcategory or ''}"
        )

        return saved_transaction
