"""DTOs for synchronization operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SyncDirection(str, Enum):
    """Direction for synchronization."""

    NOTION_TO_SQLITE = "notion_to_sqlite"
    SQLITE_TO_NOTION = "sqlite_to_notion"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(str, Enum):
    """Strategy for resolving conflicts during sync."""

    SOURCE_WINS = "source_wins"  # Source repository always wins
    TARGET_WINS = "target_wins"  # Target repository always wins
    NEWEST_WINS = "newest_wins"  # Most recently updated wins (default)
    SKIP = "skip"  # Skip conflicting transactions


class SyncMode(str, Enum):
    """Synchronization mode."""

    FULL = "full"  # Sync all transactions
    INCREMENTAL = "incremental"  # Sync only new/updated since last sync


@dataclass
class SyncOptions:
    """Options for synchronization operation."""

    direction: SyncDirection
    conflict_resolution: ConflictResolution = ConflictResolution.NEWEST_WINS
    mode: SyncMode = SyncMode.FULL
    last_sync_time: Optional[datetime] = None
    dry_run: bool = False  # Preview changes without applying them


@dataclass
class SyncResult:
    """Result of a synchronization operation."""

    direction: SyncDirection
    created_in_target: int = 0
    updated_in_target: int = 0
    skipped: int = 0
    conflicts_resolved: int = 0
    errors: int = 0
    total_processed: int = 0
    dry_run: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate sync duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def __str__(self) -> str:
        """Human-readable summary."""
        mode = "[DRY RUN] " if self.dry_run else ""
        return (
            f"{mode}Sync Result ({self.direction.value}):\n"
            f"  Created: {self.created_in_target}\n"
            f"  Updated: {self.updated_in_target}\n"
            f"  Skipped: {self.skipped}\n"
            f"  Conflicts Resolved: {self.conflicts_resolved}\n"
            f"  Errors: {self.errors}\n"
            f"  Total Processed: {self.total_processed}\n"
            f"  Duration: {self.duration_seconds:.2f}s"
        )
