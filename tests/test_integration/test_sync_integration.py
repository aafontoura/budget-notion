"""Integration tests for sync functionality."""

import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from src.application.dtos.sync_dto import (
    ConflictResolution,
    SyncDirection,
    SyncMode,
    SyncOptions,
)
from src.application.services.sync_service import SyncService
from src.application.use_cases.sync_transactions import SyncTransactionsUseCase
from src.domain.entities import Transaction
from src.infrastructure.repositories import SQLiteTransactionRepository


@pytest.fixture
def temp_db_path():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def notion_sqlite_repo(temp_db_path):
    """SQLite repository acting as Notion (for testing)."""
    return SQLiteTransactionRepository(db_path=temp_db_path)


@pytest.fixture
def target_sqlite_repo():
    """SQLite repository acting as target."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return SQLiteTransactionRepository(db_path=Path(f.name))


@pytest.fixture
def sync_service(notion_sqlite_repo, target_sqlite_repo):
    """Create SyncService with SQLite repositories."""
    return SyncService(
        notion_repository=notion_sqlite_repo,
        sqlite_repository=target_sqlite_repo,
    )


@pytest.fixture
def sync_use_case(sync_service):
    """Create SyncTransactionsUseCase."""
    return SyncTransactionsUseCase(sync_service=sync_service)


@pytest.fixture
def sample_transactions():
    """Create sample transactions."""
    return [
        Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Coffee at Starbucks",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            subcategory="Coffee",
            account="Checking",
            reviewed=True,
        ),
        Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 16),
            description="Uber ride",
            amount=Decimal("-12.00"),
            category="Transportation",
            subcategory="Taxi",
            account="Credit Card",
            reviewed=False,
        ),
        Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 17),
            description="Grocery shopping",
            amount=Decimal("-45.30"),
            category="Food & Dining",
            subcategory="Groceries",
            account="Checking",
            tags=["weekly", "essentials"],
            reviewed=True,
        ),
    ]


class TestSyncIntegration:
    """Integration tests for sync service."""

    def test_sync_new_transactions_notion_to_sqlite(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo, sample_transactions
    ):
        """Test syncing new transactions from Notion to SQLite."""
        # Add transactions to source (notion)
        for txn in sample_transactions:
            notion_sqlite_repo.add(txn)

        # Sync
        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        result = sync_service.sync(options)

        # Verify results
        assert result.created_in_target == 3
        assert result.updated_in_target == 0
        assert result.errors == 0

        # Verify all transactions are in target
        target_txns = target_sqlite_repo.list()
        assert len(target_txns) == 3

        # Verify transaction data - sort by ID for consistent comparison
        original_sorted = sorted(sample_transactions, key=lambda t: str(t.id))
        synced_sorted = sorted(target_txns, key=lambda t: str(t.id))

        for original, synced in zip(original_sorted, synced_sorted):
            assert synced.id == original.id
            assert synced.description == original.description
            assert synced.amount == original.amount
            assert synced.category == original.category

    def test_sync_new_transactions_sqlite_to_notion(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo, sample_transactions
    ):
        """Test syncing new transactions from SQLite to Notion."""
        # Add transactions to source (sqlite)
        for txn in sample_transactions:
            target_sqlite_repo.add(txn)

        # Sync
        options = SyncOptions(
            direction=SyncDirection.SQLITE_TO_NOTION,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        result = sync_service.sync(options)

        # Verify results
        assert result.created_in_target == 3
        assert result.updated_in_target == 0
        assert result.errors == 0

        # Verify all transactions are in target
        notion_txns = notion_sqlite_repo.list()
        assert len(notion_txns) == 3

    def test_sync_bidirectional(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test bidirectional sync."""
        # Add different transactions to each repo
        notion_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Only in Notion",
            amount=Decimal("-10.00"),
            category="Shopping",
        )
        sqlite_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 16),
            description="Only in SQLite",
            amount=Decimal("-20.00"),
            category="Entertainment",
        )

        notion_sqlite_repo.add(notion_txn)
        target_sqlite_repo.add(sqlite_txn)

        # Sync bidirectionally
        options = SyncOptions(
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        result = sync_service.sync(options)

        # Verify both transactions are in both repos
        assert result.created_in_target == 2
        assert len(notion_sqlite_repo.list()) == 2
        assert len(target_sqlite_repo.list()) == 2

    def test_sync_conflict_newest_wins(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test conflict resolution with newest_wins strategy."""
        # Create same transaction with different data
        txn_id = uuid4()
        older_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Original",
            amount=Decimal("-5.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )
        newer_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Updated",
            amount=Decimal("-7.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),
        )

        # Add older to notion, newer to sqlite
        notion_sqlite_repo.add(older_txn)
        target_sqlite_repo.add(newer_txn)

        # Sync notion to sqlite (newer should win, so skip)
        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        result = sync_service.sync(options)

        assert result.updated_in_target == 0
        assert result.skipped == 1

        # Verify target still has newer version
        target_txn = target_sqlite_repo.get(txn_id)
        assert target_txn.description == "Updated"
        assert target_txn.amount == Decimal("-7.00")

    def test_sync_dry_run(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo, sample_transactions
    ):
        """Test dry run doesn't make changes."""
        # Add transactions to source
        for txn in sample_transactions:
            notion_sqlite_repo.add(txn)

        # Dry run sync
        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
            dry_run=True,
        )
        result = sync_service.sync(options)

        # Verify results show what would happen
        assert result.created_in_target == 3
        assert result.dry_run is True

        # Verify no changes were made
        assert len(target_sqlite_repo.list()) == 0

    def test_sync_status(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test sync status checking."""
        # Add different transactions to each
        notion_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Notion only",
            amount=Decimal("-10.00"),
            category="Shopping",
        )
        sqlite_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 16),
            description="SQLite only",
            amount=Decimal("-20.00"),
            category="Entertainment",
        )

        notion_sqlite_repo.add(notion_txn)
        target_sqlite_repo.add(sqlite_txn)

        # Check status
        status = sync_service.get_sync_status()

        assert status["notion_count"] == 1
        assert status["sqlite_count"] == 1
        assert status["only_in_notion"] == 1
        assert status["only_in_sqlite"] == 1
        assert status["in_sync"] is False


class TestSyncUseCaseIntegration:
    """Integration tests for SyncTransactionsUseCase."""

    def test_use_case_sync_notion_to_sqlite(
        self, sync_use_case, notion_sqlite_repo, sample_transactions
    ):
        """Test sync use case with notion_to_sqlite direction."""
        # Add transactions to notion
        for txn in sample_transactions:
            notion_sqlite_repo.add(txn)

        # Execute use case
        result = sync_use_case.execute(
            direction="notion_to_sqlite",
            conflict_resolution="newest_wins",
            mode="full",
            dry_run=False,
        )

        assert result.created_in_target == 3
        assert result.direction == SyncDirection.NOTION_TO_SQLITE

    def test_use_case_invalid_direction(self, sync_use_case):
        """Test use case with invalid direction."""
        with pytest.raises(ValueError, match="Invalid sync direction"):
            sync_use_case.execute(
                direction="invalid_direction",
                conflict_resolution="newest_wins",
                mode="full",
            )

    def test_use_case_invalid_conflict_resolution(self, sync_use_case):
        """Test use case with invalid conflict resolution."""
        with pytest.raises(ValueError, match="Invalid conflict resolution strategy"):
            sync_use_case.execute(
                direction="notion_to_sqlite",
                conflict_resolution="invalid_strategy",
                mode="full",
            )

    def test_use_case_get_status(
        self, sync_use_case, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test use case get_status method."""
        # Add a transaction to notion
        txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Test",
            amount=Decimal("-10.00"),
            category="Shopping",
        )
        notion_sqlite_repo.add(txn)

        # Get status
        status = sync_use_case.get_status()

        assert status["notion_count"] == 1
        assert status["sqlite_count"] == 0
        assert status["in_sync"] is False


class TestSyncComplexScenarios:
    """Test complex sync scenarios."""

    def test_sync_with_tags_and_reimbursements(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test syncing transactions with tags and reimbursement data."""
        # Create transaction with complex data
        txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Group dinner",
            amount=Decimal("-50.00"),
            category="Food & Dining",
            subcategory="Restaurant",
            account="Credit Card",
            tags=["reimbursable", "team", "dinner"],
            reimbursable=True,
            expected_reimbursement=Decimal("25.00"),
            reviewed=True,
        )

        notion_sqlite_repo.add(txn)

        # Sync
        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        sync_service.sync(options)

        # Verify all fields are synced
        synced_txn = target_sqlite_repo.get(txn.id)
        assert synced_txn is not None
        assert synced_txn.tags == ["reimbursable", "team", "dinner"]
        assert synced_txn.reimbursable is True
        assert synced_txn.expected_reimbursement == Decimal("25.00")
        assert synced_txn.reviewed is True

    def test_sync_multiple_conflicts(
        self, sync_service, notion_sqlite_repo, target_sqlite_repo
    ):
        """Test syncing with multiple conflicting transactions."""
        # Create 3 transactions with conflicts
        base_time = datetime(2024, 1, 15, 10, 0)
        for i in range(3):
            txn_id = uuid4()

            # Older version in notion
            notion_txn = Transaction(
                id=txn_id,
                date=datetime(2024, 1, 15 + i),
                description=f"Transaction {i}",
                amount=Decimal(f"-{10 + i}.00"),
                category="Shopping",
                created_at=base_time,
                updated_at=base_time,
            )

            # Newer version in sqlite
            sqlite_txn = Transaction(
                id=txn_id,
                date=datetime(2024, 1, 15 + i),
                description=f"Updated Transaction {i}",
                amount=Decimal(f"-{15 + i}.00"),
                category="Shopping",
                created_at=base_time,
                updated_at=base_time.replace(day=16),
            )

            notion_sqlite_repo.add(notion_txn)
            target_sqlite_repo.add(sqlite_txn)

        # Sync with newest_wins
        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )
        result = sync_service.sync(options)

        # All should be skipped (sqlite versions are newer)
        assert result.skipped == 3
        assert result.updated_in_target == 0

        # Verify sqlite versions are unchanged
        for i in range(3):
            txns = [t for t in target_sqlite_repo.list() if f"Transaction {i}" in t.description]
            assert len(txns) == 1
            assert "Updated" in txns[0].description
