"""Use case for synchronizing transactions between repositories."""

import logging
from typing import Optional

from src.application.dtos.sync_dto import (
    ConflictResolution,
    SyncDirection,
    SyncMode,
    SyncOptions,
    SyncResult,
)
from src.application.services.sync_service import SyncService
from src.domain.repositories import RepositoryError

logger = logging.getLogger(__name__)


class SyncTransactionsUseCase:
    """
    Use case for synchronizing transactions between Notion and SQLite.

    This use case orchestrates the synchronization process, providing
    a clean interface for the CLI layer.
    """

    def __init__(self, sync_service: SyncService):
        """
        Initialize sync use case.

        Args:
            sync_service: Service for performing synchronization.
        """
        self.sync_service = sync_service

    def execute(
        self,
        direction: str,
        conflict_resolution: str = "newest_wins",
        mode: str = "full",
        dry_run: bool = False,
    ) -> SyncResult:
        """
        Execute synchronization between repositories.

        Args:
            direction: Sync direction ("notion_to_sqlite", "sqlite_to_notion", or "bidirectional").
            conflict_resolution: Conflict resolution strategy ("source_wins", "target_wins", "newest_wins", or "skip").
            mode: Sync mode ("full" or "incremental").
            dry_run: If True, preview changes without applying them.

        Returns:
            SyncResult with statistics and status.

        Raises:
            ValueError: If invalid direction or strategy provided.
            RepositoryError: If sync operation fails.
        """
        # Validate and parse direction
        try:
            sync_direction = SyncDirection(direction)
        except ValueError:
            raise ValueError(
                f"Invalid sync direction: {direction}. "
                f"Must be one of: {', '.join([d.value for d in SyncDirection])}"
            )

        # Validate and parse conflict resolution
        try:
            conflict_strategy = ConflictResolution(conflict_resolution)
        except ValueError:
            raise ValueError(
                f"Invalid conflict resolution strategy: {conflict_resolution}. "
                f"Must be one of: {', '.join([c.value for c in ConflictResolution])}"
            )

        # Validate and parse sync mode
        try:
            sync_mode = SyncMode(mode)
        except ValueError:
            raise ValueError(
                f"Invalid sync mode: {mode}. "
                f"Must be one of: {', '.join([m.value for m in SyncMode])}"
            )

        # Create sync options
        options = SyncOptions(
            direction=sync_direction,
            conflict_resolution=conflict_strategy,
            mode=sync_mode,
            dry_run=dry_run,
        )

        logger.info(
            f"Executing sync use case: direction={direction}, "
            f"conflict_resolution={conflict_resolution}, "
            f"mode={mode}, dry_run={dry_run}"
        )

        # Perform synchronization
        try:
            result = self.sync_service.sync(options)
            logger.info(f"Sync completed successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise

    def get_status(self) -> dict:
        """
        Get current synchronization status.

        Returns:
            Dictionary with sync status information including:
            - notion_count: Number of transactions in Notion
            - sqlite_count: Number of transactions in SQLite
            - only_in_notion: Transactions only in Notion
            - only_in_sqlite: Transactions only in SQLite
            - out_of_sync: Transactions that differ between repositories
            - in_sync: Boolean indicating if repositories are in sync

        Raises:
            RepositoryError: If status check fails.
        """
        logger.info("Checking sync status")
        try:
            status = self.sync_service.get_sync_status()
            logger.info(f"Sync status: {status}")
            return status
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            raise
