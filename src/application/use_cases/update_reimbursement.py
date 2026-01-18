"""Use case for updating transaction reimbursement status."""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.domain.entities.transaction import ReimbursementStatus, Transaction
from src.domain.repositories import TransactionNotFoundError, TransactionRepository

logger = logging.getLogger(__name__)


class UpdateReimbursementUseCase:
    """
    Use case for updating reimbursement status of a transaction.

    This handles recording Tikkie payments and tracking group expense reimbursements.
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
        transaction_id: UUID,
        actual_reimbursement: Decimal,
        status: Optional[ReimbursementStatus] = None
    ) -> Transaction:
        """
        Update reimbursement amount and status for a transaction.

        Args:
            transaction_id: ID of the transaction to update.
            actual_reimbursement: Actual reimbursement amount received.
            status: Optional status override (auto-calculated if None).

        Returns:
            Updated transaction entity.

        Raises:
            TransactionNotFoundError: If transaction doesn't exist.
            ValueError: If reimbursement data is invalid.
            RepositoryError: If update fails.
        """
        # Retrieve transaction
        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(transaction_id)

        # Validate transaction is reimbursable
        if not transaction.reimbursable:
            raise ValueError(
                f"Transaction {transaction_id} is not marked as reimbursable. "
                "Update the transaction to set reimbursable=True first."
            )

        # Update reimbursement
        updated_transaction = transaction.update_reimbursement(
            actual_amount=actual_reimbursement,
            status=status
        )

        # Save to repository
        saved_transaction = self.repository.update(updated_transaction)

        logger.info(
            f"Updated reimbursement for transaction {transaction_id}: "
            f"${actual_reimbursement} | Status: {saved_transaction.reimbursement_status.value} | "
            f"Pending: ${saved_transaction.pending_reimbursement}"
        )

        return saved_transaction

    def mark_as_pending(self, transaction_id: UUID) -> Transaction:
        """
        Mark a reimbursable transaction as pending (no reimbursement yet).

        Args:
            transaction_id: ID of the transaction.

        Returns:
            Updated transaction entity.
        """
        return self.execute(
            transaction_id=transaction_id,
            actual_reimbursement=Decimal("0"),
            status=ReimbursementStatus.PENDING
        )

    def mark_as_complete(
        self,
        transaction_id: UUID,
        actual_reimbursement: Optional[Decimal] = None
    ) -> Transaction:
        """
        Mark a reimbursable transaction as complete.

        Args:
            transaction_id: ID of the transaction.
            actual_reimbursement: Actual amount received (uses expected if None).

        Returns:
            Updated transaction entity.

        Raises:
            TransactionNotFoundError: If transaction doesn't exist.
            ValueError: If actual_reimbursement is None and transaction has no expected amount.
        """
        # Retrieve transaction to get expected reimbursement if needed
        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(transaction_id)

        if actual_reimbursement is None:
            if transaction.expected_reimbursement == 0:
                raise ValueError(
                    "Cannot mark as complete without actual_reimbursement amount "
                    "when transaction has no expected reimbursement set."
                )
            actual_reimbursement = transaction.expected_reimbursement

        return self.execute(
            transaction_id=transaction_id,
            actual_reimbursement=actual_reimbursement,
            status=ReimbursementStatus.COMPLETE
        )

    def record_partial_payment(
        self,
        transaction_id: UUID,
        payment_amount: Decimal
    ) -> Transaction:
        """
        Record a partial reimbursement payment.

        Args:
            transaction_id: ID of the transaction.
            payment_amount: Amount of this partial payment.

        Returns:
            Updated transaction entity.

        Raises:
            TransactionNotFoundError: If transaction doesn't exist.
            ValueError: If payment would exceed expected reimbursement.
        """
        # Retrieve current transaction
        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(transaction_id)

        # Calculate new total
        new_total = transaction.actual_reimbursement + payment_amount

        if new_total > transaction.expected_reimbursement and transaction.expected_reimbursement > 0:
            raise ValueError(
                f"Partial payment of ${payment_amount} would exceed expected reimbursement. "
                f"Current: ${transaction.actual_reimbursement}, "
                f"Expected: ${transaction.expected_reimbursement}"
            )

        return self.execute(
            transaction_id=transaction_id,
            actual_reimbursement=new_total
        )
