"""Unit tests for SyncService."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from src.application.dtos.sync_dto import (
    ConflictResolution,
    SyncDirection,
    SyncMode,
    SyncOptions,
)
from src.application.services.sync_service import SyncService
from src.domain.entities import Transaction
from src.domain.entities.transaction import ReimbursementStatus


@pytest.fixture
def mock_notion_repo():
    """Mock Notion repository."""
    return Mock()


@pytest.fixture
def mock_sqlite_repo():
    """Mock SQLite repository."""
    return Mock()


@pytest.fixture
def sync_service(mock_notion_repo, mock_sqlite_repo):
    """Create SyncService with mock repositories."""
    return SyncService(
        notion_repository=mock_notion_repo,
        sqlite_repository=mock_sqlite_repo,
    )


@pytest.fixture
def sample_transaction():
    """Create a sample transaction."""
    return Transaction(
        id=uuid4(),
        date=datetime(2024, 1, 15),
        description="Coffee",
        amount=Decimal("-5.50"),
        category="Food & Dining",
        subcategory="Coffee",
        account="Checking",
        reviewed=True,
        created_at=datetime(2024, 1, 15, 10, 0),
        updated_at=datetime(2024, 1, 15, 10, 0),
    )


class TestSyncServiceUnidirectional:
    """Test unidirectional sync operations."""

    def test_sync_notion_to_sqlite_new_transaction(
        self, sync_service, mock_notion_repo, mock_sqlite_repo, sample_transaction
    ):
        """Test syncing new transaction from Notion to SQLite."""
        # Setup
        mock_notion_repo.list.return_value = [sample_transaction]
        mock_sqlite_repo.list.return_value = []

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert
        assert result.created_in_target == 1
        assert result.updated_in_target == 0
        assert result.skipped == 0
        assert result.errors == 0
        mock_sqlite_repo.add.assert_called_once_with(sample_transaction)

    def test_sync_sqlite_to_notion_new_transaction(
        self, sync_service, mock_notion_repo, mock_sqlite_repo, sample_transaction
    ):
        """Test syncing new transaction from SQLite to Notion."""
        # Setup
        mock_sqlite_repo.list.return_value = [sample_transaction]
        mock_notion_repo.list.return_value = []

        options = SyncOptions(
            direction=SyncDirection.SQLITE_TO_NOTION,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert
        assert result.created_in_target == 1
        assert result.updated_in_target == 0
        assert result.skipped == 0
        assert result.errors == 0
        mock_notion_repo.add.assert_called_once_with(sample_transaction)

    def test_sync_dry_run(
        self, sync_service, mock_notion_repo, mock_sqlite_repo, sample_transaction
    ):
        """Test dry run mode doesn't make changes."""
        # Setup
        mock_notion_repo.list.return_value = [sample_transaction]
        mock_sqlite_repo.list.return_value = []

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
            dry_run=True,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert
        assert result.created_in_target == 1
        assert result.dry_run is True
        mock_sqlite_repo.add.assert_not_called()


class TestSyncServiceConflictResolution:
    """Test conflict resolution strategies."""

    def test_conflict_newest_wins_source_newer(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test newest_wins when source is newer."""
        # Setup - source transaction is newer
        txn_id = uuid4()
        source_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Updated Coffee",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),  # Newer
        )
        target_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Coffee",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),  # Older
        )

        mock_notion_repo.list.return_value = [source_txn]
        mock_sqlite_repo.list.return_value = [target_txn]

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - source should update target
        assert result.updated_in_target == 1
        assert result.conflicts_resolved == 1
        mock_sqlite_repo.update.assert_called_once_with(source_txn)

    def test_conflict_newest_wins_target_newer(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test newest_wins when target is newer."""
        # Setup - target transaction is newer
        txn_id = uuid4()
        source_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Coffee",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),  # Older
        )
        target_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Updated Coffee",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),  # Newer
        )

        mock_notion_repo.list.return_value = [source_txn]
        mock_sqlite_repo.list.return_value = [target_txn]

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - should skip (target is newer)
        assert result.updated_in_target == 0
        assert result.skipped == 1
        mock_sqlite_repo.update.assert_not_called()

    def test_conflict_source_wins(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test source_wins strategy."""
        # Setup
        txn_id = uuid4()
        source_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Source",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )
        target_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Target",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),  # Even if target is newer
        )

        mock_notion_repo.list.return_value = [source_txn]
        mock_sqlite_repo.list.return_value = [target_txn]

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.SOURCE_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - source always wins
        assert result.updated_in_target == 1
        assert result.conflicts_resolved == 1
        mock_sqlite_repo.update.assert_called_once_with(source_txn)

    def test_conflict_target_wins(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test target_wins strategy."""
        # Setup
        txn_id = uuid4()
        source_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Source",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),  # Even if source is newer
        )
        target_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Target",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )

        mock_notion_repo.list.return_value = [source_txn]
        mock_sqlite_repo.list.return_value = [target_txn]

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.TARGET_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - target always wins (skip update)
        assert result.updated_in_target == 0
        assert result.skipped == 1
        mock_sqlite_repo.update.assert_not_called()

    def test_conflict_skip(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test skip strategy."""
        # Setup
        txn_id = uuid4()
        source_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Source",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),
        )
        target_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Target",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )

        mock_notion_repo.list.return_value = [source_txn]
        mock_sqlite_repo.list.return_value = [target_txn]

        options = SyncOptions(
            direction=SyncDirection.NOTION_TO_SQLITE,
            conflict_resolution=ConflictResolution.SKIP,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - conflicts are skipped
        assert result.updated_in_target == 0
        assert result.skipped == 1
        mock_sqlite_repo.update.assert_not_called()


class TestSyncServiceBidirectional:
    """Test bidirectional sync."""

    def test_bidirectional_sync(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test bidirectional sync combines both directions."""
        # Setup - different transactions in each repo
        notion_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Only in Notion",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )
        sqlite_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 16),
            description="Only in SQLite",
            amount=Decimal("-7.00"),
            category="Transportation",
            created_at=datetime(2024, 1, 16, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),
        )

        mock_notion_repo.list.return_value = [notion_txn]
        mock_sqlite_repo.list.return_value = [sqlite_txn]

        options = SyncOptions(
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            mode=SyncMode.FULL,
        )

        # Execute
        result = sync_service.sync(options)

        # Assert - both directions should create
        assert result.created_in_target == 2  # 1 from each direction
        assert result.direction == SyncDirection.BIDIRECTIONAL


class TestSyncServiceStatus:
    """Test sync status checking."""

    def test_get_sync_status_in_sync(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test status when repositories are in sync."""
        # Setup - same transaction in both
        txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Coffee",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )

        mock_notion_repo.list.return_value = [txn]
        mock_sqlite_repo.list.return_value = [txn]

        # Execute
        status = sync_service.get_sync_status()

        # Assert
        assert status["notion_count"] == 1
        assert status["sqlite_count"] == 1
        assert status["only_in_notion"] == 0
        assert status["only_in_sqlite"] == 0
        assert status["out_of_sync"] == 0
        assert status["in_sync"] is True

    def test_get_sync_status_out_of_sync(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test status when repositories are out of sync."""
        # Setup - different transactions
        notion_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 15),
            description="Only in Notion",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )
        sqlite_txn = Transaction(
            id=uuid4(),
            date=datetime(2024, 1, 16),
            description="Only in SQLite",
            amount=Decimal("-7.00"),
            category="Transportation",
            created_at=datetime(2024, 1, 16, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),
        )

        mock_notion_repo.list.return_value = [notion_txn]
        mock_sqlite_repo.list.return_value = [sqlite_txn]

        # Execute
        status = sync_service.get_sync_status()

        # Assert
        assert status["notion_count"] == 1
        assert status["sqlite_count"] == 1
        assert status["only_in_notion"] == 1
        assert status["only_in_sqlite"] == 1
        assert status["out_of_sync"] == 0
        assert status["in_sync"] is False

    def test_get_sync_status_different_data(
        self, sync_service, mock_notion_repo, mock_sqlite_repo
    ):
        """Test status when same transaction has different data."""
        # Setup - same ID, different data
        txn_id = uuid4()
        notion_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Coffee",
            amount=Decimal("-5.50"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 15, 10, 0),
        )
        sqlite_txn = Transaction(
            id=txn_id,
            date=datetime(2024, 1, 15),
            description="Coffee Updated",
            amount=Decimal("-6.00"),
            category="Food & Dining",
            created_at=datetime(2024, 1, 15, 10, 0),
            updated_at=datetime(2024, 1, 16, 10, 0),  # Different update time
        )

        mock_notion_repo.list.return_value = [notion_txn]
        mock_sqlite_repo.list.return_value = [sqlite_txn]

        # Execute
        status = sync_service.get_sync_status()

        # Assert
        assert status["notion_count"] == 1
        assert status["sqlite_count"] == 1
        assert status["only_in_notion"] == 0
        assert status["only_in_sqlite"] == 0
        assert status["out_of_sync"] == 1  # Same ID but different data
        assert status["in_sync"] is False
