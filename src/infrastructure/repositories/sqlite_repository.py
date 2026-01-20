"""SQLite implementation of TransactionRepository for local caching and testing."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import UUID

from src.domain.entities import Transaction
from src.domain.entities.transaction import ReimbursementStatus
from src.domain.repositories import (
    RepositoryError,
    TransactionNotFoundError,
    TransactionRepository,
)

logger = logging.getLogger(__name__)


class SQLiteTransactionRepository(TransactionRepository):
    """
    SQLite-based implementation of TransactionRepository.

    Useful for:
    - Local caching of Notion data
    - Offline mode
    - Testing without Notion API calls
    - Faster queries for analysis
    """

    def __init__(self, db_path: str | Path = "transactions.db"):
        """
        Initialize SQLite repository.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    summary TEXT,
                    account TEXT,
                    notes TEXT,
                    reviewed INTEGER NOT NULL DEFAULT 0,
                    ai_confidence REAL,
                    tags TEXT DEFAULT '[]',
                    reimbursable INTEGER NOT NULL DEFAULT 0,
                    expected_reimbursement REAL DEFAULT 0.0,
                    actual_reimbursement REAL DEFAULT 0.0,
                    reimbursement_status TEXT DEFAULT 'none',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_date ON transactions(date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON transactions(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_account ON transactions(account)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reimbursement_status ON transactions(reimbursement_status)
            """)

            conn.commit()

            # Run migrations for existing databases
            self._migrate_database(conn)

            logger.info(f"Initialized SQLite database at {self.db_path}")

    def _migrate_database(self, conn: sqlite3.Connection) -> None:
        """Add new columns to existing databases if they don't exist."""
        try:
            # Check if tags column exists
            cursor = conn.execute("PRAGMA table_info(transactions)")
            columns = {row[1] for row in cursor.fetchall()}

            migrations_needed = []

            if 'tags' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN tags TEXT DEFAULT '[]'")
            if 'reimbursable' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN reimbursable INTEGER NOT NULL DEFAULT 0")
            if 'expected_reimbursement' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN expected_reimbursement REAL DEFAULT 0.0")
            if 'actual_reimbursement' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN actual_reimbursement REAL DEFAULT 0.0")
            if 'reimbursement_status' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN reimbursement_status TEXT DEFAULT 'none'")
            if 'subcategory' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN subcategory TEXT")
            if 'summary' not in columns:
                migrations_needed.append("ALTER TABLE transactions ADD COLUMN summary TEXT")

            for migration in migrations_needed:
                conn.execute(migration)
                logger.info(f"Ran migration: {migration}")

            if migrations_needed:
                # Create index for reimbursement status
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reimbursement_status ON transactions(reimbursement_status)
                """)
                conn.commit()
                logger.info(f"Applied {len(migrations_needed)} database migrations")
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            raise

    def add(self, transaction: Transaction) -> Transaction:
        """Add a new transaction to SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO transactions (
                        id, date, description, amount, category, subcategory, summary,
                        account, notes, reviewed, ai_confidence,
                        tags, reimbursable, expected_reimbursement,
                        actual_reimbursement, reimbursement_status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(transaction.id),
                    transaction.date.isoformat(),
                    transaction.description,
                    float(transaction.amount),
                    transaction.category,
                    transaction.subcategory,
                    transaction.summary,
                    transaction.account,
                    transaction.notes,
                    1 if transaction.reviewed else 0,
                    transaction.ai_confidence,
                    json.dumps(transaction.tags),
                    1 if transaction.reimbursable else 0,
                    float(transaction.expected_reimbursement),
                    float(transaction.actual_reimbursement),
                    transaction.reimbursement_status.value,
                    transaction.created_at.isoformat(),
                    transaction.updated_at.isoformat(),
                ))
                conn.commit()

            logger.info(f"Added transaction to SQLite: {transaction.id}")
            return transaction

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error while adding transaction: {e}")
            raise RepositoryError(f"Transaction already exists: {transaction.id}") from e
        except Exception as e:
            logger.error(f"Error while adding transaction: {e}")
            raise RepositoryError(f"Failed to add transaction: {e}") from e

    def get(self, transaction_id: UUID) -> Optional[Transaction]:
        """Retrieve a transaction by ID from SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM transactions WHERE id = ?
                """, (str(transaction_id),))

                row = cursor.fetchone()

                if row is None:
                    return None

                return self._row_to_transaction(row)

        except Exception as e:
            logger.error(f"Error while getting transaction: {e}")
            raise RepositoryError(f"Failed to get transaction: {e}") from e

    def list(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        account: Optional[str] = None,
        tags: Optional[list[str]] = None,
        reimbursable_status: Optional[ReimbursementStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> "list[Transaction]":
        """List transactions with optional filtering."""
        try:
            # Build query with filters
            query = "SELECT * FROM transactions WHERE 1=1"
            params = []

            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())

            if category:
                query += " AND category = ?"
                params.append(category)

            if account:
                query += " AND account = ?"
                params.append(account)

            if reimbursable_status:
                query += " AND reimbursement_status = ?"
                params.append(reimbursable_status.value)

            # Order by date descending
            query += " ORDER BY date DESC"

            # Apply limit and offset
            if limit:
                query += " LIMIT ?"
                params.append(limit)

            if offset:
                query += " OFFSET ?"
                params.append(offset)

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                transactions = [self._row_to_transaction(row) for row in rows]

            # Apply tag filtering in-memory (SQLite doesn't have good JSON search)
            if tags:
                transactions = [
                    t for t in transactions
                    if any(t.has_tag(tag) for tag in tags)
                ]

            logger.info(f"Retrieved {len(transactions)} transactions from SQLite")
            return transactions

        except Exception as e:
            logger.error(f"Error while listing transactions: {e}")
            raise RepositoryError(f"Failed to list transactions: {e}") from e

    def update(self, transaction: Transaction) -> Transaction:
        """Update an existing transaction in SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE transactions SET
                        date = ?,
                        description = ?,
                        amount = ?,
                        category = ?,
                        subcategory = ?,
                        summary = ?,
                        account = ?,
                        notes = ?,
                        reviewed = ?,
                        ai_confidence = ?,
                        tags = ?,
                        reimbursable = ?,
                        expected_reimbursement = ?,
                        actual_reimbursement = ?,
                        reimbursement_status = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    transaction.date.isoformat(),
                    transaction.description,
                    float(transaction.amount),
                    transaction.category,
                    transaction.subcategory,
                    transaction.summary,
                    transaction.account,
                    transaction.notes,
                    1 if transaction.reviewed else 0,
                    transaction.ai_confidence,
                    json.dumps(transaction.tags),
                    1 if transaction.reimbursable else 0,
                    float(transaction.expected_reimbursement),
                    float(transaction.actual_reimbursement),
                    transaction.reimbursement_status.value,
                    datetime.now().isoformat(),
                    str(transaction.id),
                ))

                if cursor.rowcount == 0:
                    raise TransactionNotFoundError(transaction.id)

                conn.commit()

            logger.info(f"Updated transaction in SQLite: {transaction.id}")
            return transaction

        except TransactionNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error while updating transaction: {e}")
            raise RepositoryError(f"Failed to update transaction: {e}") from e

    def delete(self, transaction_id: UUID) -> bool:
        """Delete a transaction from SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM transactions WHERE id = ?
                """, (str(transaction_id),))
                conn.commit()

                deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"Deleted transaction from SQLite: {transaction_id}")

            return deleted

        except Exception as e:
            logger.error(f"Error while deleting transaction: {e}")
            raise RepositoryError(f"Failed to delete transaction: {e}") from e

    def get_by_category(self, category: str) -> "list[Transaction]":
        """Get all transactions for a specific category."""
        return self.list(category=category)

    def get_total_by_category(
        self,
        category: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """Calculate total spending/income for a category."""
        try:
            query = "SELECT SUM(amount) as total FROM transactions WHERE category = ?"
            params = [category]

            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                result = cursor.fetchone()

                total = result[0] if result[0] is not None else 0.0

            return Decimal(str(total))

        except Exception as e:
            logger.error(f"Error while calculating total: {e}")
            raise RepositoryError(f"Failed to calculate total: {e}") from e

    def search(self, query: str) -> "list[Transaction]":
        """Search transactions by description."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM transactions
                    WHERE description LIKE ?
                    ORDER BY date DESC
                """, (f"%{query}%",))

                rows = cursor.fetchall()
                transactions = [self._row_to_transaction(row) for row in rows]

            logger.info(f"Found {len(transactions)} transactions matching '{query}'")
            return transactions

        except Exception as e:
            logger.error(f"Error while searching transactions: {e}")
            raise RepositoryError(f"Failed to search transactions: {e}") from e

    def get_by_tag(self, tag: str) -> "list[Transaction]":
        """Get all transactions with a specific tag."""
        return self.list(tags=[tag])

    def get_pending_reimbursements(self) -> "list[Transaction]":
        """Get all transactions with pending or partial reimbursements."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM transactions
                    WHERE reimbursement_status IN ('pending', 'partial')
                    ORDER BY date DESC
                """)

                rows = cursor.fetchall()
                transactions = [self._row_to_transaction(row) for row in rows]

            logger.info(f"Found {len(transactions)} pending reimbursements")
            return transactions

        except Exception as e:
            logger.error(f"Error while getting pending reimbursements: {e}")
            raise RepositoryError(f"Failed to get pending reimbursements: {e}") from e

    def get_total_by_tag(
        self,
        tag: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """Calculate total spending/income for transactions with a specific tag."""
        transactions = self.get_by_tag(tag)

        # Apply date filtering
        if start_date:
            transactions = [t for t in transactions if t.date >= start_date]
        if end_date:
            transactions = [t for t in transactions if t.date <= end_date]

        total = sum((t.amount for t in transactions), Decimal("0"))
        return total

    # Helper methods

    def clear_all(self) -> None:
        """Clear all transactions (useful for testing)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM transactions")
            conn.commit()
        logger.info("Cleared all transactions from SQLite")

    def get_statistics(self) -> dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) as expense_count,
                    SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as income_count,
                    SUM(amount) as net_total,
                    SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as total_expenses,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income
                FROM transactions
            """)
            row = cursor.fetchone()

            return {
                "total_transactions": row[0] or 0,
                "expense_count": row[1] or 0,
                "income_count": row[2] or 0,
                "net_total": Decimal(str(row[3] or 0)),
                "total_expenses": Decimal(str(row[4] or 0)),
                "total_income": Decimal(str(row[5] or 0)),
            }

    @staticmethod
    def _row_to_transaction(row: sqlite3.Row) -> Transaction:
        """Convert SQLite row to Transaction entity."""
        # Parse tags from JSON
        try:
            tags_json = row["tags"] if "tags" in row.keys() else "[]"
            tags = json.loads(tags_json) if tags_json else []
        except (KeyError, json.JSONDecodeError):
            tags = []

        # Parse reimbursement status
        try:
            status_str = row["reimbursement_status"] if "reimbursement_status" in row.keys() else "none"
            reimbursement_status = ReimbursementStatus(status_str)
        except (KeyError, ValueError):
            reimbursement_status = ReimbursementStatus.NONE

        # Helper to safely get values with defaults
        def safe_get(key: str, default):
            try:
                return row[key] if key in row.keys() and row[key] is not None else default
            except KeyError:
                return default

        return Transaction(
            id=UUID(row["id"]),
            date=datetime.fromisoformat(row["date"]),
            description=row["description"],
            amount=Decimal(str(row["amount"])),
            category=row["category"],
            subcategory=safe_get("subcategory", None),
            summary=safe_get("summary", None),
            account=row["account"],
            notes=row["notes"],
            reviewed=bool(row["reviewed"]),
            ai_confidence=row["ai_confidence"],
            tags=tags,
            reimbursable=bool(safe_get("reimbursable", 0)),
            expected_reimbursement=Decimal(str(safe_get("expected_reimbursement", 0.0))),
            actual_reimbursement=Decimal(str(safe_get("actual_reimbursement", 0.0))),
            reimbursement_status=reimbursement_status,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
