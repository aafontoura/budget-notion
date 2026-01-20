"""Service for synchronizing transactions between repositories."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.domain.entities import Transaction
from src.domain.repositories import TransactionRepository, RepositoryError
from src.application.dtos.sync_dto import (
    ConflictResolution,
    SyncDirection,
    SyncMode,
    SyncOptions,
    SyncResult,
)

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service for synchronizing transactions between Notion and SQLite repositories.

    Handles conflict resolution, incremental sync, and bidirectional sync.
    """

    def __init__(
        self,
        notion_repository: TransactionRepository,
        sqlite_repository: TransactionRepository,
    ):
        """
        Initialize sync service.

        Args:
            notion_repository: Notion transaction repository.
            sqlite_repository: SQLite transaction repository.
        """
        self.notion_repository = notion_repository
        self.sqlite_repository = sqlite_repository

    def sync(self, options: SyncOptions) -> SyncResult:
        """
        Synchronize transactions between repositories.

        Args:
            options: Synchronization options.

        Returns:
            SyncResult with statistics and status.

        Raises:
            RepositoryError: If sync operation fails.
        """
        logger.info(
            f"Starting sync: {options.direction.value} "
            f"(mode={options.mode.value}, "
            f"conflict_resolution={options.conflict_resolution.value}, "
            f"dry_run={options.dry_run})"
        )

        result = SyncResult(
            direction=options.direction,
            dry_run=options.dry_run,
            started_at=datetime.now(),
        )

        try:
            if options.direction == SyncDirection.NOTION_TO_SQLITE:
                self._sync_unidirectional(
                    source=self.notion_repository,
                    target=self.sqlite_repository,
                    options=options,
                    result=result,
                )
            elif options.direction == SyncDirection.SQLITE_TO_NOTION:
                self._sync_unidirectional(
                    source=self.sqlite_repository,
                    target=self.notion_repository,
                    options=options,
                    result=result,
                )
            elif options.direction == SyncDirection.BIDIRECTIONAL:
                # Bidirectional sync: sync both directions
                logger.info("Performing bidirectional sync (Notion → SQLite)")
                result_n2s = SyncResult(
                    direction=SyncDirection.NOTION_TO_SQLITE,
                    dry_run=options.dry_run,
                    started_at=datetime.now(),
                )
                self._sync_unidirectional(
                    source=self.notion_repository,
                    target=self.sqlite_repository,
                    options=options,
                    result=result_n2s,
                )

                logger.info("Performing bidirectional sync (SQLite → Notion)")
                result_s2n = SyncResult(
                    direction=SyncDirection.SQLITE_TO_NOTION,
                    dry_run=options.dry_run,
                    started_at=datetime.now(),
                )
                self._sync_unidirectional(
                    source=self.sqlite_repository,
                    target=self.notion_repository,
                    options=options,
                    result=result_s2n,
                )

                # Merge results
                result.created_in_target = (
                    result_n2s.created_in_target + result_s2n.created_in_target
                )
                result.updated_in_target = (
                    result_n2s.updated_in_target + result_s2n.updated_in_target
                )
                result.skipped = result_n2s.skipped + result_s2n.skipped
                result.conflicts_resolved = (
                    result_n2s.conflicts_resolved + result_s2n.conflicts_resolved
                )
                result.errors = result_n2s.errors + result_s2n.errors
                result.total_processed = (
                    result_n2s.total_processed + result_s2n.total_processed
                )

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result.errors += 1
            raise RepositoryError(f"Sync operation failed: {e}") from e
        finally:
            result.completed_at = datetime.now()

        logger.info(f"Sync completed: {result}")
        return result

    def _sync_unidirectional(
        self,
        source: TransactionRepository,
        target: TransactionRepository,
        options: SyncOptions,
        result: SyncResult,
    ) -> None:
        """
        Perform unidirectional sync from source to target.

        Args:
            source: Source repository to read from.
            target: Target repository to write to.
            options: Synchronization options.
            result: SyncResult object to update with statistics.
        """
        # Get all transactions from source
        if options.mode == SyncMode.INCREMENTAL and options.last_sync_time:
            logger.info(f"Incremental sync since {options.last_sync_time}")
            # For incremental, we need to filter by updated_at
            # Note: Current repository interface doesn't support filtering by updated_at
            # We'll fetch all and filter in memory
            source_transactions = source.list()
            source_transactions = [
                t for t in source_transactions
                if t.updated_at >= options.last_sync_time
            ]
        else:
            source_transactions = source.list()

        logger.info(f"Found {len(source_transactions)} transactions in source")

        # Build a map of existing transactions in target by UUID
        target_transactions = target.list()
        target_map: dict[UUID, Transaction] = {t.id: t for t in target_transactions}

        logger.info(f"Found {len(target_transactions)} transactions in target")

        # Process each source transaction
        for source_txn in source_transactions:
            result.total_processed += 1

            try:
                if source_txn.id not in target_map:
                    # New transaction: add to target
                    if not options.dry_run:
                        target.add(source_txn)
                    result.created_in_target += 1
                    logger.debug(f"Created transaction in target: {source_txn.id}")
                else:
                    # Existing transaction: check for updates
                    target_txn = target_map[source_txn.id]

                    if self._needs_update(source_txn, target_txn):
                        # Conflict: resolve based on strategy
                        should_update = self._resolve_conflict(
                            source_txn=source_txn,
                            target_txn=target_txn,
                            strategy=options.conflict_resolution,
                        )

                        if should_update:
                            if not options.dry_run:
                                target.update(source_txn)
                            result.updated_in_target += 1
                            result.conflicts_resolved += 1
                            logger.debug(
                                f"Updated transaction in target: {source_txn.id} "
                                f"(strategy={options.conflict_resolution.value})"
                            )
                        else:
                            result.skipped += 1
                            logger.debug(
                                f"Skipped transaction: {source_txn.id} "
                                f"(strategy={options.conflict_resolution.value})"
                            )

            except Exception as e:
                logger.error(f"Error syncing transaction {source_txn.id}: {e}")
                result.errors += 1

    def _needs_update(self, source: Transaction, target: Transaction) -> bool:
        """
        Check if source transaction has changes compared to target.

        Args:
            source: Source transaction.
            target: Target transaction.

        Returns:
            True if source has been updated more recently or has different data.
        """
        # Check if updated_at timestamps differ
        if source.updated_at != target.updated_at:
            return True

        # For additional safety, check key fields
        if (
            source.date != target.date
            or source.description != target.description
            or source.amount != target.amount
            or source.category != target.category
            or source.subcategory != target.subcategory
            or source.account != target.account
            or source.notes != target.notes
            or source.reviewed != target.reviewed
            or source.ai_confidence != target.ai_confidence
            or source.tags != target.tags
            or source.reimbursable != target.reimbursable
            or source.expected_reimbursement != target.expected_reimbursement
            or source.actual_reimbursement != target.actual_reimbursement
            or source.reimbursement_status != target.reimbursement_status
        ):
            return True

        return False

    def _resolve_conflict(
        self,
        source_txn: Transaction,
        target_txn: Transaction,
        strategy: ConflictResolution,
    ) -> bool:
        """
        Resolve conflict between source and target transaction.

        Args:
            source_txn: Transaction from source repository.
            target_txn: Transaction from target repository.
            strategy: Conflict resolution strategy.

        Returns:
            True if source should overwrite target, False otherwise.
        """
        if strategy == ConflictResolution.SOURCE_WINS:
            return True
        elif strategy == ConflictResolution.TARGET_WINS:
            return False
        elif strategy == ConflictResolution.SKIP:
            return False
        elif strategy == ConflictResolution.NEWEST_WINS:
            # Use the transaction with the most recent updated_at
            return source_txn.updated_at > target_txn.updated_at
        else:
            logger.warning(f"Unknown conflict resolution strategy: {strategy}")
            return False

    def get_sync_status(self) -> dict:
        """
        Get current sync status and statistics.

        Returns:
            Dictionary with sync status information.
        """
        try:
            notion_count = len(self.notion_repository.list())
            sqlite_count = len(self.sqlite_repository.list())

            # Get all transactions to check for differences
            notion_txns = {t.id: t for t in self.notion_repository.list()}
            sqlite_txns = {t.id: t for t in self.sqlite_repository.list()}

            only_in_notion = len(set(notion_txns.keys()) - set(sqlite_txns.keys()))
            only_in_sqlite = len(set(sqlite_txns.keys()) - set(notion_txns.keys()))

            # Check for out-of-sync transactions (same ID, different data)
            out_of_sync = 0
            for txn_id in set(notion_txns.keys()) & set(sqlite_txns.keys()):
                if self._needs_update(notion_txns[txn_id], sqlite_txns[txn_id]):
                    out_of_sync += 1

            return {
                "notion_count": notion_count,
                "sqlite_count": sqlite_count,
                "only_in_notion": only_in_notion,
                "only_in_sqlite": only_in_sqlite,
                "out_of_sync": out_of_sync,
                "in_sync": (
                    notion_count == sqlite_count
                    and only_in_notion == 0
                    and only_in_sqlite == 0
                    and out_of_sync == 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            raise RepositoryError(f"Failed to get sync status: {e}") from e
