"""Transaction repository interface (Port in Hexagonal Architecture)."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.domain.entities import Transaction


class TransactionRepository(ABC):
    """
    Abstract repository interface for transaction persistence.

    This interface defines the contract for transaction storage and retrieval,
    allowing different implementations (Notion, SQLite, PostgreSQL, etc.)
    to be swapped without changing business logic.

    This is the key abstraction that enables UI/storage layer swapping.
    """

    @abstractmethod
    def add(self, transaction: Transaction) -> Transaction:
        """
        Add a new transaction to the repository.

        Args:
            transaction: Transaction entity to add.

        Returns:
            The added transaction with any updates (e.g., assigned ID).

        Raises:
            RepositoryError: If transaction cannot be added.
        """
        pass

    @abstractmethod
    def get(self, transaction_id: UUID) -> Optional[Transaction]:
        """
        Retrieve a transaction by ID.

        Args:
            transaction_id: Unique identifier of the transaction.

        Returns:
            Transaction if found, None otherwise.

        Raises:
            RepositoryError: If retrieval fails.
        """
        pass

    @abstractmethod
    def list(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        account: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Transaction]:
        """
        List transactions with optional filtering.

        Args:
            start_date: Filter transactions on or after this date.
            end_date: Filter transactions on or before this date.
            category: Filter by category name.
            account: Filter by account name.
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip (for pagination).

        Returns:
            List of transactions matching the filters.

        Raises:
            RepositoryError: If listing fails.
        """
        pass

    @abstractmethod
    def update(self, transaction: Transaction) -> Transaction:
        """
        Update an existing transaction.

        Args:
            transaction: Transaction entity with updated data.

        Returns:
            The updated transaction.

        Raises:
            RepositoryError: If transaction not found or update fails.
        """
        pass

    @abstractmethod
    def delete(self, transaction_id: UUID) -> bool:
        """
        Delete a transaction by ID.

        Args:
            transaction_id: Unique identifier of the transaction to delete.

        Returns:
            True if transaction was deleted, False if not found.

        Raises:
            RepositoryError: If deletion fails.
        """
        pass

    @abstractmethod
    def get_by_category(self, category: str) -> list[Transaction]:
        """
        Get all transactions for a specific category.

        Args:
            category: Category name.

        Returns:
            List of transactions in the category.

        Raises:
            RepositoryError: If retrieval fails.
        """
        pass

    @abstractmethod
    def get_total_by_category(
        self,
        category: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """
        Calculate total spending/income for a category.

        Args:
            category: Category name.
            start_date: Filter transactions on or after this date.
            end_date: Filter transactions on or before this date.

        Returns:
            Total amount (positive for income, negative for expenses).

        Raises:
            RepositoryError: If calculation fails.
        """
        pass

    @abstractmethod
    def search(self, query: str) -> list[Transaction]:
        """
        Search transactions by description.

        Args:
            query: Search query string.

        Returns:
            List of transactions matching the query.

        Raises:
            RepositoryError: If search fails.
        """
        pass


class RepositoryError(Exception):
    """Base exception for repository errors."""

    pass


class TransactionNotFoundError(RepositoryError):
    """Raised when a transaction is not found."""

    def __init__(self, transaction_id: UUID):
        super().__init__(f"Transaction not found: {transaction_id}")
        self.transaction_id = transaction_id


class DuplicateTransactionError(RepositoryError):
    """Raised when attempting to add a duplicate transaction."""

    def __init__(self, message: str = "Duplicate transaction detected"):
        super().__init__(message)
